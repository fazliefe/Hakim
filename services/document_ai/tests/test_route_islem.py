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


def test_confidence_is_lowest_band_when_no_pattern_matches() -> None:
    # Hiçbir _INTENT_RULES needle'ı eşleşmiyor (best == 0) — en düşük banda
    # düşmeli, zayıf-ama-gerçek bir eşleşmeden (ör. tahliye örneği) daha
    # "güvenilir" görünmemeli. Eski kod bunu sabit 0.4'e bağlıyordu.
    route = route_islem("Bu metin hiçbir tanıdık ifade içermiyor xyzzy plugh.")
    assert route.confidence == 0.15


def test_confidence_scales_with_match_strength() -> None:
    weak = route_islem("Dolandırıldım.")  # tek, başlık-dışı needle eşleşmesi
    strong = route_islem(
        "Bankadan dolandırıldım, hesabımdan paramı aldılar. Savcılığa şikayet etmek istiyorum."
    )
    no_match = route_islem("Bu metin hiçbir tanıdık ifade içermiyor xyzzy plugh.")
    assert no_match.confidence < weak.confidence <= strong.confidence
    assert 0.15 <= no_match.confidence < strong.confidence <= 0.95
