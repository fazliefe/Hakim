"""Groq Whisper üzerinden ses -> metin (dikte).

Yalnızca Araştırma modülünde kullanılıyor: kullanıcı burada kendi kişisel/
dosya verisini değil, genel bir hukuki soru dikte eder — bu yüzden
self-hosted bir model yerine bir API kabul edilebilir (bkz. config/
models.yaml `whisper` yorumu). Evrak/işlem modüllerinde AYNI karar
verilmemeli — oralarda gerçek kişisel veri dikte edilebilir.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid

from hakim_config import get_models
from llm.client import OllamaError
from llm.retry import call_with_retry

logger = logging.getLogger(__name__)


def whisper_configured() -> bool:
    key = os.environ.get("HAKIM_WHISPER_API_KEY", "").strip() or os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    return bool(key)


def _multipart_body(
    fields: dict[str, str], *, file_field: str, filename: str, content: bytes, content_type: str
) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    parts.append(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def transcribe_audio(data: bytes, *, filename: str = "audio.webm", content_type: str = "audio/webm") -> str:
    key = os.environ.get("HAKIM_WHISPER_API_KEY", "").strip() or os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    if not key:
        raise OllamaError("HAKIM_WHISPER_API_KEY (veya HAKIM_LLM_API_KEY) tanımlı değil")
    if not data:
        raise OllamaError("Ses verisi boş")

    cfg = get_models()
    body, boundary = _multipart_body(
        {"model": cfg.whisper_model, "language": "tr", "response_format": "json"},
        file_field="file",
        filename=filename,
        content=data,
        content_type=content_type,
    )

    def _call() -> dict:
        request = urllib.request.Request(
            f"{cfg.whisper_url}/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "HAKIM/0.1 (legal-research)",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=cfg.whisper_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        result = call_with_retry(_call, label="Whisper API")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.warning("Whisper API hata döndürdü: %s %s", exc.code, detail[:180])
        raise OllamaError(f"Dikte API {exc.code}: {detail[:180]}") from exc
    except urllib.error.URLError as exc:
        logger.warning("Whisper API'ye bağlanılamadı: %s", exc)
        raise OllamaError(str(exc)) from exc

    text = str(result.get("text") or "").strip()
    if not text:
        raise OllamaError("Dikte boş sonuç döndü — ses anlaşılamamış olabilir")
    return text
