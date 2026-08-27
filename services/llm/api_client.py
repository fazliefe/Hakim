from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from hakim_config import effective_max_tokens, get_models
from llm.client import OllamaError
from llm.retry import call_with_retry


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
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    **_kwargs: Any,
) -> str:
    def _run() -> str:
        try:
            return _api_chat_body(
                messages,
                timeout=timeout,
                json_mode=json_mode,
                temperature=temperature,
                model=model,
                max_tokens=max_tokens,
            )
        except OllamaError as exc:
            if json_mode and "json_validate_failed" in str(exc).lower():
                return _api_chat_body(
                    messages,
                    timeout=timeout,
                    json_mode=False,
                    temperature=temperature,
                    model=model,
                    max_tokens=max_tokens,
                )
            raise

    try:
        from document_ai.observability import observe_generation

        return observe_generation("llm-api", messages, _run)
    except OllamaError:
        raise
    except Exception:
        return _run()


def _record_usage(body: dict[str, Any], *, model: str) -> None:
    try:
        from llm.usage import record_usage_from_response

        record_usage_from_response(body, model=model)
    except Exception:
        pass


def _api_chat_body(
    messages: list[dict[str, str]],
    *,
    timeout: float = 25,
    json_mode: bool = True,
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    if not key:
        raise OllamaError("HAKIM_LLM_API_KEY yok")
    cfg = get_models()
    base = cfg.llm_url
    model = model or cfg.llm_model
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": cfg.llm_temperature if temperature is None else temperature,
        "max_tokens": effective_max_tokens(
            max_tokens if max_tokens is not None else cfg.llm_max_tokens
        ),
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if cfg.llm_disable_reasoning:
        # vLLM/Qwen3 thinking modu varsayılan açık; karmaşık promptlarda
        # reasoning izi max_tokens'ı tüketip boş içerik döndürebiliyor.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=data,
        headers=_headers(key),
        method="POST",
    )

    def _call() -> dict[str, Any]:
        with urllib.request.urlopen(request, timeout=timeout or cfg.llm_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    try:
        body = call_with_retry(_call, label="LLM API")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            _record_usage(json.loads(detail), model=model)
        except Exception:
            pass
        raise OllamaError(f"LLM API {exc.code}: {detail[:180]}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(str(exc)) from exc
    _record_usage(body, model=model)
    choices = body.get("choices") or []
    message = ((choices[0].get("message") or {}) if choices else {}).get("content") or ""
    if not str(message).strip():
        raise OllamaError("LLM API boş cevap döndü")
    return str(message)


def api_payload_url(base: str) -> str:
    return f"{base.rstrip('/')}/chat/completions"
