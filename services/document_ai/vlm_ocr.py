"""Evren vision OCR for photos and scanned pages.

Evren's `vlm` alias is video-only (images return 400). Handwriting and
stills go to `llm-fast` / `llm-large`, at most two images per request.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any

from hakim_config import get_models
from llm.api_client import _headers, _record_usage
from llm.client import OllamaError

TRANSCRIBE_PROMPT = (
    "Bu görüntüdeki belgeyi yukarıdan aşağı, soldan sağa SATIR SATIR aktar. "
    "Başlık, mahkeme, davacı/davalı, konu, harç, arabuluculuk, açıklamalar, ekler, dipnot, "
    "imza satırı ve şablon yer tutucuları ([Ad Soyad], noktalı yerler, 20...) DAHİL. "
    "Hiçbir paragrafı veya maddeyi atlama. Yalnızca KONU satırı yazmak yasak. "
    "Metin uydurma. Okunmayan yere [okunamadı] yaz. "
    "Başlık, özet veya açıklama ekleme; yalnız belge metnini döndür."
)

MAX_PDF_PAGES = 10
PDF_RENDER_DPI = 144


def vision_configured() -> bool:
    return bool(os.environ.get("HAKIM_LLM_API_KEY", "").strip())


def transcribe_images(images: list[tuple[str, bytes]]) -> str:
    """`images` is a list of (mime, bytes). Batches by Evren's 2-image cap."""
    if not images:
        return ""
    cfg = get_models()
    batch_size = max(1, int(cfg.vision_max_images or 2))
    parts: list[str] = []
    for start in range(0, len(images), batch_size):
        chunk = images[start : start + batch_size]
        parts.append(vision_chat(chunk, TRANSCRIBE_PROMPT))
    return "\n\n".join(p for p in parts if p.strip()).strip()


def transcribe_pdf_bytes(data: bytes, *, max_pages: int = MAX_PDF_PAGES) -> str:
    try:
        pages = render_pdf_page_pngs(data, max_pages=max_pages)
    except Exception as exc:
        raise OllamaError(f"PDF sayfası görüntüye çevrilemedi: {exc}") from exc
    if not pages:
        raise OllamaError("PDF sayfası görüntüye çevrilemedi.")
    return transcribe_images([("image/png", png) for png in pages])


def render_pdf_page_pngs(data: bytes, *, max_pages: int = MAX_PDF_PAGES, dpi: int = PDF_RENDER_DPI) -> list[bytes]:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        limit = min(len(doc), max_pages if max_pages > 0 else len(doc))
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        out: list[bytes] = []
        for i in range(limit):
            pix = doc.load_page(i).get_pixmap(matrix=matrix, alpha=False)
            out.append(pix.tobytes("png"))
        return out
    finally:
        doc.close()


def look_like_image(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] in (b"II", b"MM") and data[2:4] in (b"\x2a\x00", b"\x00\x2a"):
        return "image/tiff"
    return None


def vision_chat(
    images: list[tuple[str, bytes]],
    prompt: str,
    *,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    try:
        return _vision_chat_body(images, prompt, json_mode=json_mode, model=model)
    except OllamaError as exc:
        if json_mode and "json_validate_failed" in str(exc).lower():
            return _vision_chat_body(images, prompt, json_mode=False, model=model)
        raise


def _vision_chat_body(
    images: list[tuple[str, bytes]],
    prompt: str,
    *,
    json_mode: bool = False,
    model: str | None = None,
) -> str:
    key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    if not key:
        raise OllamaError("HAKIM_LLM_API_KEY yok")
    cfg = get_models()
    chosen = model or cfg.vision_model
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for mime, raw in images:
        b64 = base64.b64encode(raw).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )
    payload: dict[str, Any] = {
        "model": chosen,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
        "max_tokens": cfg.vision_max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if cfg.llm_disable_reasoning:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    request = urllib.request.Request(
        f"{cfg.llm_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.vision_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            _record_usage(json.loads(detail), model=chosen)
        except Exception:
            pass
        raise OllamaError(f"Evren görüntü API {exc.code}: {detail[:180]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(str(exc)) from exc
    _record_usage(body, model=chosen)
    choices = body.get("choices") or []
    message = ((choices[0].get("message") or {}) if choices else {}).get("content") or ""
    if not str(message).strip():
        raise OllamaError("Evren görüntü API boş cevap döndü")
    return str(message).strip()


def _vision_chat(images: list[tuple[str, bytes]]) -> str:
    return vision_chat(images, TRANSCRIBE_PROMPT)
