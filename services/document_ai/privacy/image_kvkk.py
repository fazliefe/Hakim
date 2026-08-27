"""KVKK gate for dilekçe annex photos. VLM observes; this module decides."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from document_ai.privacy.pii_detector import detect_pii, redact_text

REJECT_FLAGS = (
    "identifiable_face",
    "identity_document",
    "tckn_visible",
    "iban_or_account",
    "phone_or_email",
    "child_or_minor",
    "health_data",
)

KVKK_REJECT_MESSAGE = (
    "KVKK nedeniyle bu fotoğraf işleme alınmadı. "
    "Tanınabilir yüz, kimlik belgesi, T.C. kimlik no veya benzeri kişisel veri "
    "içeren görüntüler dilekçeye eklenmez."
)

KVKK_SCREEN_PROMPT = """\
Bu görüntüyü dilekçe eki olarak kullanmadan önce KVKK kontrolü yap.

Yalnızca JSON yaz:
{
  "kvkk_risk": true,
  "flags": {
    "identifiable_face": false,
    "identity_document": false,
    "tckn_visible": false,
    "iban_or_account": false,
    "phone_or_email": false,
    "child_or_minor": false,
    "health_data": false
  },
  "reasons": [],
  "caption": "",
  "scene": ""
}

Tanınabilir yüz, kimlik / ehliyet / pasaport, TCKN, IBAN, çocuk yüzü veya
sağlık verisi varsa kvkk_risk true olsun; caption ve scene boş kalsın.
Plaka tek başına ret sebebi değildir.
kvkk_risk false ise caption EK satırı için kısa resmi başlık olsun; scene
1-3 cümle görünür olguyu anlatsın. Yüz, isim, TCKN, hesap no yazma.
Hukuki sonuç veya suç niteliği çıkarma. Görseli kanıt sayma.
"""


@dataclass
class KvkkDecision:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    caption: str = ""
    scene: str = ""
    flags: dict[str, bool] = field(default_factory=dict)


def _extract_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(text[start : end + 1])
        if isinstance(data, dict):
            return data
    raise json.JSONDecodeError("not json", text, 0)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "evet", "yes"}
    return False


def _clean(text: str, limit: int) -> str:
    return " ".join(redact_text(text or "").split())[:limit]


def parse_kvkk_screen(raw: str | dict[str, Any]) -> KvkkDecision:
    try:
        data = raw if isinstance(raw, dict) else _extract_json(str(raw))
    except Exception:
        return KvkkDecision(accepted=False, reasons=["Görüntü KVKK kontrolünden geçemedi."])

    flags_raw = data.get("flags") if isinstance(data.get("flags"), dict) else {}
    flags = {str(key): _truthy(value) for key, value in flags_raw.items()}
    reasons = [str(item).strip() for item in (data.get("reasons") or []) if str(item).strip()]
    caption_raw = str(data.get("caption") or "")
    scene_raw = str(data.get("scene") or "")
    pii_hit = bool(detect_pii(f"{caption_raw} {scene_raw}"))
    flagged = any(flags.get(name) for name in REJECT_FLAGS)
    risk = _truthy(data.get("kvkk_risk"))
    if risk or flagged or pii_hit:
        if pii_hit and not any("kişisel" in item.lower() or "tckn" in item.lower() for item in reasons):
            reasons.append("Görüntü veya açıklamada kişisel veri var.")
        if flagged and not reasons:
            reasons.append("Görüntü KVKK kapsamındaki kişisel veri içeriyor.")
        if risk and not reasons:
            reasons.append(KVKK_REJECT_MESSAGE)
        return KvkkDecision(
            accepted=False,
            reasons=reasons or [KVKK_REJECT_MESSAGE],
            flags=flags,
        )
    caption = _clean(caption_raw, 160) or "Olay görseli"
    scene = _clean(scene_raw, 400)
    return KvkkDecision(accepted=True, caption=caption, scene=scene, flags=flags)


def screen_islem_photo(data: bytes, filename: str = "ek.jpg") -> KvkkDecision:
    from document_ai.ingest import MAX_UPLOAD_BYTES
    from document_ai.vlm_ocr import look_like_image, vision_chat
    from llm.client import OllamaError

    if not data:
        return KvkkDecision(accepted=False, reasons=["Dosya boş."])
    if len(data) > MAX_UPLOAD_BYTES:
        return KvkkDecision(accepted=False, reasons=["Dosya 8 MB sınırını aşıyor."])
    mime = look_like_image(data)
    if not mime:
        return KvkkDecision(accepted=False, reasons=["Yalnızca JPG, PNG veya WebP fotoğraf kabul edilir."])
    try:
        raw = vision_chat([(mime, data)], KVKK_SCREEN_PROMPT, json_mode=True)
    except OllamaError as exc:
        return KvkkDecision(accepted=False, reasons=[f"Görüntü okunamadı: {exc}"])
    _ = filename
    return parse_kvkk_screen(raw)
