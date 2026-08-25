from fastapi.testclient import TestClient

from hakim_api.main import DEFAULT_CORS_ORIGINS, _cors_origins, app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["api"] == "ok"
    assert body["status"] in {"ok", "kapalı"}
    assert {"api", "elasticsearch", "neo4j", "postgres", "yazim"} <= set(body["checks"])
    # Dini bayram takvimi güncelliği (bkz. deadline/engine.py) — veri
    # tazeliği kontrolü, "required" değil (bkz. main.py::health), bu yüzden
    # tüm API'yi "kapalı" yapmadan bilgilendirici kalmalı. Bu assert KASITLI
    # olarak zamana bağlı: LAST_FULLY_COVERED_RELIGIOUS_HOLIDAY_YEAR
    # güncellenmezse bu test bir gün gerçekten kırmızıya döner — bu, tam da
    # health-check'in amaçladığı erken uyarı.
    assert body["checks"]["takvim"] == "ok"


def test_durum_labels_deadline_calendar_pill() -> None:
    client = TestClient(app)
    response = client.get("/v1/durum")
    assert response.status_code == 200
    body = response.json()
    assert body["etiketler"]["takvim"] == "Süre takvimi"


def test_cors_origins_default_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_CORS_ORIGINS", raising=False)
    assert _cors_origins() == DEFAULT_CORS_ORIGINS


def test_cors_origins_reads_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_CORS_ORIGINS", "http://192.168.1.50:3000, http://localhost:3000")
    assert _cors_origins() == ["http://192.168.1.50:3000", "http://localhost:3000"]


def test_cors_origins_falls_back_when_env_is_blank(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_CORS_ORIGINS", "   ")
    assert _cors_origins() == DEFAULT_CORS_ORIGINS


def test_schema_version() -> None:
    client = TestClient(app)
    response = client.get("/v1/schema")
    assert response.status_code == 200
    assert response.json()["legal_data_model"] == "1.0.0"


def test_kaynaklar_lists_official_catalog() -> None:
    client = TestClient(app)
    response = client.get("/v1/kaynaklar")
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["official"]}
    assert "source:rekabet.gov.tr" in ids
    assert "source:emsal.uyap.gov.tr" in ids
    assert body["huggingface"]


def test_belgeler_lists_petition_templates() -> None:
    client = TestClient(app)
    response = client.get("/v1/belgeler")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["documents"]}
    assert "sikayet" in ids
    assert "istinaf" in ids
    assert "idari_dava" in ids
    assert "ust_yazi" in ids
    assert "bilgi_yazisi" in ids
    assert "olur" in ids


def test_kamu_sablon_exposes_block_order() -> None:
    client = TestClient(app)
    response = client.get("/v1/kamu/sablon")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "2646-ek"
    assert "ust_yazi" in body["varyantlar"]
    assert body["varyantlar"]["ust_yazi"]["blok_sirasi"][0] == "baslik"
    assert body["kaynaklar"]
    urls = {item["url"] for item in body["kaynaklar"]}
    assert any("2646" in url for url in urls)
    assert "ust_yazi" in body["ornekler"]
    assert "Sayı" in body["ornekler"]["ust_yazi"]
    assert "İLGİLİ BİRİM" in body["ornekler"]["ust_yazi"]


def test_islem_routes_complaint_without_action() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/islem",
        json={"text": "Bankadan dolandırıldım, paramı aldılar. Savcılığa şikayet etmek istiyorum."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "sikayet"
    assert body["belge"] == "sikayet"
    assert "Şikayet" in (body.get("route_reason") or "")
    assert body["draft"]
    assert "SAVCILI" in body["draft"].upper()
    assert "İLGİLİ BİRİM BELİRLENEMEDİ" not in body["draft"]
    assert body["petition"]["id"] == "sikayet"
    assert body["petition"]["layout"] == "savcilik"


def test_islem_incomplete_text_lists_gaps() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/islem",
        json={"text": "paramı aldılar şikayet etmek istiyorum"},
    )
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body.get("gaps") or []}
    assert "sikayetci" in ids
    assert "olay_tarihi" in ids
    assert body["draft"]
    assert "«[şikayetçi" in body["draft"]
    labels = [section.get("label", "") for section in (body.get("petition") or {}).get("sections") or []]
    assert not any("Eksik hususlar" in label for label in labels)
    assert "EKSİK HUSUSLAR" not in (body.get("draft") or "")


def test_islem_anla_guesses_format_without_writing() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/islem/anla",
        json={"text": "Tutukluyum, tahliye talebinde bulunmak istiyorum."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "tahliye"
    assert "Tahliye" in body["title"]
    assert body["confidence"] > 0.4
    assert "draft" not in body


def test_islem_accepts_sikayet_template() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/islem",
        json={
            "action": "sikayet",
            "text": (
                "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
                "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
                "Tebliğ tarihi: 14.08.2026"
            ),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "sikayet"
    assert body["belge"] == "sikayet"
    assert body["draft"]


def test_evrak_complaint_uses_sikayet_not_generic_draft() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak",
        json={"text": "Bankadan dolandırıldım, paramı aldılar. Savcılığa şikayet etmek istiyorum."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggested_action"] == "sikayet"
    assert body["belge"] == "sikayet"
    assert "SAVCILI" in body["draft"].upper()
    assert "İLGİLİ BİRİM BELİRLENEMEDİ" not in body["draft"]
    assert "Tür belirsiz hk" not in body["draft"]
    assert "TESPİTLER" not in body["draft"]
    assert body["petition"]["id"] == "sikayet"


def test_evrak_classifies_judgment() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak",
        json={
            "text": (
                "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
                "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
                "Tebliğ tarihi: 14.08.2026"
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["document_type"] == "mahkeme_karari"
    assert body["draft"]
    assert body["deadlines"]


def test_evrak_dosya_reads_txt() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak/dosya",
        files={
            "file": (
                "gerekceli_karar.txt",
                (
                    "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
                    "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
                    "Tebliğ tarihi: 14.08.2026"
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_kind"] == "txt"
    assert body["source_filename"] == "gerekceli_karar.txt"
    assert body["classification"]["document_type"] == "mahkeme_karari"
    assert body["text"]
    assert [item["id"] for item in body["agents"]] == [
        "okuyucu",
        "sinif",
        "mevzuat",
        "sure",
        "taslak",
        "havale",
    ]


def test_senaryo_runs_judgment_to_istinaf() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/senaryo",
        json={
            "text": (
                "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
                "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
                "Tebliğ tarihi: 14.08.2026"
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["senaryo"] is True
    assert body["action"] == "istinaf"
    assert body["belge"] == "istinaf"
    assert body["havale"]["unit"]
    assert body["draft"]
    assert body["agents"][0]["id"] == "okuyucu"
    assert body["agents"][-1]["id"] == "havale"
    assert len(body["reasoning"]["hops"]) == 6
    assert body["reasoning"]["hops"][0]["question"]
