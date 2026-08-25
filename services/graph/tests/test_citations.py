from __future__ import annotations

from graph.citations import citations_to_relations, extract_article_citations, extract_law_article_citations


def test_extract_ordinal_citations() -> None:
    text = (
        "Bir Türk vatandaşı, 13 üncü maddede yazılı suçlar dışında, "
        "11 ve 12 nci maddelerde belirtilen hallerde..."
    )
    cites = extract_article_citations(text, from_article_no="11")
    targets = {c.to_article_no for c in cites}
    assert "13" in targets
    assert "12" in targets
    assert "11" not in targets


def test_extract_madde_keyword() -> None:
    text = "Bu fiil Madde 158 kapsamında nitelikli dolandırıcılıktır."
    cites = extract_article_citations(text, from_article_no="157")
    assert cites[0].to_article_no == "158"


def test_citations_become_official_relations() -> None:
    cites = extract_article_citations("13 üncü maddede yazılı suçlar", from_article_no="11")
    rels = citations_to_relations(cites, law_number="5237")
    assert rels[0].from_id == "law:5237:article:11"
    assert rels[0].to_id == "law:5237:article:13"
    assert rels[0].relation_type.value == "REFERENCES"
    assert rels[0].provenance.value == "official_text"
    assert rels[0].confidence == 1.0


def test_extract_law_article_citations_uses_nearby_abbreviation() -> None:
    text = "Yerel mahkemece CMK'nın 100 üncü maddesi uyarınca tutuklamaya karar verilmiştir."
    cites = extract_law_article_citations(text, from_article_no="_")
    assert len(cites) == 1
    assert cites[0].law_no == "5271"
    assert cites[0].to_article_no == "100"


def test_extract_law_article_citations_uses_law_number_context() -> None:
    text = "2577 sayılı Kanunun 7 nci maddesinde belirtilen altmış günlük süre içinde dava açılmalıdır."
    cites = extract_law_article_citations(text, from_article_no="_")
    assert len(cites) == 1
    assert cites[0].law_no == "2577"
    assert cites[0].to_article_no == "7"


def test_extract_law_article_citations_skips_ambiguous_context() -> None:
    # Ne kısaltma ne kanun numarası var — hangi kanunun "158. maddesi" olduğu
    # belirsiz, yanlış eşlemek yerine hiç kayıt üretilmemeli.
    text = "Sanığın eylemi 158 inci maddesi kapsamında değerlendirilmiştir."
    assert extract_law_article_citations(text, from_article_no="_") == []


def test_extract_law_article_citations_skips_when_two_laws_in_window() -> None:
    # Aynı pencerede hem TCK hem CMK geçiyor — belirsiz, atlanmalı.
    text = "TCK ve CMK'nın 100 üncü maddeleri birlikte değerlendirilmiştir."
    assert extract_law_article_citations(text, from_article_no="_") == []
