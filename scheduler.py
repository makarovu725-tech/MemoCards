"""Алгоритм интервального повторения (упрощённый SM-2)."""
from datetime import date, timedelta

FORGOT, HARD, GOOD, EASY = 0, 1, 2, 3
GRADE_NAMES = {FORGOT: "Забыл", HARD: "Трудно", GOOD: "Хорошо", EASY: "Легко"}

MIN_EASE = 1.3


def next_review(ease: float, interval: int, repetitions: int, grade: int,
                today: date | None = None) -> dict:
    """Возвращает новые параметры карточки после ответа.

    ease        - коэффициент лёгкости (старт 2.5)
    interval    - текущий интервал в днях
    repetitions - число подряд успешных повторений
    grade       - оценка: 0 забыл, 1 трудно, 2 хорошо, 3 легко
    """
    today = today or date.today()

    if grade == FORGOT:
        repetitions = 0
        interval = 0  # показать снова сегодня
        ease = max(MIN_EASE, ease - 0.2)
        state = "learning"
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 3
        else:
            interval = round(interval * ease)

        if grade == HARD:
            interval = max(1, round(interval * 0.8))
            ease = max(MIN_EASE, ease - 0.15)
        elif grade == EASY:
            interval = round(interval * 1.3) + 1
            ease += 0.15

        repetitions += 1
        state = "mature" if interval >= 21 else "learning"

    return {
        "ease": round(ease, 2),
        "interval": interval,
        "repetitions": repetitions,
        "due_date": (today + timedelta(days=interval)).isoformat(),
        "state": state,
    }
