from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from hakim_legal_schema.entities import ArticleVersion
from hakim_legal_schema.temporal import resolve_version


def _version(n: int, start: str, end: str | None) -> ArticleVersion:
    valid_until = None if end is None else datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    return ArticleVersion(
        id=f"law:5237:article:158:v{n}",
        article_id="law:5237:article:158",
        law_id="law:5237",
        article_no="158",
        title="Nitelikli dolandırıcılık",
        text=f"version {n}",
        version=n,
        valid_from=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
        valid_until=valid_until,
    )


def test_historical_query_uses_then_in_force_text() -> None:
    versions = [
        _version(3, "2005-06-01T00:00:00", "2016-07-01T00:00:00"),
        _version(4, "2016-07-01T00:00:00", None),
    ]
    at = datetime(2012, 1, 15, tzinfo=timezone.utc)
    chosen = resolve_version(versions, at)
    assert chosen is not None
    assert chosen.version == 3
    assert chosen.text == "version 3"


def test_current_query_uses_open_ended_version() -> None:
    versions = [
        _version(3, "2005-06-01T00:00:00", "2016-07-01T00:00:00"),
        _version(4, "2016-07-01T00:00:00", None),
    ]
    chosen = resolve_version(versions, datetime(2021, 3, 1, tzinfo=timezone.utc))
    assert chosen is not None
    assert chosen.version == 4


def test_query_before_first_version_returns_none() -> None:
    versions = [_version(1, "2005-06-01T00:00:00", None)]
    assert resolve_version(versions, datetime(2004, 1, 1, tzinfo=timezone.utc)) is None


def test_valid_until_must_be_after_valid_from() -> None:
    with pytest.raises(ValidationError):
        _version(1, "2016-07-01T00:00:00", "2015-01-01T00:00:00")
