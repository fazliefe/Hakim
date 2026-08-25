from __future__ import annotations

from datetime import date

from deadline.engine import DeadlineComputation
from hakim_legal_schema.enums import CalendarType, DurationUnit

from document_ai.answers import (
    format_havale,
    format_mevzuat_2646,
    format_mevzuat_empty,
    format_mevzuat_hits,
    format_okuyucu,
    format_sinif,
    format_sure,
    format_taslak,
)
from document_ai.classify import classify_document
from document_ai.pipeline import analyze_document


def test_okuyucu_answer_quotes_excerpt() -> None:
    summary, answer = format_okuyucu("T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR Sanık mahkûm edildi.")
    assert "karakter okundu" in summary
    assert "Alıntı:" in answer
    assert "GEREKÇELİ KARAR" in answer
    assert "«" in answer


def test_sinif_answer_states_type_and_missing() -> None:
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    c = classify_document(text)
    summary, answer = format_sinif(c, {"teblig": "2026-08-14"}, ["Karar tarihi"])
    assert "Mahkeme kararı" in summary
    assert "Tür: Mahkeme kararı" in answer
    assert "Nitelik:" in answer
    assert "Eksik:" in answer
    assert "Karar tarihi" in answer


def test_mevzuat_answer_cites_article() -> None:
    summary, answer = format_mevzuat_hits(
        [
            {
                "n": 1,
                "law_no": "5237",
                "article_no": "158",
                "title": "Nitelikli dolandırıcılık",
                "content": "Madde 158- (1) Dolandırıcılık suçunun;",
            }
        ]
    )
    assert summary == "1 kaynak"
    assert "[1] TCK m.158" in answer
    assert "Nitelikli dolandırıcılık" in answer
    assert "Madde 158" in answer


def test_mevzuat_2646_and_empty_have_own_shape() -> None:
    _, yonetmelik = format_mevzuat_2646()
    assert "2646" in yonetmelik
    assert "m.10–20" in yonetmelik or "m.10-20" in yonetmelik
    _, empty = format_mevzuat_empty()
    assert "uydurma" in empty.lower()


def test_sure_answer_names_last_day() -> None:
    item = DeadlineComputation(
        rule_id="deadline:istinaf:cmk273",
        name="İstinaf",
        trigger=date(2026, 8, 14),
        duration=7,
        unit=DurationUnit.DAY,
        calendar=CalendarType.CRIMINAL,
        last_day=date(2026, 8, 21),
        legal_basis=("CMK m.273", "cmk:273"),
        missing=None,
    )
    summary, answer = format_sure([item])
    assert "1 süre" in summary
    assert "İstinaf" in answer
    assert "21.08.2026" in answer
    assert "CMK m.273" in answer


def test_taslak_and_havale_answers() -> None:
    _, taslak = format_taslak("istinaf", "İlk derece ceza hükmü → istinaf dilekçesi (CMK m.273).")
    assert "istinaf dilekçesi" in taslak.lower()
    assert "Taslaklar" in taslak
    _, havale = format_havale("İlgili Cumhuriyet savcılığı / ceza mahkemesi", "CMK m.273.")
    assert "Havale birimi:" in havale
    assert "UYAP" in havale
    assert "gönderim yoktur" in havale.lower()


def test_pipeline_hops_use_stage_answers_not_only_summaries() -> None:
    def retrieve(query: str, at=None):
        return [
            {
                "n": 1,
                "title": "Nitelikli dolandırıcılık",
                "article_no": "158",
                "law_no": "5237",
                "content": "Madde 158- (1) Dolandırıcılık suçunun;",
                "document_id": "law:5237",
            }
        ]

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    hops = {item["id"]: item for item in analysis.reasoning["hops"]}
    by = {item["id"]: item for item in analysis.agents}
    assert "Alıntı:" in hops["okuyucu"]["answer"]
    assert "Tür: Mahkeme kararı" in hops["sinif"]["answer"]
    assert "TCK m.158" in hops["mevzuat"]["answer"]
    assert "İstinaf" in hops["sure"]["answer"]
    assert "istinaf dilekçesi" in hops["taslak"]["answer"].lower()
    assert "Havale birimi:" in hops["havale"]["answer"]
    assert by["okuyucu"]["summary"] != hops["okuyucu"]["answer"]
    assert by["mevzuat"]["summary"] == "1 kaynak"


def test_kamu_hops_use_2646_and_skip_deadline_prose() -> None:
    analysis = analyze_document(
        "T.C. İÇİŞLERİ BAKANLIĞI\nGENELGE\n2026/12 sayılı genelge ile taşra teşkilatına duyurulur."
    )
    hops = {item["id"]: item for item in analysis.reasoning["hops"]}
    assert "2646" in hops["mevzuat"]["answer"]
    assert "süre" in hops["sure"]["answer"].lower()
    assert "bilgi yazısı" in hops["taslak"]["answer"].lower()
