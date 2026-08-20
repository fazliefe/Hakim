from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from hakim_legal_schema.entities import (
    Article,
    ArticleVersion,
    CourtDecision,
    DeadlineRule,
    Law,
    Publication,
    Source,
)
from hakim_legal_schema.enums import (
    AuthorityLevel,
    CalendarType,
    DocumentType,
    DurationUnit,
    ProvenanceKind,
)


def test_tck_law_record() -> None:
    law = Law(
        id="law:5237",
        number="5237",
        title="Türk Ceza Kanunu",
        publication=Publication(date=date(2004, 10, 12), gazette_number="25611"),
        source=Source(
            provider="mevzuat.gov.tr",
            official=True,
            retrieved_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            content_hash="abc123",
        ),
    )
    assert law.type == DocumentType.LAW
    assert law.source.authority == AuthorityLevel.OFFICIAL
    assert law.publication.gazette_number == "25611"


def test_article_version_is_temporally_bounded() -> None:
    version = ArticleVersion(
        id="law:5237:article:158:v4",
        article_id="law:5237:article:158",
        law_id="law:5237",
        article_no="158",
        title="Nitelikli dolandırıcılık",
        text="Madde metni...",
        version=4,
        valid_from=datetime(2016, 7, 1, tzinfo=timezone.utc),
        valid_until=None,
    )
    assert version.is_in_force_at(datetime(2021, 3, 1, tzinfo=timezone.utc))
    assert version.valid_until is None


def test_article_identity_points_at_law() -> None:
    article = Article(id="law:5237:article:158", law_id="law:5237", article_no="158")
    assert article.id == "law:5237:article:158"


def test_official_source_cannot_be_user_authority() -> None:
    with pytest.raises(ValidationError):
        Source(
            provider="mevzuat.gov.tr",
            official=True,
            retrieved_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            content_hash="abc",
            authority=AuthorityLevel.USER,
        )


def test_deadline_rule_is_deterministic() -> None:
    rule = DeadlineRule(
        id="deadline:appeal:notification:14d",
        procedure="appeal",
        trigger="notification",
        duration=14,
        unit=DurationUnit.DAY,
        calendar_type=CalendarType.CIVIL,
        legal_basis=["law:2577:article:7"],
    )
    assert rule.duration == 14
    assert rule.provenance == ProvenanceKind.OFFICIAL_TEXT


def test_court_decision_requires_court() -> None:
    decision = CourtDecision(
        id="decision:yargitay:2021:2019/1234:2021/5678",
        court_id="court:yargitay",
        year=2021,
        docket_no="2019/1234",
        decision_no="2021/5678",
        decision_date=date(2021, 4, 12),
        title="Yargıtay kararı",
        source=Source(
            provider="yargitay.gov.tr",
            official=True,
            retrieved_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            content_hash="def",
        ),
    )
    assert decision.type == DocumentType.COURT_DECISION
    assert decision.court_id == "court:yargitay"
