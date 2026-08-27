from __future__ import annotations

import json


def test_parse_rejects_identifiable_face() -> None:
    from document_ai.privacy.image_kvkk import parse_kvkk_screen
    decision = parse_kvkk_screen(
        json.dumps(
            {
                "kvkk_risk": True,
                "flags": {"identifiable_face": True},
                "reasons": ["Görüntüde tanınabilir yüz var."],
                "caption": "Kişi fotoğrafı",
                "scene": "Bir yüz görünüyor.",
            },
            ensure_ascii=False,
        )
    )
    assert decision.accepted is False
    assert decision.caption == ""
    assert decision.scene == ""
    assert decision.reasons


def test_parse_rejects_identity_document_even_if_risk_flag_false() -> None:
    from document_ai.privacy.image_kvkk import parse_kvkk_screen
    decision = parse_kvkk_screen(
        json.dumps(
            {
                "kvkk_risk": False,
                "flags": {"identity_document": True, "identifiable_face": False},
                "reasons": [],
                "caption": "Kimlik kartı",
                "scene": "Nüfus cüzdanı.",
            },
            ensure_ascii=False,
        )
    )
    assert decision.accepted is False
    assert decision.caption == ""


def test_parse_accepts_scene_without_personal_data() -> None:
    from document_ai.privacy.image_kvkk import parse_kvkk_screen
    decision = parse_kvkk_screen(
        json.dumps(
            {
                "kvkk_risk": False,
                "flags": {
                    "identifiable_face": False,
                    "identity_document": False,
                    "tckn_visible": False,
                    "iban_or_account": False,
                    "phone_or_email": False,
                    "child_or_minor": False,
                    "health_data": False,
                },
                "reasons": [],
                "caption": "Kaza mahallindeki hasarlı araç görüntüsü",
                "scene": "Ön tamponu ezilmiş bir binek araç kaldırım kenarında durmaktadır.",
            },
            ensure_ascii=False,
        )
    )
    assert decision.accepted is True
    assert "araç" in decision.caption.lower()
    assert "tampon" in decision.scene.lower()


def test_parse_rejects_caption_that_contains_tckn() -> None:
    from document_ai.privacy.image_kvkk import parse_kvkk_screen
    decision = parse_kvkk_screen(
        json.dumps(
            {
                "kvkk_risk": False,
                "flags": {},
                "reasons": [],
                "caption": "Dekont TCKN 10000000146",
                "scene": "Banka dekontu.",
            },
            ensure_ascii=False,
        )
    )
    assert decision.accepted is False
    assert decision.caption == ""


def test_parse_rejects_invalid_json_closed() -> None:
    from document_ai.privacy.image_kvkk import parse_kvkk_screen
    decision = parse_kvkk_screen("bu json değil")
    assert decision.accepted is False
    assert decision.caption == ""
    assert decision.reasons
