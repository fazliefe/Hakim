from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from hakim_api.main import app

ONE_PX_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def test_islem_fotograf_rejects_kvkk_photo(monkeypatch) -> None:
    monkeypatch.setattr(
        "document_ai.privacy.image_kvkk.screen_islem_photo",
        lambda data, filename="ek.jpg": SimpleNamespace(
            accepted=False,
            reasons=["Görüntüde tanınabilir yüz var."],
            caption="",
            scene="",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/islem/fotograf",
        files={"file": ("yuz.png", ONE_PX_PNG, "image/png")},
    )
    assert response.status_code == 422
    detail = str(response.json().get("detail") or "").lower()
    assert "kvkk" in detail


def test_islem_fotograf_returns_caption_when_safe(monkeypatch) -> None:
    monkeypatch.setattr(
        "document_ai.privacy.image_kvkk.screen_islem_photo",
        lambda data, filename="ek.jpg": SimpleNamespace(
            accepted=True,
            reasons=[],
            caption="Hasarlı araç görüntüsü",
            scene="Ön tamponu ezilmiş bir binek araç görünmektedir.",
        ),
    )
    client = TestClient(app)
    response = client.post(
        "/v1/islem/fotograf",
        files={"file": ("kaza.png", ONE_PX_PNG, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert "araç" in body["caption"].lower()
    assert body["scene"]


def test_islem_draft_includes_visual_ek() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/islem",
        json={
            "text": "Bankadan dolandırıldım, paramı aldılar. Savcılığa şikayet etmek istiyorum.",
            "visual_eks": [
                {
                    "caption": "ATM önü güvenlik kamerası karesi",
                    "scene": "ATM önünde bir kişi durmaktadır; yüz ayırt edilememektedir.",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    ekler = (body.get("petition") or {}).get("ekler") or []
    assert any("ATM" in item for item in ekler)
    draft = (body.get("draft") or "").lower()
    olay = ""
    for section in (body.get("petition") or {}).get("sections") or []:
        if section.get("id") == "olay":
            olay = (section.get("text") or "").lower()
    blob = f"{draft} {olay}"
    assert "ekte" in blob or "ekler" in blob
    assert "EKLER:" in (body.get("draft") or "")
