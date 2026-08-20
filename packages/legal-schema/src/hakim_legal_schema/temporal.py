from __future__ import annotations

from datetime import date, datetime
from typing import TypeVar

from hakim_legal_schema.entities import TemporalVersion

T = TypeVar("T", bound=TemporalVersion)


def resolve_version(versions: list[T], at: datetime) -> T | None:
    """Return the unique version in force at `at`, using a half-open range."""
    matches = [version for version in versions if version.is_in_force_at(at)]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("overlapping temporal versions; data model invariant violated")
    return matches[0]


def as_of_date(versions: list[T], on: date) -> T | None:
    at = datetime(on.year, on.month, on.day, tzinfo=versions[0].valid_from.tzinfo) if versions else None
    if at is None:
        return None
    return resolve_version(versions, at)
