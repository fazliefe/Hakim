from __future__ import annotations

import pytest

from hakim_legal_schema.ids import (
    CanonicalIdError,
    article_id,
    article_version_id,
    court_id,
    decision_id,
    law_id,
    parse_canonical_id,
)


def test_law_id_for_tck() -> None:
    assert law_id("5237") == "law:5237"


def test_article_identity_is_stable_across_versions() -> None:
    assert article_id("5237", "158") == "law:5237:article:158"


def test_article_version_id_includes_version() -> None:
    assert article_version_id("5237", "158", 4) == "law:5237:article:158:v4"


def test_article_no_keeps_letter_suffix() -> None:
    assert article_id("5237", "158/A") == "law:5237:article:158/A"


def test_decision_id_uses_court_year_and_docket() -> None:
    assert (
        decision_id(court="yargitay", year=2021, docket="2019/1234", decision_no="2021/5678")
        == "decision:yargitay:2021:2019/1234:2021/5678"
    )


def test_court_id() -> None:
    assert court_id("yargitay") == "court:yargitay"


def test_parse_roundtrip_article_version() -> None:
    parsed = parse_canonical_id("law:5237:article:158:v4")
    assert parsed.kind == "article_version"
    assert parsed.law_number == "5237"
    assert parsed.article_no == "158"
    assert parsed.version == 4


@pytest.mark.parametrize("value", ["", "5237", "law:", "law:5237:article:"])
def test_invalid_ids_are_rejected(value: str) -> None:
    with pytest.raises(CanonicalIdError):
        parse_canonical_id(value)
