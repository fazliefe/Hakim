from __future__ import annotations

from hakim_legal_schema.document import (
    ExtractedField,
    QualityIssue,
    QualityReport,
    QualityStatus,
    StructuredDocument,
)


def test_page_warnings_finds_gap() -> None:
    from document_ai.validation.page_validator import page_warnings

    warnings = page_warnings("Sayfa 1/4 ... Sayfa 2/4 ... Sayfa 4/4")
    assert any(item.code == "missing_page" and "3" in item.message for item in warnings)


def test_page_warnings_silent_when_complete() -> None:
    from document_ai.validation.page_validator import page_warnings

    assert page_warnings("Sayfa 1/2 ve Sayfa 2/2") == []
    assert page_warnings("1/2 hissesi tapuda yazılıdır") == []
    assert page_warnings("dilekçe metni sayfa yok") == []


def test_attachment_warnings_numbered_gap() -> None:
    from document_ai.validation.attachment_validator import attachment_warnings

    warnings = attachment_warnings("[Ek. 1 Tapu] ... [Ek. 3 Dekont]")
    assert any(item.code == "missing_attachment_number" and "Ek-2" in item.message for item in warnings)


def test_attachment_warnings_declared_info() -> None:
    from document_ai.validation.attachment_validator import attachment_warnings

    warnings = attachment_warnings("Ekte: tapu kaydı", ["tapu kaydı"])
    assert any(item.code == "declared_attachments" for item in warnings)


def test_pii_detects_and_redacts_tckn() -> None:
    from document_ai.privacy.pii_detector import detect_pii, redact_text

    text = "T.C. Kimlik No: 10000000146 telefon 0532 123 45 67"
    kinds = {item.type for item in detect_pii(text)}
    assert "tckn" in kinds
    assert "phone" in kinds
    redacted = redact_text(text)
    assert "10000000146" not in redacted
    assert "[TCKN gizli]" in redacted
    assert "0532 123 45 67" not in redacted


def test_pii_ignores_invalid_tckn() -> None:
    from document_ai.privacy.pii_detector import detect_pii

    assert detect_pii("Kimlik 11111111111 ve 12345678901") == []


def test_conflict_detector_does_not_pick_winner() -> None:
    from document_ai.validation.conflict_detector import detect_conflicts

    left = StructuredDocument(
        document_id="a",
        filename="karar.jpg",
        fields=[ExtractedField(name="case_no", value="2024/12", bbox=[0.1, 0.1, 0.3, 0.2], confidence=0.9)],
    )
    right = StructuredDocument(
        document_id="b",
        filename="tebligat.jpg",
        fields=[ExtractedField(name="case_no", value="2024/13", bbox=[0.1, 0.1, 0.3, 0.2], confidence=0.9)],
    )
    conflicts = detect_conflicts([left, right])
    assert len(conflicts) == 1
    assert conflicts[0].field == "case_no"
    assert {row["value"] for row in conflicts[0].values} == {"2024/12", "2024/13"}


def test_bundle_reports_missing_tebligat_without_vllm() -> None:
    from document_ai.bundle.analyzer import analyze_bundle

    dilekce = StructuredDocument(
        document_id="d1",
        document_type="dilekce",
        filename="dilekce.jpg",
        raw_text="Tebliğ mazbatası ektedir. Tahliye talebidir.",
    )
    bundle = analyze_bundle([dilekce])
    assert "tebligat" in bundle.missing_documents
    assert bundle.conflicts == []
    assert bundle.documents[0].raw_text.startswith("Tebliğ")


def test_anomaly_notes_never_say_fake() -> None:
    from document_ai.forensics.visual_anomaly import anomaly_notes

    doc = StructuredDocument(
        document_id="q1",
        quality=QualityReport(
            quality_score=0.4,
            status=QualityStatus.WARNING,
            issues=[
                QualityIssue(
                    type="blur",
                    severity="high",
                    message="Görüntü bulanık.",
                    bbox=[0.1, 0.1, 0.4, 0.3],
                )
            ],
        ),
    )
    warnings, regions = anomaly_notes(doc)
    blob = " ".join(item.message for item in warnings).lower()
    assert "anlamına gelmez" in blob
    assert "belge sahte" not in blob
    assert all(item.type == "quality" for item in regions)


def test_verify_review_fields_updates_low_confidence(monkeypatch) -> None:
    from document_ai.vision import verifier
    from hakim_legal_schema.document import ExtractedField

    monkeypatch.setattr(verifier, "verify_field", lambda *_args, **_kwargs: "15.08.2026")
    fields = [
        ExtractedField(
            name="notification_date",
            value="14.08.2026",
            bbox=[0.62, 0.41, 0.82, 0.47],
            confidence=0.82,
            band="review",
        )
    ]
    out = verifier.verify_review_fields(b"png", fields)
    assert out[0].value == "15.08.2026"
    assert out[0].source == "vlm-verify"


def test_verify_review_fields_skips_trusted() -> None:
    from document_ai.vision.verifier import verify_review_fields
    from hakim_legal_schema.document import ExtractedField

    fields = [
        ExtractedField(
            name="subject",
            value="tahliye",
            bbox=[0.12, 0.28, 0.78, 0.34],
            confidence=0.96,
            band="trusted",
        )
    ]
    assert verify_review_fields(b"png", fields)[0].value == "tahliye"
