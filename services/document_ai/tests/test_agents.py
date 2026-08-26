from __future__ import annotations

from document_ai.agents import pick_yazisma_action, route_yazisma
from document_ai.classify import classify_document
from document_ai.pipeline import analyze_document


def test_route_yazisma_judgment_is_istinaf() -> None:
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi."
    )
    action, reason = route_yazisma(classify_document(text))
    assert action == "istinaf"
    assert "CMK" in reason


def test_route_yazisma_hukuk_judgment_is_istinaf_hukuk() -> None:
    text = (
        "T.C. ANKARA 4. ASLİYE HUKUK MAHKEMESİ GEREKÇELİ KARAR "
        "Davacının maddi tazminat davasının reddine, HMK hükümleri uyarınca karar verilmiştir."
    )
    action, reason = route_yazisma(classify_document(text))
    assert action == "istinaf_hukuk"
    assert "HMK" in reason


def test_route_yazisma_hukuk_yargitay_karari_is_temyiz_hukuk() -> None:
    text = (
        "Bölge Adliye Mahkemesi'nce davacının istinaf başvurusunun esastan reddine "
        "oy birliği ile karar verildi. HMK'nin 361. maddesi uyarınca Yargıtay ilgili "
        "hukuk dairesine temyiz yolu açıktır."
    )
    action, reason = route_yazisma(classify_document(text))
    assert action == "temyiz_hukuk"
    assert "HMK" in reason


def test_route_yazisma_genelge_is_bilgi() -> None:
    text = "T.C. İÇİŞLERİ BAKANLIĞI\nGENELGE\n2026/12 sayılı genelge ile taşra teşkilatına duyurulur."
    action, reason = route_yazisma(classify_document(text))
    assert action == "bilgi_yazisi"
    assert "bilgi" in reason.lower()


def test_route_yazisma_olur() -> None:
    text = "T.C. BAKANLIK\nOlura arz ederim.\nKonu: Personel görevlendirme"
    action, _ = route_yazisma(classify_document(text))
    assert action == "olur"


def test_route_yazisma_cevap_yazisi() -> None:
    text = "T.C. KURUM\nİlgi yazıya cevaben aşağıdaki bilgiler sunulmuştur."
    action, _ = route_yazisma(classify_document(text))
    assert action == "cevap_yazisi"


def test_analyze_exposes_six_agent_steps() -> None:
    analysis = analyze_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın mahkûmiyetine karar verildi. Tebliğ tarihi: 14.08.2026"
    )
    ids = [item["id"] for item in analysis.agents]
    assert ids == ["okuyucu", "sinif", "mevzuat", "sure", "taslak", "havale"]
    assert analysis.suggested_action == "istinaf"
    assert all("ms" in item and "summary" in item for item in analysis.agents)
    assert analysis.agents[0]["state"] == "done"


def test_kamu_mevzuat_uses_2646_not_skip() -> None:
    analysis = analyze_document(
        "T.C. İÇİŞLERİ BAKANLIĞI\nGENELGE\n2026/12 sayılı genelge ile taşra teşkilatına duyurulur."
    )
    mevzuat = next(item for item in analysis.agents if item["id"] == "mevzuat")
    sure = next(item for item in analysis.agents if item["id"] == "sure")
    taslak = next(item for item in analysis.agents if item["id"] == "taslak")
    assert mevzuat["state"] == "done"
    assert "2646" in mevzuat["summary"]
    assert sure["state"] == "skip"
    assert taslak["state"] == "done"
    assert analysis.chain_status == "solid"


def test_missing_sources_warn_and_propagate() -> None:
    analysis = analyze_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın mahkûmiyetine karar verildi. Tebliğ tarihi: 14.08.2026"
    )
    by_id = {item["id"]: item for item in analysis.agents}
    assert by_id["mevzuat"]["state"] == "warn"
    assert by_id["taslak"]["state"] == "warn"
    assert by_id["taslak"]["depends_on"] == "mevzuat"
    assert "bağlı" in (by_id["taslak"].get("note") or "")
    assert analysis.chain_status == "fragile"


def test_short_text_warns_reader_and_later_steps() -> None:
    analysis = analyze_document("kısa metin")
    by_id = {item["id"]: item for item in analysis.agents}
    assert by_id["okuyucu"]["state"] == "warn"
    assert by_id["sinif"]["depends_on"] == "okuyucu"
    assert analysis.chain_status == "fragile"


def test_belirsiz_complaint_routes_to_sikayet_kalip() -> None:
    text = "Bankadan dolandırıldım, paramı aldılar. Savcılığa şikayet etmek istiyorum."
    action, reason = pick_yazisma_action(classify_document(text), text)
    assert action == "sikayet"
    assert "Şikayet" in reason
    analysis = analyze_document(text)
    assert analysis.suggested_action == "sikayet"
    assert "İLGİLİ BİRİM BELİRLENEMEDİ" not in analysis.draft
    assert "Tür belirsiz hk" not in analysis.draft
    assert "TESPİTLER" not in analysis.draft
    assert "SAVCILI" in analysis.draft.upper()
    assert analysis.petition.get("id") == "sikayet"


def test_reasoning_has_six_hops() -> None:
    analysis = analyze_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın mahkûmiyetine karar verildi. Tebliğ tarihi: 14.08.2026"
    )
    hops = analysis.reasoning["hops"]
    assert [item["n"] for item in hops] == [1, 2, 3, 4, 5, 6]
    assert hops[0]["question"]
    assert hops[1]["answer"]
    assert analysis.reasoning["status"] == "fragile"
    assert "Zincir" in analysis.reasoning["conclusion"]