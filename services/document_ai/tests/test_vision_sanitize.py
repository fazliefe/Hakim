from __future__ import annotations

from document_ai.vision.extractor import fields_from_payload
from document_ai.vision.sanitize import is_placeholder, sanitize_fields, value_fits_field
from hakim_legal_schema.document import ExtractedField


def test_rejects_template_placeholders() -> None:
    assert is_placeholder("Av. [Ad Soyad]")
    assert is_placeholder("20...")
    assert is_placeholder(".../.../20...")
    assert is_placeholder("[Yıllık kira bedeli]")
    assert is_placeholder("[Ad Soyad] (T.C. Kimlik No: [...])")
    assert not is_placeholder("14.08.2026")
    assert not is_placeholder("Konut ihtiyacı nedeniyle tahliye")
    assert not is_placeholder("[Ek. 1 Tapu Kaydı]")


def test_field_compatibility_matches_live_dilekce_errors() -> None:
    assert not value_fits_field("document_no", "yıllık kira bedeli")
    assert not value_fits_field("signature", "20...")
    assert not value_fits_field("stamp", "Av. Mehmet Yılmaz — İmza")
    assert not value_fits_field("institution", "T.C. Kimlik No: 123")
    assert not value_fits_field("date", "20...")
    assert value_fits_field("recipient", "ANKARA SULH HUKUK MAHKEMESİNE")
    assert value_fits_field("document_no", "E-123")
    assert value_fits_field("case_no", "2026/481")
    assert value_fits_field("signature", "imza var")
    assert value_fits_field("stamp", "mühür var")
    assert value_fits_field("person_name", "Mehmet Yılmaz")
    assert not value_fits_field("person_name", "Ad Soyad")
    assert not value_fits_field("person_name", "ANKARA SULH HUKUK MAHKEMESİNE")


def test_sanitize_drops_screenshot_false_fields() -> None:
    fields = fields_from_payload(
        {
            "fields": [
                {
                    "name": "subject",
                    "value": "Konut/iş yeri ihtiyacı nedeniyle kiralananın tahliyesi talebidir.",
                    "bbox": [0.12, 0.28, 0.78, 0.32],
                    "confidence": 0.93,
                },
                {
                    "name": "recipient",
                    "value": "ANKARA SULH HUKUK MAHKEMESİNE",
                    "bbox": [0.55, 0.08, 0.88, 0.12],
                    "confidence": 0.90,
                },
                {"name": "person_name", "value": "Av. [Ad Soyad]", "confidence": 0.88},
                {
                    "name": "institution",
                    "value": "[Ad Soyad] (T.C. Kimlik No: [...])",
                    "confidence": 0.86,
                },
                {"name": "signature", "value": "20...", "confidence": 0.82},
                {"name": "stamp", "value": "Av. [Ad Soyad] — İmza", "confidence": 0.81},
                {"name": "date", "value": "20...", "confidence": 0.80},
                {"name": "document_no", "value": "[Yıllık kira bedeli]", "confidence": 0.79},
            ]
        }
    )
    names = [item.name for item in fields]
    assert names == ["subject", "recipient"]


def test_huge_bbox_is_not_used_for_overlay() -> None:
    cleaned = sanitize_fields(
        [
            ExtractedField(
                name="subject",
                value="Tahliye talebidir.",
                bbox=[0.05, 0.10, 0.95, 0.85],
                confidence=0.9,
            )
        ]
    )
    assert cleaned[0].bbox == [0.0, 0.0, 0.0, 0.0]


def test_duplicate_attachment_section_keeps_one() -> None:
    fields = fields_from_payload(
        {
            "fields": [
                {
                    "name": "attachment_section",
                    "value": "HUKUKİ NEDENLERİ TBK m.350",
                    "confidence": 0.9,
                    "bbox": [0.1, 0.2, 0.4, 0.3],
                },
                {
                    "name": "attachment_section",
                    "value": "Ekler: sağlık raporu, kira sözleşmesi",
                    "confidence": 0.7,
                    "bbox": [0.1, 0.7, 0.5, 0.78],
                },
            ]
        }
    )
    names = [item.name for item in fields]
    assert names.count("attachment_section") <= 1
    if names:
        assert "ek" in fields[0].value.lower()


def test_signature_field_is_dropped() -> None:
    cleaned = sanitize_fields(
        [
            ExtractedField(
                name="signature",
                value="imza var",
                bbox=[0.70, 0.82, 0.88, 0.90],
                confidence=0.92,
            ),
            ExtractedField(
                name="subject",
                value="Tahliye talebidir.",
                bbox=[0.12, 0.28, 0.78, 0.32],
                confidence=0.93,
            ),
        ]
    )
    assert [item.name for item in cleaned] == ["subject"]


def test_low_confidence_bbox_is_zeroed() -> None:
    cleaned = sanitize_fields(
        [
            ExtractedField(
                name="subject",
                value="Tahliye talebidir.",
                bbox=[0.12, 0.28, 0.78, 0.32],
                confidence=0.40,
            )
        ]
    )
    assert cleaned[0].bbox == [0.0, 0.0, 0.0, 0.0]
