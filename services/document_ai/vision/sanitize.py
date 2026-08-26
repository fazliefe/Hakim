from __future__ import annotations

import re

from hakim_legal_schema.document import ExtractedField

_BRACKET = re.compile(r"\[[^\]]*\]")
_EK_BRACKET = re.compile(r"\[?\s*ek\.?\s*\d+", re.I)
_ELLIPSIS = re.compile(r"(\.{2,}|…|/ ?\.{2,}|20\.{2,})")
_MONEY = re.compile(r"\b(tl|lira|kira\s*bedeli|harca?\s*esas|yıllık\s*kira)\b", re.I)
_NATIONAL_ID = re.compile(r"t\.?\s*c\.?\s*kimlik|kimlik\s*no", re.I)
_COURT = re.compile(r"mahkeme(si)?ne?\b|sulh\s+hukuk|ağır\s+ceza|idar[iî]\s+mahkeme", re.I)
_STAMP_HINT = re.compile(r"mühür|kaşe|soğuk\s*damga", re.I)
_DOC_NO = re.compile(r"(\d{4}\s*/\s*\d+|[eE]\s*[-–]\s*\d|\d{2,}\s*[-./]\s*\d+)")
_NAME_TOKEN = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÊêÎîÔôÛû]{2,}")
_NAME_LABEL = re.compile(r"\b(ad[ıi]\s*ve\s*soyad|ad\s*soyad|isim\s*soyisim)\b", re.I)
_PRESENCE = frozenset({"imza var", "mühür var", "kaşe var", "imza mevcut", "mühür mevcut", "kaşe mevcut"})
_TITLES = frozenset({"av", "avukat", "dr", "prof", "öğr", "öğretim", "üyesi", "tc", "sn", "sayın"})

ZERO_BBOX = [0.0, 0.0, 0.0, 0.0]
OVERLAY_MIN_W = 0.04
OVERLAY_MIN_H = 0.012
OVERLAY_MIN_AREA = 0.0008
OVERLAY_MIN_CONF = 0.75

SCALAR_MAX_AREA = {
    "date": 0.08,
    "notification_date": 0.08,
    "document_no": 0.08,
    "case_no": 0.08,
    "decision_no": 0.08,
    "signature": 0.08,
    "stamp": 0.08,
    "page_number": 0.06,
    "person_name": 0.12,
    "institution": 0.12,
    "sender": 0.12,
    "recipient": 0.14,
    "subject": 0.16,
    "attachment_section": 0.28,
    "distribution_section": 0.22,
    "reference_section": 0.22,
}


def _date(value: str):
    from document_ai.vision.extractor import normalize_date

    return normalize_date(value)


def bbox_area(bbox: list[float]) -> float:
    if len(bbox) != 4:
        return 1.0
    x0, y0, x1, y1 = (float(v) for v in bbox)
    return abs(x1 - x0) * abs(y1 - y0)


def drawable_bbox(bbox: list[float] | None) -> bool:
    if not bbox or len(bbox) != 4:
        return False
    x0, y0, x1, y1 = (float(v) for v in bbox)
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    area = width * height
    return width >= OVERLAY_MIN_W and height >= OVERLAY_MIN_H and OVERLAY_MIN_AREA <= area <= 0.22


def is_placeholder(value: str) -> bool:
    text = (value or "").strip()
    if not text or text == "[okunamadı]":
        return True
    if _BRACKET.search(text):
        if _EK_BRACKET.search(text):
            return False
        return True
    if _ELLIPSIS.search(text) and _date(text) is None:
        return True
    compact = re.sub(r"[\s./\-]", "", text)
    if compact.lower() in {"imza", "tarih", "sayi", "sayı", "konu", "vekil", "davacı", "davalı"}:
        return True
    return False


def looks_like_person_name(value: str) -> bool:
    text = (value or "").strip()
    if not text or _NAME_LABEL.search(text) or _COURT.search(text) or _NATIONAL_ID.search(text):
        return False
    tokens = [token for token in _NAME_TOKEN.findall(text) if token.lower() not in _TITLES]
    return 2 <= len(tokens) <= 6


def value_fits_field(name: str, value: str) -> bool:
    text = (value or "").strip()
    if name in {"date", "notification_date"}:
        return _date(text) is not None
    if name == "document_no":
        if _MONEY.search(text):
            return False
        return bool(_DOC_NO.search(text)) and len(text) <= 48
    if name in {"case_no", "decision_no"}:
        return bool(re.search(r"\d{4}\s*/\s*\d+", text))
    if name == "signature":
        if _date(text):
            return False
        if re.fullmatch(r"[\d./\-\s…\.]+", text):
            return False
        return True
    if name == "stamp":
        if "imza" in text.lower() and not _STAMP_HINT.search(text):
            return False
        return bool(_STAMP_HINT.search(text) or "kaşe" in text.lower())
    if name == "institution":
        if _NATIONAL_ID.search(text):
            return False
        if _COURT.search(text):
            return False
        return True
    if name == "person_name":
        return looks_like_person_name(text)
    if name == "recipient":
        return True
    if name == "attachment_section":
        lower = text.lower()
        if any(word in lower for word in ("hukuki", "sonuç", "talep", "açıklama", "itiraz neden")):
            return False
        return "ek" in lower and len(text) <= 240
    return True


def overlay_bbox(name: str, bbox: list[float], *, confidence: float = 1.0, value: str = "") -> list[float]:
    if confidence < OVERLAY_MIN_CONF:
        return list(ZERO_BBOX)
    if name in {"signature", "stamp"} and (value or "").strip().lower() in _PRESENCE:
        return list(ZERO_BBOX)
    if not drawable_bbox(bbox):
        return list(ZERO_BBOX)
    if bbox_area(bbox) > SCALAR_MAX_AREA.get(name, 0.16):
        return list(ZERO_BBOX)
    return bbox


def sanitize_fields(fields: list[ExtractedField]) -> list[ExtractedField]:
    best: dict[str, ExtractedField] = {}
    for field in fields:
        if is_placeholder(field.value):
            continue
        if not value_fits_field(field.name, field.value):
            continue
        cleaned = field.model_copy(
            update={
                "bbox": overlay_bbox(
                    field.name,
                    list(field.bbox),
                    confidence=field.confidence,
                    value=field.value,
                )
            }
        )
        previous = best.get(field.name)
        if previous and previous.confidence >= cleaned.confidence:
            continue
        best[field.name] = cleaned
    return list(best.values())
