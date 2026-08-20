from __future__ import annotations

from graph.citations import citations_to_relations, extract_article_citations


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
