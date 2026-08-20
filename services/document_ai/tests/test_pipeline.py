from __future__ import annotations

from document_ai.pipeline import analyze_document


def test_analyze_computes_istinaf_deadline() -> None:
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR\n"
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\n"
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.document_type == "mahkeme_karari"
    names = {item.name for item in analysis.deadlines}
    assert "İstinaf" in names
    istinaf = next(item for item in analysis.deadlines if item.name == "İstinaf")
    assert istinaf.trigger.isoformat() == "2026-08-14"
    assert istinaf.last_day is not None
    assert "CMK m.273" in istinaf.legal_basis
    assert "taslak" in analysis.draft.lower()


def test_mevzuat_retrieve_uses_full_document_not_type_span() -> None:
    seen: list[str] = []

    def retrieve(query: str):
        seen.append(query)
        return [
            {
                "n": 1,
                "title": "Nitelikli dolandırıcılık",
                "article_no": "158",
                "law_no": "5237",
                "content": "Madde 158",
                "document_id": "law:5237",
            }
        ]

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    assert seen
    assert "nitelikli dolandırıcılık" in seen[0].lower()
    assert analysis.related[0]["article_no"] == "158"


def test_kamu_genelge_skips_law_retrieve() -> None:
    called = {"n": 0}

    def retrieve(query: str):
        called["n"] += 1
        return [{"n": 1, "title": "TCK 158", "content": "nitelikli dolandırıcılık"}]

    text = (
        "T.C. İÇİŞLERİ BAKANLIĞI\n"
        "GENELGE\n"
        "2026/12 sayılı genelge ile taşra teşkilatına duyurulur."
    )
    analysis = analyze_document(text, retrieve=retrieve)
    assert analysis.classification.document_type == "genelge"
    assert called["n"] == 0
    assert analysis.related == []
