from __future__ import annotations

from hakim_legal_schema.document import ExtractedField, StructuredDocument


def test_bbox_normalizes_and_clamps() -> None:
    from hakim_legal_schema.document import BBox

    box = BBox.from_list([1.2, -0.1, 0.3, 0.8])
    assert box.as_list() == [0.3, 0.0, 1.0, 0.8]


def test_extracted_field_fills_label() -> None:
    field = ExtractedField(
        name="notification_date",
        value="14.08.2026",
        normalized_value="2026-08-14",
        page=1,
        bbox=[0.62, 0.41, 0.82, 0.47],
        confidence=0.91,
        source="vlm",
    )
    assert field.label == "Tebliğ Tarihi"
    assert field.bbox[0] == 0.62
    assert all(0.0 <= value <= 1.0 for value in field.bbox)


def test_structured_document_roundtrip() -> None:
    doc = StructuredDocument(
        document_id="doc-001",
        document_type="tebligat",
        document_type_confidence=0.96,
        fields=[
            ExtractedField(
                name="notification_date",
                value="14.08.2026",
                bbox=[0.62, 0.41, 0.82, 0.47],
                confidence=0.91,
            )
        ],
    )
    payload = doc.model_dump()
    again = StructuredDocument.model_validate(payload)
    assert again.document_type == "tebligat"
    assert again.fields[0].name == "notification_date"
    assert "pages" in payload
    assert "quality" in payload
    assert "visual_evidence" in payload


def test_document_page_preview_roundtrip() -> None:
    from hakim_legal_schema.document import DocumentPage

    page = DocumentPage(page=1, width=800, height=1000, preview_jpeg="/9j/fake")
    assert page.preview_jpeg == "/9j/fake"
