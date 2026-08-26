from __future__ import annotations

import io

from PIL import Image
from hakim_legal_schema.document import ExtractedField, QualityReport, QualityStatus


def _png(width: int = 800, height: int = 1000) -> bytes:
    image = Image.new("RGB", (width, height), (220, 220, 220))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def test_analyze_bytes_skips_vlm_when_unusable(monkeypatch) -> None:
    from document_ai.vision import analyzer

    def boom(*_args, **_kwargs):
        raise AssertionError("unusable image must not call VLM")

    monkeypatch.setattr(analyzer, "extract_from_images", boom)
    tiny = Image.new("RGB", (1, 1), (0, 0, 0))
    buf = io.BytesIO()
    tiny.save(buf, format="PNG")
    doc = analyzer.analyze_bytes("blur.jpg", buf.getvalue())
    assert doc.quality.status == QualityStatus.UNUSABLE
    assert doc.fields == []
    assert any(item.code == "unusable" for item in doc.warnings)


def test_analyze_bytes_returns_structured_fields(monkeypatch) -> None:
    from document_ai.vision import analyzer

    monkeypatch.setattr(
        analyzer,
        "assess_image",
        lambda _data, page=1: QualityReport(quality_score=0.92, status=QualityStatus.GOOD),
    )
    monkeypatch.setattr(analyzer, "transcribe_images", lambda _images: "")
    monkeypatch.setattr(
        analyzer,
        "extract_from_images",
        lambda _images, page_offset=0: {
            "document_type": "tebligat",
            "document_type_confidence": 0.96,
            "fields": [
                ExtractedField(
                    name="notification_date",
                    value="14.08.2026",
                    bbox=[0.62, 0.41, 0.82, 0.47],
                    confidence=0.91,
                    source="vlm",
                )
            ],
            "sections": [],
            "full_text": "Tebliğ tarihi 14.08.2026",
            "raw": "{}",
        },
    )
    monkeypatch.setattr(analyzer, "verify_review_fields", lambda _blob, fields: fields)
    doc = analyzer.analyze_bytes("tebligat.jpg", _png())
    assert doc.document_type == "tebligat"
    assert doc.fields[0].value == "14.08.2026"
    assert doc.raw_text == "Tebliğ tarihi 14.08.2026"
    assert doc.visual_evidence[0].field_name == "notification_date"
    payload = doc.model_dump()
    assert "verdict" not in payload
    assert payload["fields"][0]["bbox"] == [0.62, 0.41, 0.82, 0.47]
    assert doc.pages[0].preview_jpeg
    missing = {item.field for item in doc.warnings if item.code == "missing_field"}
    assert "case_no" in missing
    assert "recipient" in missing


def test_analyze_bytes_prefers_full_page_transcript(monkeypatch) -> None:
    from document_ai.vision import analyzer

    page = (
        "T.C.\n... SULH HUKUK MAHKEMESİNE\nDAVACI: [Ad Soyad]\n"
        "KONU: Konut ihtiyacı nedeniyle tahliye talebidir.\n"
        "AÇIKLAMALAR: 1. Müvekkil tapu kaydına göre maliktir. (Ekte: tapu kaydı)\n"
        "Ekte: müvekkilin kendi kira sözleşmesi, ödeme dekontları, ikametgâh belgesi.\n"
    )
    monkeypatch.setattr(
        analyzer,
        "assess_image",
        lambda _data, page=1: QualityReport(quality_score=0.92, status=QualityStatus.GOOD),
    )
    monkeypatch.setattr(analyzer, "transcribe_images", lambda _images: page)
    monkeypatch.setattr(
        analyzer,
        "extract_from_images",
        lambda _images, page_offset=0: {
            "document_type": "dilekce",
            "document_type_confidence": 0.9,
            "fields": [
                ExtractedField(
                    name="subject",
                    value="Konut ihtiyacı nedeniyle tahliye talebidir.",
                    bbox=[0.12, 0.28, 0.78, 0.34],
                    confidence=0.93,
                    source="vlm",
                )
            ],
            "sections": [],
            "full_text": "Konut ihtiyacı nedeniyle tahliye talebidir.",
            "raw": "{}",
        },
    )
    doc = analyzer.analyze_bytes("dilekce.jpg", _png())
    assert "tapu kaydı" in doc.raw_text
    assert "kira sözleşmesi" in doc.raw_text
    assert any(item.name == "attachment_section" for item in doc.fields)
    assert doc.visual_evidence == []


def test_analyze_bytes_keeps_transcript_when_extract_fails(monkeypatch) -> None:
    from document_ai.vision import analyzer
    from llm.client import OllamaError

    page = "T.C.\nANKARA SULH HUKUK MAHKEMESİNE\nKONU: tahliye\nAÇIKLAMALAR: tam metin burada."
    monkeypatch.setattr(
        analyzer,
        "assess_image",
        lambda _data, page=1: QualityReport(quality_score=0.92, status=QualityStatus.GOOD),
    )
    monkeypatch.setattr(analyzer, "transcribe_images", lambda _images: page)

    def boom(*_args, **_kwargs):
        raise OllamaError("VLM JSON ayrıştırılamadı: Unterminated string")

    monkeypatch.setattr(analyzer, "extract_from_images", boom)
    doc = analyzer.analyze_bytes("dilekce.jpg", _png())
    assert doc.raw_text == page
    assert "AÇIKLAMALAR" in doc.raw_text
    assert doc.visual_evidence == []


def test_harvest_ek_lines_from_dilekce_body() -> None:
    from document_ai.vision.analyzer import harvest_ek_lines

    text = (
        "Müvekkil tapu kaydına göre maliktir. (Ekte: tapu kaydı)\n"
        "Ekte: müvekkilin kendi kira sözleşmesi, ödeme dekontları, ikametgâh belgesi.\n"
        "Arabuluculuk son tutanağı ektedir.\n"
    )
    found = harvest_ek_lines(text)
    assert "tapu kaydı" in found
    assert any("kira sözleşmesi" in item for item in found)


def test_harvest_ek_numbered_citation() -> None:
    from document_ai.vision.analyzer import harvest_ek_lines

    text = (
        "Annemin vefatı üzerine maliki oldum [Ek. 1 Tapu Kaydı ]. "
        "Noter ihtarnamesi keşide edildi."
    )
    found = harvest_ek_lines(text)
    assert any("Tapu" in item for item in found)


def test_analyze_bytes_skips_verify_when_transcribe_works(monkeypatch) -> None:
    from document_ai.vision import analyzer

    def boom(*_args, **_kwargs):
        raise AssertionError("transcribe path must not call second-pass VLM")

    monkeypatch.setattr(
        analyzer,
        "assess_image",
        lambda _data, page=1: QualityReport(quality_score=0.92, status=QualityStatus.GOOD),
    )
    monkeypatch.setattr(analyzer, "transcribe_images", lambda _images: "T.C.\nKONU: tahliye\nAÇIKLAMALAR: tam metin.")
    monkeypatch.setattr(analyzer, "extract_from_images", boom)
    monkeypatch.setattr(analyzer, "verify_review_fields", boom)
    doc = analyzer.analyze_bytes("dilekce.jpg", _png())
    assert "tahliye" in doc.raw_text
    assert doc.visual_evidence == []


def test_analyze_bytes_rejects_pdf() -> None:
    from document_ai.vision import analyzer
    from document_ai.vision.analyzer import VisionUploadError

    try:
        analyzer.analyze_bytes("scan.pdf", b"%PDF-1.4 fake")
        raise AssertionError("PDF must not enter VLM analyze")
    except VisionUploadError as exc:
        assert "fotoğraf" in str(exc).lower()
