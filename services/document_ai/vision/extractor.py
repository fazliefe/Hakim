from __future__ import annotations

import json
import re
from typing import Any

from document_ai.classify import TYPE_LABELS
from document_ai.evidence.confidence import apply_bands
from document_ai.vlm_ocr import vision_chat
from document_ai.vision.sanitize import sanitize_fields
from hakim_legal_schema.document import (
    FIELD_LABELS,
    KNOWN_FIELDS,
    DocumentSection,
    ExtractedField,
)
from llm.client import OllamaError

_DATE_RE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$")

EXTRACT_PROMPT = """Bu bir Türk kamu/yargı evrakı görüntüsüdür.
Sayfanın tamamını oku: başlık, taraflar, konu, harç, arabuluculuk, açıklamalar, ek cümleleri.
Hukuki yorum veya hüküm verme.

full_text: görünen HER satır. Şablon yer tutucu da yaz ([Ad Soyad], 20..., Ekte: ...). Satır atlama.

fields: yalnız gerçekten doldurulmuş değerler. [Ad Soyad], 20..., .../.../20... field olmasın.
Paragrafı veya tüm bloğu tek kutu yapma. En fazla 8 field.

Alan kuralları:
- date / notification_date: tam gün.ay.yıl. "20..." tarih değildir.
- document_no: evrak sayısı. Harç, yıllık kira, TL sayı değildir.
- recipient: muhatap veya mahkeme.
- person_name: gerçek ad soyad. "Av. [Ad Soyad]" değildir.
- subject: KONU satırının kısa metni; AÇIKLAMALAR gövdesi field olmasın (gövde full_text'te kalsın).
- attachment_section: "Ekte:" / "Ekler:" geçen somut belgeler (tapu, kira sözleşmesi, tutanak).
- signature field YOK. El yazısı imza/paraf full_text'e yazılmasın; "imza var" yazma.

bbox yalnız o değerin ince kutusu. Emin değilsen [0,0,0,0].
JSON içinde gerçek satır sonu kullanma; full_text satır dizisi olsun.

Yalnızca JSON döndür:
{
  "document_type": "tebligat|iddianame|mahkeme_karari|dilekce|ust_yazi|olur|genelge|tutanak|rapor|cevap_yazisi|bilgi_yazisi|belirsiz",
  "document_type_confidence": 0.0,
  "full_text": ["T.C.", "okunan satır 2"],
  "fields": [
    {
      "name": "notification_date",
      "value": "14.08.2026",
      "page": 1,
      "bbox": [0.62, 0.41, 0.82, 0.47],
      "confidence": 0.91
    }
  ],
  "sections": []
}

name yalnızca: date, document_no, case_no, decision_no, notification_date, sender, recipient, person_name, institution, subject, stamp, page_number, attachment_section, distribution_section, reference_section.
"""


def _strip_fences(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    return text[start:].strip() if start >= 0 else text.strip()


def _escape_raw_controls_in_strings(text: str) -> str:
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            out.append(ch)
            continue
        out.append(ch)
        if ch == '"':
            in_string = True
    if in_string:
        out.append('"')
    return "".join(out)


def _close_open_containers(text: str) -> str:
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    if in_string:
        text += '"'
    while stack:
        text += stack.pop()
    return text


def parse_vlm_json(raw: str) -> dict[str, Any]:
    text = _strip_fences(raw)
    candidates = [text]
    repaired = _escape_raw_controls_in_strings(text)
    if repaired not in candidates:
        candidates.append(repaired)
    closed = _close_open_containers(repaired)
    if closed not in candidates:
        candidates.append(closed)
    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(payload, dict):
            return payload
        last_error = json.JSONDecodeError("VLM JSON nesne değil", candidate, 0)
    detail = last_error or "bilinmeyen hata"
    raise OllamaError(f"VLM JSON ayrıştırılamadı: {detail}") from last_error


def _parse_json(raw: str) -> dict[str, Any]:
    return parse_vlm_json(raw)


def _join_full_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def normalize_date(value: str) -> str | None:
    match = _DATE_RE.match((value or "").strip())
    if not match:
        return None
    day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def fields_from_payload(payload: dict[str, Any], *, page_offset: int = 0) -> list[ExtractedField]:
    rows = payload.get("fields") or []
    out: list[ExtractedField] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if name not in KNOWN_FIELDS or name == "signature":
            continue
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        page = int(row.get("page") or 1) + page_offset
        raw_bbox = row.get("bbox")
        try:
            bbox = [float(v) for v in list(raw_bbox)[:4]] if isinstance(raw_bbox, list) else [0.0, 0.0, 0.0, 0.0]
            if len(bbox) != 4:
                bbox = [0.0, 0.0, 0.0, 0.0]
        except (TypeError, ValueError):
            bbox = [0.0, 0.0, 0.0, 0.0]
        try:
            confidence = float(row.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        normalized = None
        if name.endswith("date") or name == "date":
            normalized = normalize_date(value)
        out.append(
            ExtractedField(
                name=name,
                label=FIELD_LABELS.get(name, name),
                value=value,
                normalized_value=normalized,
                page=max(1, page),
                bbox=bbox,
                confidence=max(0.0, min(1.0, confidence)),
                source="vlm",
            )
        )
    return apply_bands(sanitize_fields(out))


def sections_from_payload(payload: dict[str, Any], *, page_offset: int = 0) -> list[DocumentSection]:
    rows = payload.get("sections") or []
    out: list[DocumentSection] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "body").strip() or "body"
        text = str(row.get("text") or "").strip()
        page = int(row.get("page") or 1) + page_offset
        out.append(DocumentSection(name=name, text=text, page=max(1, page)))
    return out


def extract_from_images(images: list[tuple[str, bytes]], *, page_offset: int = 0) -> dict[str, Any]:
    raw = vision_chat(images, EXTRACT_PROMPT, json_mode=True)
    payload = _parse_json(raw)
    doc_type = str(payload.get("document_type") or "belirsiz").strip().lower()
    if doc_type not in TYPE_LABELS:
        doc_type = "belirsiz"
    try:
        type_conf = float(payload.get("document_type_confidence") or 0.0)
    except (TypeError, ValueError):
        type_conf = 0.0
    full_text = _join_full_text(payload.get("full_text") or payload.get("full_text_lines"))
    return {
        "document_type": doc_type,
        "document_type_confidence": max(0.0, min(1.0, type_conf)),
        "fields": fields_from_payload(payload, page_offset=page_offset),
        "sections": sections_from_payload(payload, page_offset=page_offset),
        "full_text": full_text,
        "raw": raw,
    }
