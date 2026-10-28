"""Слой работы с базой данных SQLite."""
import sqlite3
from datetime import date

from scheduler import next_review

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id     INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front       TEXT NOT NULL,
    back        TEXT NOT NULL,
    hint        TEXT DEFAULT '',
    ease        REAL NOT NULL DEFAULT 2.5,
    interval    INTEGER NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    due_date    TEXT,
    state       TEXT NOT NULL DEFAULT 'new'   -- new / learning / mature
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    reviewed_at TEXT NOT NULL,
    grade       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path: str = "memocards.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---------- колоды ----------
    def add_deck(self, name: str, description: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO decks (name, description) VALUES (?, ?)",
            (name, description))
        self.conn.commit()
        return cur.lastrowid

    def update_deck(self, deck_id: int, name: str, description: str = ""):
        self.conn.execute(
            "UPDATE decks SET name = ?, description = ? WHERE id = ?",
            (name, description, deck_id))
        self.conn.commit()

    def delete_deck(self, deck_id: int):
        self.conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        self.conn.commit()

    def get_decks(self) -> list[sqlite3.Row]:
        """Колоды с количеством карточек и числом карточек к повторению."""
        today = date.today().isoformat()
        return self.conn.execute(
            """SELECT d.id, d.name, d.description,
                      COUNT(c.id) AS total,
                      SUM(CASE WHEN c.state = 'new' THEN 1 ELSE 0 END) AS new_count,
                      SUM(CASE WHEN c.state != 'new' AND c.due_date <= ? THEN 1 ELSE 0 END) AS due_count
               FROM decks d LEFT JOIN cards c ON c.deck_id = d.id
               GROUP BY d.id ORDER BY d.name""", (today,)).fetchall()

    # ---------- карточки ----------
    def add_card(self, deck_id: int, front: str, back: str, hint: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO cards (deck_id, front, back, hint) VALUES (?, ?, ?, ?)",
            (deck_id, front, back, hint))
        self.conn.commit()
        return cur.lastrowid

    def update_card(self, card_id: int, front: str, back: str, hint: str = ""):
        self.conn.execute(
            "UPDATE cards SET front = ?, back = ?, hint = ? WHERE id = ?",
            (front, back, hint, card_id))
        self.conn.commit()

    def delete_card(self, card_id: int):
        self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self.conn.commit()

    def get_cards(self, deck_id: int, text: str = "", state: str | None = None):
        """Список карточек с поиском по тексту и фильтром по состоянию."""
        query = "SELECT * FROM cards WHERE deck_id = ?"
        params: list = [deck_id]
        if text:
            query += " AND (front LIKE ? OR back LIKE ?)"
            params += [f"%{text}%", f"%{text}%"]
        if state:
            query += " AND state = ?"
            params.append(state)
        return self.conn.execute(query + " ORDER BY id", params).fetchall()

    # ---------- обучение ----------
    def get_study_queue(self, deck_id: int, new_limit: int = 10):
        """Карточки на сегодня: сначала просроченные, затем новые (с лимитом)."""
        today = date.today().isoformat()
        due = self.conn.execute(
            """SELECT * FROM cards
               WHERE deck_id = ? AND state != 'new' AND due_date <= ?
               ORDER BY due_date""", (deck_id, today)).fetchall()
        new = self.conn.execute(
            "SELECT * FROM cards WHERE deck_id = ? AND state = 'new' LIMIT ?",
            (deck_id, new_limit)).fetchall()
        return list(due) + list(new)

    def answer_card(self, card_id: int, grade: int):
        """Сохраняет ответ: пересчитывает расписание и пишет историю."""
        card = self.conn.execute(
            "SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        res = next_review(card["ease"], card["interval"],
                          card["repetitions"], grade)
        self.conn.execute(
            """UPDATE cards SET ease = ?, interval = ?, repetitions = ?,
               due_date = ?, state = ? WHERE id = ?""",
            (res["ease"], res["interval"], res["repetitions"],
             res["due_date"], res["state"], card_id))
        self.conn.execute(
            "INSERT INTO reviews (card_id, reviewed_at, grade) VALUES (?, ?, ?)",
            (card_id, date.today().isoformat(), grade))
        self.conn.commit()

    # ---------- статистика ----------
    def reviews_per_day(self, days: int = 14):
        return self.conn.execute(
            """SELECT reviewed_at AS day, COUNT(*) AS total,
                      SUM(CASE WHEN grade > 0 THEN 1 ELSE 0 END) AS correct
               FROM reviews GROUP BY reviewed_at
               ORDER BY reviewed_at DESC LIMIT ?""", (days,)).fetchall()

    def cards_by_state(self):
        return self.conn.execute(
            "SELECT state, COUNT(*) AS n FROM cards GROUP BY state").fetchall()

    # ---------- настройки ----------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value))
        self.conn.commit()
