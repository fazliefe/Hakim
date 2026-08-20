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
