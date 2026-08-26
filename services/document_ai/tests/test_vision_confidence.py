from __future__ import annotations

from document_ai.evidence.confidence import band_for
from hakim_legal_schema.document import ExtractedField, StructuredDocument


def test_critical_fields_use_stricter_thresholds() -> None:
    assert band_for("subject", 0.91) == "trusted"
    assert band_for("notification_date", 0.91) == "review"
    assert band_for("notification_date", 0.96) == "trusted"
    assert band_for("case_no", 0.70) == "uncertain"


def test_completeness_flags_required_tebligat_fields() -> None:
    from document_ai.validation.completeness import completeness_warnings

    doc = StructuredDocument(
        document_id="doc-001",
        document_type="tebligat",
        fields=[
            ExtractedField(name="notification_date", value="14.08.2026", confidence=0.9),
        ],
    )
    codes = {item.field for item in completeness_warnings(doc)}
    assert "recipient" in codes
    assert "case_no" in codes
    assert "notification_date" not in codes


def test_completeness_ignores_unread_values() -> None:
    from document_ai.validation.completeness import completeness_warnings

    doc = StructuredDocument(
        document_id="doc-002",
        document_type="ust_yazi",
        fields=[
            ExtractedField(name="date", value="01.01.2026"),
            ExtractedField(name="document_no", value="E-123"),
            ExtractedField(name="subject", value="Konu"),
            ExtractedField(name="recipient", value="İlgi"),
            ExtractedField(name="signature", value="[okunamadı]"),
        ],
    )
    missing = completeness_warnings(doc)
    assert [item.field for item in missing] == ["signature"]
    assert missing[0].message.startswith("✗")
