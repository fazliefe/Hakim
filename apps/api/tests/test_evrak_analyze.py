from fastapi.testclient import TestClient

from hakim_api.main import app
from hakim_legal_schema.document import ExtractedField, StructuredDocument


def test_evrak_analyze_returns_structured_document(monkeypatch) -> None:
    def fake_analyze(filename: str, data: bytes) -> StructuredDocument:
        return StructuredDocument(
            document_id="doc-001",
            document_type="tebligat",
            document_type_confidence=0.96,
            filename=filename,
            fields=[
                ExtractedField(
                    name="notification_date",
                    value="14.08.2026",
                    bbox=[0.62, 0.41, 0.82, 0.47],
                    confidence=0.91,
                    source="vlm",
                )
            ],
        )

    monkeypatch.setattr("document_ai.vision.analyzer.analyze_bytes", fake_analyze)
    client = TestClient(app)
    response = client.post(
        "/v1/evrak/analyze",
        files={"file": ("tebligat.jpg", b"\xff\xd8\xff fake-jpeg", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == "doc-001"
    assert body["document_type"] == "tebligat"
    assert body["fields"][0]["name"] == "notification_date"
    assert body["fields"][0]["bbox"] == [0.62, 0.41, 0.82, 0.47]
    assert "classification" not in body
    assert "draft" not in body


def test_evrak_analyze_rejects_empty_file() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak/analyze",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 422


def test_evrak_analyze_rejects_pdf() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak/analyze",
        files={"file": ("scan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert response.status_code == 422
    assert "fotoğraf" in response.json()["detail"].lower()


def test_evrak_bundle_empty_ok() -> None:
    client = TestClient(app)
    response = client.post("/v1/evrak/bundle", json={"documents": []})
    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == []
    assert body["conflicts"] == []
    assert "bundle_id" in body


def test_evrak_bundle_flags_case_no_conflict() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/evrak/bundle",
        json={
            "documents": [
                {
                    "document_id": "a",
                    "filename": "karar.jpg",
                    "fields": [
                        {
                            "name": "case_no",
                            "value": "2024/12",
                            "bbox": [0.1, 0.1, 0.3, 0.2],
                            "confidence": 0.9,
                        }
                    ],
                },
                {
                    "document_id": "b",
                    "filename": "tebligat.jpg",
                    "fields": [
                        {
                            "name": "case_no",
                            "value": "2024/13",
                            "bbox": [0.1, 0.1, 0.3, 0.2],
                            "confidence": 0.9,
                        }
                    ],
                },
            ]
        },
    )
    assert response.status_code == 200
    conflicts = response.json()["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "case_no"


def test_evrak_redact_masks_tckn() -> None:
    client = TestClient(app)
    response = client.post("/v1/evrak/redact", json={"text": "Kimlik 10000000146"})
    assert response.status_code == 200
    body = response.json()
    assert "10000000146" not in body["redacted"]
    assert body["count"] == 1
    assert "tckn" in body["kinds"]
