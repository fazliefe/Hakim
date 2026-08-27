from __future__ import annotations

import json
from datetime import datetime

import pytest

from document_ai.classify import classify_document
from document_ai.pipeline import (
    GRAPH_NODES,
    Analysis,
    _apply_citation_usage,
    _mevzuat_at,
    analyze_document,
    build_document_trace,
)


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
    # CMK m.273/1: tebliğden itibaren iki hafta (14 gün), 7 gün değil.
    # Ham hesap 2026-08-28'e denk gelir, ancak bu tarih adli tatil
    # penceresinin (20 Temmuz-31 Ağustos, CMK m.331) içinde kaldığından
    # tatilin bitişinden itibaren 3 gün uzar (CMK m.331/4): 31 Ağustos + 3
    # gün = 3 Eylül.
    assert istinaf.last_day.isoformat() == "2026-09-03"
    assert "CMK m.273" in istinaf.legal_basis
    assert "taslak" in analysis.draft.lower()


def test_deadline_has_no_coverage_warning_within_covered_years() -> None:
    """Orta #9: dini tatil takviminin tam kapsadığı ufkun içine düşen normal
    bir hesap, madde bazında hiçbir uyarı taşımamalı — yalnızca /health'teki
    global pil değil, spesifik hesabın kendisi de sessizce doğru olmalı."""
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR\n"
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\n"
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    istinaf = next(item for item in analysis.deadlines if item.name == "İstinaf")
    assert istinaf.calendar_coverage_warning is None


def test_deadline_carries_coverage_warning_beyond_covered_years(monkeypatch) -> None:
    """Aynı hesap, dini tatil takviminin kapsadığı ufuk daraltılınca (ör.
    tablo bakımı gerçekten geride kalsaydı) artık bir uyarı taşımalı — bu,
    global /health pilinden BAĞIMSIZ, spesifik hesabın kendi alanı."""
    monkeypatch.setattr("document_ai.pipeline.LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR", 2020)
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR\n"
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\n"
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    istinaf = next(item for item in analysis.deadlines if item.name == "İstinaf")
    assert istinaf.calendar_coverage_warning is not None
    assert "2020" in istinaf.calendar_coverage_warning
    assert istinaf.last_day.isoformat() in istinaf.calendar_coverage_warning


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


def test_analyze_computes_hukuk_istinaf_and_temyiz_deadline() -> None:
    """HMK m.345 (istinaf) ve m.361 (temyiz): tebliğden itibaren iki hafta
    (14 gün) — CMK'nın ceza süreleriyle aynı rakam ama farklı kanuna
    dayanıyor; hukuk davaları CMK m.273/291'e (ceza) yanlış bağlanmamalı
    (canlı bir BAM/istinaf tazminat kararıyla doğrulandı)."""
    text = (
        "T.C. ANKARA 4. ASLİYE HUKUK MAHKEMESİ\nGEREKÇELİ KARAR\n"
        "Davacının maddi tazminat davasının reddine, HMK hükümleri uyarınca "
        "karar verilmiştir. İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\nTebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.legal_nature == "hukuk"
    assert analysis.classification.stage == "ilk_derece"
    names = {item.name for item in analysis.deadlines}
    assert "İstinaf (hukuk)" in names
    # Temyiz, İLK DERECE hükmünün değil istinaf/BAM kararının tebliğinden
    # işler (HMK m.361/1) — bu aşamada henüz gösterilmemeli, bkz.
    # test_temyiz_hukuk_only_shows_after_istinaf_stage.
    assert "Temyiz (hukuk)" not in names
    istinaf = next(item for item in analysis.deadlines if item.name == "İstinaf (hukuk)")
    assert istinaf.trigger.isoformat() == "2026-08-14"
    # Ham hesap 2026-08-28'e denk gelir, ancak bu tarih adli tatil
    # penceresinin (20 Temmuz-31 Ağustos, HMK m.102) içinde kaldığından
    # tatilin bitişinden itibaren bir hafta (7 gün) uzar (HMK m.104):
    # 31 Ağustos + 7 gün = 7 Eylül.
    assert istinaf.last_day.isoformat() == "2026-09-07"
    assert "HMK m.345" in istinaf.legal_basis
    # CMK'nın ceza kuralları hiç karışmamalı.
    assert "CMK m.273" not in istinaf.legal_basis
    assert not any("CMK" in basis for item in analysis.deadlines for basis in item.legal_basis)


def test_temyiz_hukuk_only_shows_after_istinaf_stage() -> None:
    """Aynı HMK m.361 kuralı, dosya BAM/istinaf aşamasına geçtiğinde
    (bölge adliye mahkemesi kararı) devreye girmeli."""
    text = (
        "T.C. ANKARA BÖLGE ADLİYE MAHKEMESİ 3. HUKUK DAİRESİ\nGEREKÇELİ KARAR\n"
        "Davacının maddi tazminat davasının reddine dair ilk derece hükmüne "
        "karşı yapılan istinaf başvurusunun esastan reddine, HMK hükümleri "
        "uyarınca karar verilmiştir.\n"
        "Karar tarihi: 01.08.2026\nTebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.legal_nature == "hukuk"
    assert analysis.classification.stage == "istinaf"
    names = {item.name for item in analysis.deadlines}
    assert "Temyiz (hukuk)" in names
    assert "İstinaf (hukuk)" not in names


def test_ceza_analysis_carries_legal_interpretation_caveat() -> None:
    """Ceren Özkurt'un bulgusu: sistem güncel kanun metnini uyguluyor gibi
    görünüyor ama lehe kanun uygulaması (TCK m.7), içtihat, zamanaşımı gibi
    ilkeler nedeniyle gerçek sonuç farklılaşabilir — bu sessizce göz ardı
    edilmemeli, açıkça uyarılmalı."""
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR\n"
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\nTebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.legal_caveat is not None
    assert "lehe kanun" in analysis.legal_caveat.lower()
    assert "TCK m.7" in analysis.legal_caveat


def test_hukuk_analysis_carries_shorter_generic_caveat() -> None:
    text = (
        "T.C. ANKARA 4. ASLİYE HUKUK MAHKEMESİ\nGEREKÇELİ KARAR\n"
        "Davacının maddi tazminat davasının reddine, HMK hükümleri uyarınca "
        "karar verilmiştir. İstinaf yolu açıktır.\n"
        "Karar tarihi: 01.08.2026\nTebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.legal_caveat is not None
    assert "çtihat" in analysis.legal_caveat
    # Hukuk davasında "lehe kanun" (TCK m.7'ye özgü bir ceza ilkesi) geçmemeli.
    assert "lehe kanun" not in analysis.legal_caveat.lower()


def test_kamu_evrak_has_no_legal_interpretation_caveat() -> None:
    analysis = analyze_document(
        "T.C. İÇİŞLERİ BAKANLIĞI\nGENELGE\n2026/12 sayılı genelge ile taşra teşkilatına duyurulur."
    )
    assert analysis.legal_caveat is None


def test_analyze_computes_idari_dava_deadline() -> None:
    """İYUK m.7: dava açma süresi altmış gündür (Danıştay/idare mahkemesi)."""
    text = (
        "T.C. ANKARA 3. İDARE MAHKEMESİ\n"
        "Davacı tarafından idari işlemin iptali istemiyle açılan davada karar verilmiştir.\n"
        "Tebliğ tarihi: 01.08.2026"
    )
    analysis = analyze_document(text)
    assert analysis.classification.legal_nature == "idare"
    names = {item.name for item in analysis.deadlines}
    assert "İdari dava açma süresi" in names
    idari = next(item for item in analysis.deadlines if item.name == "İdari dava açma süresi")
    assert idari.trigger.isoformat() == "2026-08-01"
    assert idari.last_day.isoformat() == "2026-09-30"
    assert "İYUK m.7" in idari.legal_basis


def test_mevzuat_retrieve_uses_full_document_not_type_span() -> None:
    seen: list[str] = []

    def retrieve(query: str, at=None):
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


def test_mevzuat_retrieve_runs_for_hukuk_nature() -> None:
    """Regresyon: MEVZUAT_RETRY_ELIGIBLE bir zamanlar yalnızca
    {"ceza","idare","anayasa"} idi — HMK (6100 sayılı Kanun) arşive
    alınmadan önce "hukuk" davalar için bilgi tabanı zaten boş döneceğinden
    dışlanmıştı. HMK artık indekste (bkz. scripts/ingest_law.py --mevzuat-no
    6100); bu test retrieve'in hukuk nitelikli belgeler için de gerçekten
    çağrıldığını doğrular — canlı doğrulandı, HMK ingest sonrası bu olmadan
    hukuk davalarında "İlgili kaynak" hiç görünmüyordu."""
    seen: list[str] = []

    def retrieve(query: str, at=None):
        seen.append(query)
        return [
            {
                "n": 1,
                "title": "İstinaf yoluna başvurulabilen kararlar",
                "article_no": "341",
                "law_no": "6100",
                "document_type": "law",
                "document_id": "law:6100",
                "content": "Madde 341",
            }
        ]

    text = (
        "T.C. ANKARA 4. ASLİYE HUKUK MAHKEMESİ GEREKÇELİ KARAR "
        "Davacının maddi tazminat davasının reddine, HMK hükümleri uyarınca karar verildi. "
        "İstinaf yolu açıktır. Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    assert seen
    assert analysis.classification.legal_nature == "hukuk"
    ids = {item.get("document_id") for item in analysis.related}
    assert "law:6100" in ids


def test_mevzuat_second_query_fetches_topic_court() -> None:
    seen: list[str] = []

    def retrieve(query: str, at=None):
        seen.append(query)
        folded = query.casefold()
        if "yargıtay" in folded or "yargitay" in folded:
            return [
                {
                    "n": 2,
                    "document_type": "court_decision",
                    "court": "Yargıtay 11. Ceza Dairesi",
                    "esas_no": "2018/334",
                    "karar_no": "2018/891",
                    "document_id": "decision:yargitay:2018:2018/334:2018/891",
                    "content": "Nitelikli dolandırıcılık suçundan bozma.",
                }
            ]
        return [
            {
                "n": 1,
                "title": "Nitelikli dolandırıcılık",
                "article_no": "158",
                "law_no": "5237",
                "document_type": "law",
                "document_id": "law:5237",
                "content": "Madde 158",
            }
        ]

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    assert any("yargıtay" in item.casefold() or "yargitay" in item.casefold() for item in seen)
    ids = {item.get("document_id") for item in analysis.related}
    assert "law:5237" in ids
    assert "decision:yargitay:2018:2018/334:2018/891" in ids


def test_mevzuat_search_passes_evrak_date_as_temporal_filter() -> None:
    """A2: mevzuat araması, evrakın tebliğ/karar tarihine göre yürürlükte olan
    metni istemeli — 'at' parametresi bugünün tarihi değil, evrakın kendi
    tarihi olmalı (bkz. retrieval.mapping.corpus_filters)."""
    seen_at: list[object] = []

    def retrieve(query: str, at=None):
        seen_at.append(at)
        return []

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analyze_document(text, retrieve=retrieve)
    # İlk deneme + boş dönünce geniş sorguyla tekrar (+ konu emsal araması).
    # Hepsi evrakın kendi tebliğ tarihini kullanmalı.
    assert seen_at
    assert all(item == datetime(2026, 8, 14) for item in seen_at)
    assert len(seen_at) >= 2


def test_mevzuat_at_prefers_teblig_falls_back_to_karar() -> None:
    from datetime import date

    assert _mevzuat_at({"teblig": date(2026, 8, 14), "karar": date(2026, 8, 1)}) == datetime(2026, 8, 14)
    assert _mevzuat_at({"karar": date(2026, 8, 1)}) == datetime(2026, 8, 1)
    assert _mevzuat_at({}) is None


def test_mevzuat_retries_with_broader_query_when_first_pass_empty() -> None:
    """Görev 6: dar sorgu boş dönerse graf `mevzuat` node'una bir kez daha
    (geniş sorguyla) uğrar — LangGraph conditional edge, sadece prompt değil."""
    seen: list[str] = []

    def retrieve(query: str, at=None):
        seen.append(query)
        if len(seen) == 1:
            return []
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

    # 500 karakter sınırını aşacak kadar uzun; geniş sorgu (1500) daha fazlasını
    # yakalar, bu yüzden iki sorgu birbirinden farklı olmalı.
    dolgu = " Olayın ayrıntıları dosya içeriğinde yer almaktadır." * 12
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi." + dolgu + " "
        "Tebliğ tarihi: 14.08.2026"
    )
    assert len(text) > 500
    analysis = analyze_document(text, retrieve=retrieve)
    assert len(seen) >= 2
    assert seen[1] != seen[0]
    assert len(seen[1]) > len(seen[0])
    assert analysis.related and analysis.related[0]["article_no"] == "158"
    mevzuat_agents = [item for item in analysis.agents if item["id"] == "mevzuat"]
    assert len(mevzuat_agents) == 1
    assert "geniş sorguyla" in (mevzuat_agents[0]["note"] or "").lower()
    edge_pairs = [(item["source"], item["target"]) for item in analysis.trace_edges]
    assert ("mevzuat", "mevzuat") in edge_pairs  # retry gerçekten oldu, grafikte görünmeli


def test_mevzuat_gives_up_after_one_retry() -> None:
    """İki denemede de bulunamazsa zincir kırılmadan devam eder."""
    seen: list[str] = []

    def retrieve(query: str, at=None):
        seen.append(query)
        return []

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    assert len(seen) >= 2
    assert analysis.related == []
    mevzuat_agents = [item for item in analysis.agents if item["id"] == "mevzuat"]
    assert len(mevzuat_agents) == 1
    assert mevzuat_agents[0]["state"] == "warn"
    assert "taslak" in analysis.draft.lower()


def test_analyze_document_builds_evidence_trace() -> None:
    """Madde 1: üretilen taslak/havale kararının hangi maddeye dayandığı
    izlenebilmeli — trace_nodes/trace_edges gerçek claim→evidence bağını taşır."""

    def retrieve(query: str, at=None):
        return [
            {
                "n": 1,
                "chunk_id": "law:5237:article:158:v1",
                "title": "Nitelikli dolandırıcılık",
                "article_no": "158",
                "law_no": "5237",
                "content": "Madde 158",
                "document_id": "law:5237",
                "rrf_rank": 1,
                "retrievers": ["bm25", "semantic"],
                "graph_neighbors": [{"id": "law:5237:article:157:v1", "article_no": "157"}],
                "used_in_answer": True,
            }
        ]

    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    analysis = analyze_document(text, retrieve=retrieve)
    node_ids = [item["id"] for item in analysis.trace_nodes]
    for node_id in GRAPH_NODES:
        assert node_id in node_ids
    chunk_node = next(item for item in analysis.trace_nodes if item["id"] == "law:5237:article:158:v1")
    assert chunk_node["kind"] == "chunk"
    assert chunk_node["label"] == "TCK 158"
    assert chunk_node["meta"]["graph_neighbors"]

    edge_pairs = [(item["source"], item["target"]) for item in analysis.trace_edges]
    assert ("mevzuat", "law:5237:article:158:v1") in edge_pairs
    assert ("law:5237:article:158:v1", "taslak") in edge_pairs
    # İlk sorguda bulunduğu için retry hiç olmadı — self-loop grafikte görünmemeli
    # (görünürse kullanıcıya olmayan bir yeniden-deneme anlatılmış olur).
    assert ("mevzuat", "mevzuat") not in edge_pairs


def test_apply_citation_usage_downgrades_unused_related_items() -> None:
    """Kaynak grafiği dürüstlüğü: taslak yalnızca [1]'i kullandıysa, [2] ve
    [3] "aday havuzunda kaldı" demektir — used_in_answer=True kalmamalı."""
    classification = classify_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR mahkûmiyetine karar verildi."
    )
    analysis = Analysis(
        classification=classification,
        dates={},
        findings=[],
        deadlines=[],
        stages=[],
        related=[
            {"n": 1, "chunk_id": "a", "used_in_answer": True},
            {"n": 2, "chunk_id": "b", "used_in_answer": True},
            {"n": 3, "chunk_id": "c", "used_in_answer": True},
        ],
    )
    analysis.petition = {"cited_ns": [1]}
    _apply_citation_usage(analysis)
    used = {item["n"]: item["used_in_answer"] for item in analysis.related}
    assert used == {1: True, 2: False, 3: False}


def test_apply_citation_usage_noop_without_cited_ns_signal() -> None:
    """`petition` bu bilgiyi taşımıyorsa (örn. belge-dışı islem fallback'i)
    mevcut used_in_answer değerine dokunma — yanlış bilgiyle üzerine yazma."""
    classification = classify_document("Genel bir metin.")
    analysis = Analysis(
        classification=classification,
        dates={},
        findings=[],
        deadlines=[],
        stages=[],
        related=[{"n": 1, "chunk_id": "a", "used_in_answer": True}],
    )
    analysis.petition = {"id": "islem", "title": "İşlem"}
    _apply_citation_usage(analysis)
    assert analysis.related[0]["used_in_answer"] is True


def test_build_document_trace_skips_chunks_without_mevzuat_step() -> None:
    """Kamu evrakında (mevzuat retrieve edilmez) sahte madde node'u üretilmemeli."""
    agents = [{"id": "okuyucu", "title": "Okuyucu", "state": "done", "ms": 1}]
    related = [{"chunk_id": "law:5237:article:1:v1", "article_no": "1", "law_no": "5237"}]
    nodes, edges = build_document_trace(agents, related)
    assert [item["id"] for item in nodes] == ["okuyucu"]
    assert not any(item["target"] == "law:5237:article:1:v1" for item in edges)


def test_kamu_genelge_skips_law_retrieve() -> None:
    called = {"n": 0}

    def retrieve(query: str, at=None):
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
