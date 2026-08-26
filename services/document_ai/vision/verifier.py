"""Second-pass llm-large on a cropped field. Does not issue legal rulings."""

from __future__ import annotations

from document_ai.vlm_ocr import vision_chat
from document_ai.vision.cropper import crop_bbox
from document_ai.vision.sanitize import drawable_bbox
from hakim_legal_schema.document import ExtractedField

VERIFY_PROMPT = (
    "Bu kırpılmış görüntü alanındaki değeri okuyun. Tahmin etmeyin. "
    "Okunamıyorsa yalnızca [okunamadı] yazın. Başka cümle eklemeyin."
)


def verify_field(image_bytes: bytes, field: ExtractedField, *, model: str = "llm-large") -> str:
    crop = crop_bbox(image_bytes, field.bbox)
    return vision_chat([("image/png", crop)], VERIFY_PROMPT, model=model)


def verify_review_fields(
    image_bytes: bytes,
    fields: list[ExtractedField],
    *,
    limit: int = 2,
) -> list[ExtractedField]:
    """Re-read low-confidence drawable fields. Failures leave the original value."""
    out: list[ExtractedField] = []
    used = 0
    for field in fields:
        if (
            used >= limit
            or field.band == "trusted"
            or not drawable_bbox(list(field.bbox))
            or not field.value
            or field.value == "[okunamadı]"
        ):
            out.append(field)
            continue
        try:
            text = (verify_field(image_bytes, field) or "").strip()
            used += 1
            if text and text != field.value:
                bump = min(1.0, float(field.confidence) + 0.05)
                out.append(field.model_copy(update={"value": text[:240], "source": "vlm-verify", "confidence": bump}))
            else:
                out.append(field)
        except Exception:
            out.append(field)
    return out
