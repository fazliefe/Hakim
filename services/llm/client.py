from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from hakim_config import get_models


def ollama_enabled() -> bool:
    flag = os.environ.get("HAKIM_OLLAMA_ENABLED")
    if flag is not None:
        return flag.strip().lower() in {"1", "true", "yes", "on"}
    return get_models().ollama_enabled


class OllamaError(RuntimeError):
    pass


def ping(timeout: float = 0.8) -> bool:
    url = get_models().ollama_url
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def chat_payload(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    json_mode: bool = True,
    keep_alive: str | None = None,
) -> dict[str, Any]:
    cfg = get_models()
    payload: dict[str, Any] = {
        "model": model or cfg.ollama_model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive or cfg.ollama_keep_alive,
        "options": {
            "temperature": cfg.llm_temperature,
        },
    }
    if json_mode:
        payload["format"] = "json"
    return payload


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    timeout: float | None = None,
    json_mode: bool = True,
) -> str:
    cfg = get_models()
    payload = chat_payload(
        messages,
        model=model,
        json_mode=json_mode,
    )
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{cfg.ollama_url}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout or cfg.llm_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError(str(exc)) from exc
    message = (body.get("message") or {}).get("content") or ""
    if not str(message).strip():
        raise OllamaError("Ollama boş cevap döndü")
    return str(message)


def parse_json_content(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise OllamaError("JSON ayrıştırılamadı") from exc
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise OllamaError("JSON nesne değil")
    return payload
