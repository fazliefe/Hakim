from __future__ import annotations

import json

import pytest

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


def test_administrative_judgment_does_not_borrow_criminal_deadline() -> None:
    # "istinaf" kelimesi idare kararında da geçer; CMK m.273'e (7 gün) sızmamalı,
    # İYUK m.45'e (30 gün, idari istinaf) bağlanmalı.
    text = (
        "T.C. ANKARA İDARE MAHKEMESİ GEREKÇELİ KARAR\n"
        "İptal davası hakkında davanın reddine, hükmün istinaf yolu açık olmak üzere "
        "karar verildi.\n"
        "Karar tarihi: 01.08.2026\n"
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.document_type == "mahkeme_karari"
    assert analysis.classification.legal_nature == "idare"
    assert "istinaf" not in analysis.classification.remedies
    assert "istinaf_idari" in analysis.classification.remedies
    assert "idari_dava" in analysis.classification.remedies

    names = {item.name for item in analysis.deadlines}
    assert "İstinaf" not in names
    assert "İdari istinaf" in names
    assert "İdari dava açma süresi" in names

    idari_istinaf = next(item for item in analysis.deadlines if item.name == "İdari istinaf")
    assert idari_istinaf.trigger.isoformat() == "2026-08-14"
    assert idari_istinaf.last_day is not None
    assert "İYUK m.45" in idari_istinaf.legal_basis

    idari_dava = next(item for item in analysis.deadlines if item.name == "İdari dava açma süresi")
    assert "İYUK m.7" in idari_dava.legal_basis


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


def test_confident_classification_never_calls_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    # resolve_writer() taslak (yazım) adımında allow_ollama=... ile zaten çağrılır;
    # burada sadece step_sinif'in EK, argümansız bir çağrı yapmadığını doğruluyoruz.
    calls: list[tuple] = []

    def tracking_resolve_writer(*args: object, **kwargs: object):
        calls.append((args, kwargs))
        return None

    monkeypatch.setattr("llm.writer.resolve_writer", tracking_resolve_writer)
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.document_type == "mahkeme_karari"
    sinif_style_calls = [c for c in calls if c == ((), {})]
    assert sinif_style_calls == []


def test_belirsiz_classification_uses_llm_assist_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve_writer(*, allow_ollama: bool = True):
        def chat_fn(messages: list[dict[str, str]]) -> str:
            return json.dumps(
                {
                    "document_type": "ust_yazi",
                    "legal_nature": "kamu",
                    "evidence": "kurumumuza ulaşmış olup incelenmesi",
                }
            )

        return chat_fn

    monkeypatch.setattr("llm.writer.resolve_writer", fake_resolve_writer)
    monkeypatch.setattr("llm.writer.writer_name", lambda **_: "sahte-llm")

    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    analysis = analyze_document(text)
    assert analysis.classification.document_type == "ust_yazi"
    assert analysis.classification.confidence == 0.6

    sinif_step = next(item for item in analysis.agents if item["id"] == "sinif")
    assert sinif_step["state"] == "done"  # LLM doğrulaması sonrası artık "warn" değil.
    assert "LLM ile doğrulandı" in (sinif_step["note"] or "")
    assert "sahte-llm" in sinif_step["note"]
