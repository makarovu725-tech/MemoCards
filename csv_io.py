"""Импорт и экспорт колод в CSV (без зависимости от Qt).

Формат файла: столбцы «лицевая сторона; обратная сторона; подсказка».
Подсказка необязательна. Экспорт пишет UTF-8 с BOM и разделителем «;»,
чтобы файл корректно открывался в Excel. Импорт сам определяет
кодировку (UTF-8 или Windows-1251) и разделитель («;», «,» или Tab).
"""
import csv
import io
import os

from database import Database

HEADER = ["front", "back", "hint"]
# первая строка считается заголовком, если в первой ячейке одно из этих слов
HEADER_NAMES = {"front", "лицевая сторона", "вопрос", "слово", "термин"}
ENCODINGS = ("utf-8-sig", "cp1251")


class CsvError(Exception):
    """Понятная пользователю ошибка импорта или экспорта."""


def export_deck(db: Database, deck_id: int, path: str) -> int:
    """Сохраняет карточки колоды в CSV. Возвращает число карточек."""
    cards = db.get_cards(deck_id)
    if not cards:
        raise CsvError("В колоде нет карточек, экспортировать нечего.")
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(HEADER)
        for card in cards:
            writer.writerow([card["front"], card["back"], card["hint"] or ""])
    return len(cards)


def _read_text(path: str) -> str:
    for encoding in ENCODINGS:
        try:
            with open(path, "r", encoding=encoding, newline="") as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    raise CsvError("Не удалось определить кодировку файла. "
                   "Сохрани его в UTF-8 или Windows-1251.")


def _detect_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.strip() else ""
    best = max(";\t,", key=first_line.count)
    return best if first_line.count(best) else ";"


def parse_csv(path: str) -> tuple[list[tuple[str, str, str]], int]:
    """Читает файл. Возвращает (список карточек, число пропущенных строк)."""
    text = _read_text(path)
    if not text.strip():
        raise CsvError("Файл пустой.")

    try:
        rows = list(csv.reader(io.StringIO(text),
                               delimiter=_detect_delimiter(text)))
    except csv.Error as error:
        raise CsvError(f"Файл повреждён или не похож на CSV: {error}")

    if rows and rows[0] and rows[0][0].strip().lower() in HEADER_NAMES:
        rows = rows[1:]

    cards, skipped = [], 0
    for row in rows:
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue  # пустая строка, не считаем ошибкой
        if len(cells) < 2 or not cells[0] or not cells[1]:
            skipped += 1
            continue
        hint = cells[2] if len(cells) > 2 else ""
        cards.append((cells[0], cells[1], hint))

    if not cards:
        raise CsvError("В файле нет подходящих карточек. "
                       "Нужно минимум два столбца: лицевая и обратная сторона.")
    return cards, skipped


def import_deck(db: Database, path: str) -> tuple[str, int, int]:
    """Создаёт новую колоду из CSV.

    Название берётся из имени файла; если такая колода уже есть,
    добавляется номер. Возвращает (название, добавлено, пропущено).
    """
    cards, skipped = parse_csv(path)

    name = os.path.splitext(os.path.basename(path))[0].strip() or "Импорт"
    existing = {deck["name"] for deck in db.get_decks()}
    candidate, number = name, 2
    while candidate in existing:
        candidate = f"{name} ({number})"
        number += 1

    deck_id = db.add_deck(candidate, "Импортировано из CSV")
    db.conn.executemany(
        "INSERT INTO cards (deck_id, front, back, hint) VALUES (?, ?, ?, ?)",
        [(deck_id, front, back, hint) for front, back, hint in cards])
    db.conn.commit()
    return candidate, len(cards), skipped
