from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from hakim_config import get_models
from llm.client import OllamaError


def api_configured() -> bool:
    key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    return bool(key)


def _headers(key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "HAKIM/0.1 (legal-research)",
    }


def api_chat(
    messages: list[dict[str, str]],
    *,
    timeout: float = 25,
    json_mode: bool = True,
    **_kwargs: Any,
) -> str:
    def _run() -> str:
        return _api_chat_body(messages, timeout=timeout, json_mode=json_mode)

    try:
        from document_ai.observability import observe_generation

        return observe_generation("llm-api", messages, _run)
    except Exception:
        return _run()


def _api_chat_body(
    messages: list[dict[str, str]],
    *,
    timeout: float = 25,
    json_mode: bool = True,
) -> str:
    key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    if not key:
        raise OllamaError("HAKIM_LLM_API_KEY yok")
    cfg = get_models()
    base = cfg.llm_url
    model = cfg.llm_model
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": cfg.llm_temperature,
        "max_tokens": cfg.llm_max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=data,
        headers=_headers(key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or cfg.llm_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:180]
        raise OllamaError(f"LLM API {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(str(exc)) from exc
    choices = body.get("choices") or []
    message = ((choices[0].get("message") or {}) if choices else {}).get("content") or ""
    if not str(message).strip():
        raise OllamaError("LLM API boş cevap döndü")
    return str(message)


def api_payload_url(base: str) -> str:
    return f"{base.rstrip('/')}/chat/completions"
