from __future__ import annotations

from document_ai.route_islem import route_islem


def test_routes_fraud_story_to_sikayet() -> None:
    text = "Bankadan dolandırıldım, hesabımdan paramı aldılar. Savcılığa şikayet etmek istiyorum."
    route = route_islem(text)
    assert route.action == "sikayet"
    assert "Şikayet" in route.title


def test_routes_appeal_story_to_istinaf() -> None:
    text = "Ağır ceza mahkemesi mahkûmiyet kararı tebliğ edildi. İstinaf etmek istiyorum."
    assert route_islem(text).action == "istinaf"


def test_routes_detention_to_tahliye() -> None:
    text = "Tutukluyum, tahliye talebinde bulunmak istiyorum."
    assert route_islem(text).action == "tahliye"


def test_routes_idari_iptal() -> None:
    text = "Valiliğin idari işlemine karşı iptal davası açmak istiyorum, idare mahkemesine."
    assert route_islem(text).action == "idari_dava"


def test_routes_natural_language_traps() -> None:
    assert route_islem("Mahkeme beni mahkum etti, üst mahkemeye gitmek istiyorum.").action == "istinaf"
    assert route_islem("Cezaevindeyim, evime dönmek istiyorum.").action == "tahliye"
    assert route_islem("Komşum bana hakaret etti, savcıya gitmek istiyorum.").action == "sikayet"


def test_bam_onama_plus_temyiz_request_is_temyiz() -> None:
    text = (
        "T.C. ANKARA BÖLGE ADLİYE MAHKEMESİ 2. CEZA DAİRESİ KARAR "
        "İlk derece mahkemesinin nitelikli dolandırıcılıktan kurduğu mahkûmiyet hükmü "
        "istinaf incelemesi sonucunda onanmıştır. "
        "Hükmün hukuka aykırılığı nedeniyle temyiz yoluna başvurmak istiyorum."
    )
    route = route_islem(text)
    assert route.action == "temyiz"
    assert "Temyiz" in route.title


def test_explicit_istinaf_still_wins_without_temyiz() -> None:
    assert route_islem("Ağır ceza mahkûmiyetini istinaf etmek istiyorum.").action == "istinaf"


def test_routes_hukuk_samples_to_their_own_templates() -> None:
    assert route_islem("Hukuk mahkemesinde cevap süresi uzatım talebi dilekçesi yazmak istiyorum.").action == "sure_uzatim"
    assert route_islem("İlamsız icra takibine borca itiraz dilekçesi vermek istiyorum, icra müdürlüğüne.").action == "icra_borca_itiraz"
    assert route_islem("Kiracıyı ihtiyaç sebebiyle tahliye etmek istiyorum, sulh hukuk mahkemesine.").action == "ihtiyac_tahliye"
    assert route_islem("Karşı tarafın temyizine cevap dilekçesi yazmak istiyorum.").action == "temyiz_cevap"
    assert route_islem("Karşı tarafın temyizine cevap ve karşı temyiz dilekçesi yazmak istiyorum.").action == "temyiz_cevap"
    assert route_islem("Tutukluyum. Tahliye talebinde bulunmak istiyorum.").action == "tahliye"
