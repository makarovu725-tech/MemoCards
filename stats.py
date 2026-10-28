"""Расчёт статистики обучения (без зависимости от Qt)."""
from datetime import date, timedelta

from database import Database

STATE_ORDER = ["new", "learning", "mature"]


def calc_streak(review_days: set[str], today: date | None = None) -> int:
    """Сколько дней подряд были повторения.

    Если сегодня ещё не занимались, серия не обрывается:
    считаем от вчерашнего дня.
    """
    today = today or date.today()
    day = today if today.isoformat() in review_days else today - timedelta(days=1)
    streak = 0
    while day.isoformat() in review_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def collect_stats(db: Database, days: int = 14,
                  today: date | None = None) -> dict:
    """Собирает всю статистику для окна и графиков."""
    today = today or date.today()

    # карточки по состояниям
    states = {key: 0 for key in STATE_ORDER}
    for row in db.cards_by_state():
        states[row["state"]] = row["n"]

    # история за всё время: серия, точность, всего повторений
    history = db.reviews_per_day(days=36500)
    by_day = {r["day"]: (r["total"], r["correct"] or 0) for r in history}
    total_reviews = sum(t for t, _ in by_day.values())
    total_correct = sum(c for _, c in by_day.values())
    accuracy = (round(100 * total_correct / total_reviews)
                if total_reviews else None)

    # последние N дней с нулями в днях без повторений
    last_days = []
    for offset in range(days - 1, -1, -1):
        d = today - timedelta(days=offset)
        total, correct = by_day.get(d.isoformat(), (0, 0))
        last_days.append((d, total, correct))

    return {
        "states": states,
        "total_cards": sum(states.values()),
        "total_reviews": total_reviews,
        "accuracy": accuracy,
        "streak": calc_streak(set(by_day), today),
        "days": last_days,
    }
