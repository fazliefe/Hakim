from __future__ import annotations

from datetime import date
from pathlib import Path

from mevzuat.parser import parse_mevzuat_html

FIXTURE = Path(__file__).parent / "fixtures" / "tck_snippet.html"


def test_parse_extracts_law_metadata() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    assert result.number == "5237"
    assert "Türk Ceza Kanunu" in result.title or "TÜRK CEZA KANUNU" in result.title.upper()
    assert result.publication_date == date(2004, 10, 12)
    assert result.gazette_number == "25611"


def test_parse_extracts_article_1_and_158() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    by_no = {a.article_no: a for a in result.articles}
    assert "1" in by_no
    assert "158" in by_no
    assert "Nitelikli" in (by_no["158"].title or "")
    assert "Dolandırıcılık" in by_no["158"].text or "dolandırıcılık" in by_no["158"].text.lower()
    assert by_no["1"].text.startswith("Madde 1")


def test_article_ids_are_canonical() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    a158 = next(a for a in result.articles if a.article_no == "158")
    assert a158.id == "law:5237:article:158"
    assert a158.version_id == "law:5237:article:158:v1"
