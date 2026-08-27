"""VLM observes; Python/rules decide. No legal conclusions here."""

from __future__ import annotations

import re
import uuid

from document_ai.evidence.confidence import apply_bands
from document_ai.forensics.visual_anomaly import anomaly_notes
from document_ai.privacy.pii_detector import detect_pii
from document_ai.validation.attachment_validator import attachment_warnings
from document_ai.validation.completeness import completeness_warnings
from document_ai.validation.page_validator import page_warnings
from document_ai.vlm_ocr import drop_signature_lines, look_like_image, transcribe_images
from document_ai.vision.extractor import extract_from_images
from document_ai.vision.quality import assess_image, jpeg_preview, user_facing_quality_lines
from document_ai.vision.sanitize import drawable_bbox
from document_ai.vision.verifier import verify_review_fields
from hakim_config import get_models
from hakim_legal_schema.document import (
    DocumentPage,
    ExtractedField,
    QualityReport,
    QualityStatus,
    StructuredDocument,
    StructuredWarning,
)
from hakim_legal_schema.evidence import evidence_from_fields
from llm.client import OllamaError

_EKTE_LINE = re.compile(r"(?:ekte|ekler)\s*[:：]?\s*(.+)", re.I)
_EK_CITATION = re.compile(r"\[?\s*ek\.?\s*(\d+)\s*[.\-:]?\s*([^\]\n]{3,80})", re.I)


class VisionUploadError(Exception):
    """Wrong file type for the photo-only VLM endpoint."""


def _pages_from_upload(filename: str, data: bytes) -> list[tuple[str, bytes]]:
    lower = (filename or "").lower()
    if lower.endswith(".pdf") or data.startswith(b"%PDF"):
        raise VisionUploadError(
            "VLM yalnız fotoğraf içindir. PDF için /v1/evrak/dosya kullanın (metin katmanı veya yerel OCR)."
        )
    mime = look_like_image(data)
    if mime:
        return [(mime, data)]
    if lower.endswith((".jpg", ".jpeg")):
        return [("image/jpeg", data)]
    if lower.endswith(".png"):
        return [("image/png", data)]
    if lower.endswith(".webp"):
        return [("image/webp", data)]
    if lower.endswith((".tif", ".tiff")):
        return [("image/tiff", data)]
    raise VisionUploadError("VLM yalnız JPEG, PNG, WebP veya TIFF fotoğraf kabul eder.")


def harvest_ek_lines(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        key = re.sub(r"\s+", " ", (label or "")).strip().strip("[] .")
        lowered = key.lower()
        if len(key) < 4 or lowered in seen:
            return
        seen.add(lowered)
        found.append(key)

    for match in _EK_CITATION.finditer(text or ""):
        add(f"Ek-{match.group(1)} {match.group(2).strip().strip('[] .')}")
    for line in (text or "").splitlines():
        match = _EKTE_LINE.search(line)
        if match:
            add(match.group(1).strip().strip(".)"))
        if len(found) >= 8:
            break
    return found[:8]


def _merge_harvested_ek(fields: list[ExtractedField], raw_text: str) -> list[ExtractedField]:
    if any(item.name == "attachment_section" for item in fields):
        return fields
    lines = harvest_ek_lines(raw_text)
    if not lines:
        return fields
    extra = ExtractedField(
        name="attachment_section",
        value="Ekler: " + "; ".join(lines),
        bbox=[0.0, 0.0, 0.0, 0.0],
        confidence=0.82,
        source="rules",
    )
    return apply_bands([*fields, extra])


def _raw_text(full_text: str, sections, fields) -> str:
    if (full_text or "").strip():
        return full_text.strip()
    section_text = "\n\n".join(item.text for item in sections if item.text)
    if section_text.strip():
        return section_text.strip()
    return "\n".join(
        f"{item.label}: {item.value}" for item in fields if item.value and item.value != "[okunamadı]"
    ).strip()


def analyze_bytes(filename: str, data: bytes) -> StructuredDocument:
    document_id = f"doc-{uuid.uuid4().hex[:8]}"
    pages_raw = _pages_from_upload(filename, data)
    if not pages_raw:
        raise OllamaError("Sayfa görüntüsü üretilemedi.")

    page_models: list[DocumentPage] = []
    quality_warnings: list[StructuredWarning] = []
    usable: list[tuple[int, str, bytes]] = []
    for index, (mime, blob) in enumerate(pages_raw, start=1):
        report = assess_image(blob, page=index)
        width, height, preview = jpeg_preview(blob)
        page_models.append(
            DocumentPage(
                page=index,
                quality=report,
                width=width,
                height=height,
                preview_jpeg=preview,
            )
        )
        for line in user_facing_quality_lines(report):
            quality_warnings.append(
                StructuredWarning(code=f"quality_{report.status.value}", message=line, page=index)
            )
        if report.status != QualityStatus.UNUSABLE:
            usable.append((index, mime, blob))

    first_quality = page_models[0].quality or QualityReport()
    doc = StructuredDocument(
        document_id=document_id,
        filename=filename,
        pages=page_models,
        quality=first_quality,
        warnings=quality_warnings,
    )

    if not usable:
        doc.warnings.append(
            StructuredWarning(
                code="unusable",
                message="Görüntü kullanılamaz. Daha net, düz ve aydınlık bir çekim yapın.",
                severity="error",
            )
        )
        return doc

    cfg = get_models()
    batch = max(1, int(cfg.vision_max_images or 2))
    fields = []
    sections = []
    transcribed_parts: list[str] = []
    extract_parts: list[str] = []
    best_type = "belirsiz"
    best_conf = 0.0
    for start in range(0, len(usable), batch):
        chunk = usable[start : start + batch]
        images = [(mime, blob) for _page, mime, blob in chunk]
        page_offset = chunk[0][0] - 1
        page_text = ""
        try:
            page_text = transcribe_images(images)
        except OllamaError:
            page_text = ""
        if page_text.strip():
            transcribed_parts.append(page_text.strip())
            continue
        extracted = {
            "document_type": "belirsiz",
            "document_type_confidence": 0.0,
            "fields": [],
            "sections": [],
            "full_text": "",
        }
        try:
            extracted = extract_from_images(images, page_offset=page_offset)
        except OllamaError:
            pass
        fields.extend(extracted["fields"])
        sections.extend(extracted["sections"])
        if extracted.get("full_text"):
            extract_parts.append(str(extracted["full_text"]).strip())
        if extracted["document_type_confidence"] >= best_conf:
            best_type = extracted["document_type"]
            best_conf = extracted["document_type_confidence"]

    transcribed = drop_signature_lines("\n\n".join(transcribed_parts))
    extracted_full = drop_signature_lines("\n\n".join(part for part in extract_parts if part))
    if transcribed:
        raw = transcribed
    else:
        raw = _raw_text(extracted_full, sections, fields)

    fields = _merge_harvested_ek(fields, raw)
    if usable and any(drawable_bbox(list(item.bbox)) and item.band != "trusted" for item in fields):
        try:
            fields = apply_bands(verify_review_fields(usable[0][2], fields))
        except Exception:
            pass
    declared = harvest_ek_lines(raw)
    doc.document_type = best_type
    doc.document_type_confidence = best_conf
    doc.fields = fields
    doc.sections = sections
    doc.attachments = [{"name": item, "status": "declared"} for item in declared]
    doc.visual_evidence = evidence_from_fields([item for item in fields if drawable_bbox(list(item.bbox))])
    doc.raw_text = raw
    if len(raw) >= 200 and sum(1 for item in fields if drawable_bbox(list(item.bbox))) <= 1:
        doc.warnings.append(
            StructuredWarning(
                code="overlay_sparse",
                message="Sayfa metni okundu. Yeşil kutu yalnız doldurulmuş alanlar içindir; [Ad Soyad] / 20... şablonları işaretlenmez.",
                severity="info",
            )
        )
    doc.warnings.extend(page_warnings(raw))
    doc.warnings.extend(attachment_warnings(raw, declared))
    anomaly_warn, anomaly_regions = anomaly_notes(doc)
    doc.warnings.extend(anomaly_warn)
    if anomaly_regions:
        doc.suspicious_regions = anomaly_regions
    doc.sensitive_regions = detect_pii(raw)
    if doc.sensitive_regions:
        kinds = sorted({item.type for item in doc.sensitive_regions})
        doc.warnings.append(
            StructuredWarning(
                code="pii_found",
                message=f"Paylaşım öncesi {len(doc.sensitive_regions)} kişisel veri izi ({', '.join(kinds)}). Gizlemeden kopyalamayın.",
                severity="info",
            )
        )
    doc.warnings.extend(completeness_warnings(doc))
    return doc
