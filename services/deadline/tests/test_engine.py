from __future__ import annotations

from datetime import date

from deadline.engine import CalendarType, DurationUnit, compute_last_day


def test_criminal_deadline_moves_off_weekend() -> None:
    # 7 days from Friday 2026-08-14 is Friday 2026-08-21 (weekday).
    last = compute_last_day(
        trigger=date(2026, 8, 14),
        duration=7,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 8, 21)


def test_criminal_deadline_friday_plus_one_is_monday() -> None:
    last = compute_last_day(
        trigger=date(2026, 8, 14),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
    )
    assert last == date(2026, 8, 17)
    assert last.weekday() == 0


def test_administrative_deadline_moves_off_weekend() -> None:
    # Friday 2026-08-14 + 1 day falls on Saturday; İYUK usulünde de ertesi iş gününe sarkar.
    last = compute_last_day(
        trigger=date(2026, 8, 14),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.ADMINISTRATIVE,
    )
    assert last == date(2026, 8, 17)
    assert last.weekday() == 0


def test_civil_deadline_keeps_calendar_day() -> None:
    last = compute_last_day(
        trigger=date(2026, 8, 14),
        duration=1,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CIVIL,
    )
    assert last == date(2026, 8, 15)
