from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from hakim_legal_schema.enums import CalendarType, DurationUnit


def compute_last_day(
    *,
    trigger: date,
    duration: int,
    unit: DurationUnit,
    calendar: CalendarType,
) -> date:
    """Deterministic last day. The model does not calculate time; this function does."""
    if duration < 1:
        raise ValueError("duration must be >= 1")
    if unit is DurationUnit.DAY:
        last = trigger + timedelta(days=duration)
    elif unit is DurationUnit.WEEK:
        last = trigger + timedelta(weeks=duration)
    elif unit is DurationUnit.MONTH:
        month = trigger.month - 1 + duration
        year = trigger.year + month // 12
        month = month % 12 + 1
        day = min(trigger.day, _month_days(year, month))
        last = date(year, month, day)
    elif unit is DurationUnit.YEAR:
        try:
            last = date(trigger.year + duration, trigger.month, trigger.day)
        except ValueError:
            last = date(trigger.year + duration, trigger.month, 28)
    else:
        raise ValueError(f"unsupported unit: {unit}")

    if calendar is CalendarType.CRIMINAL:
        last = _next_business_day(last)
    return last


def _month_days(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _next_business_day(value: date) -> date:
    if value.weekday() == 5:
        return value + timedelta(days=2)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


@dataclass(frozen=True, slots=True)
class DeadlineComputation:
    rule_id: str
    name: str
    trigger: date | None
    duration: int
    unit: DurationUnit
    calendar: CalendarType
    last_day: date | None
    legal_basis: tuple[str, ...]
    missing: str | None = None
