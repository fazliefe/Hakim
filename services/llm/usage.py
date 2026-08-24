from __future__ import annotations

import threading
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_local = threading.local()
_ctx: ContextVar[list[LlmUsage] | None] = ContextVar("hakim_llm_usage_bucket", default=None)
_lock = threading.Lock()
_global_bucket: list[LlmUsage] | None = None


def _fold(bucket: list[LlmUsage]) -> LlmUsage:
    prompt = sum(item.prompt_tokens for item in bucket)
    completion = sum(item.completion_tokens for item in bucket)
    model = next((item.model for item in reversed(bucket) if item.model), "")
    return LlmUsage(prompt_tokens=prompt, completion_tokens=completion, model=model)


def _bucket() -> list[LlmUsage]:
    for candidate in (getattr(_local, "bucket", None), _ctx.get(), _global_bucket):
        if candidate is not None:
            _local.bucket = candidate
            return candidate
    bucket: list[LlmUsage] = []
    _bind(bucket)
    return bucket


def _bind(bucket: list[LlmUsage]) -> None:
    global _global_bucket
    _local.bucket = bucket
    _ctx.set(bucket)
    with _lock:
        _global_bucket = bucket


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    input_per_million: float | None = None,
    output_per_million: float | None = None,
) -> float:
    if input_per_million is None or output_per_million is None:
        try:
            from hakim_config import get_models

            cfg = get_models()
            if input_per_million is None:
                input_per_million = cfg.llm_input_per_million
            if output_per_million is None:
                output_per_million = cfg.llm_output_per_million
        except Exception:
            input_per_million = input_per_million if input_per_million is not None else 0.075
            output_per_million = output_per_million if output_per_million is not None else 0.30
    return (prompt_tokens / 1_000_000) * float(input_per_million) + (
        completion_tokens / 1_000_000
    ) * float(output_per_million)


def parse_usage(body: dict[str, Any], *, model: str = "") -> LlmUsage:
    raw = body.get("usage") or {}
    if not isinstance(raw, dict):
        raw = {}
    if not raw:
        extra = body.get("x_groq") or {}
        if isinstance(extra, dict) and isinstance(extra.get("usage"), dict):
            raw = extra["usage"]
    prompt = int(raw.get("prompt_tokens") or raw.get("input_tokens") or 0)
    completion = int(raw.get("completion_tokens") or raw.get("output_tokens") or 0)
    if not prompt and not completion:
        prompt = int(body.get("prompt_eval_count") or 0)
        completion = int(body.get("eval_count") or 0)
    return LlmUsage(
        prompt_tokens=max(prompt, 0),
        completion_tokens=max(completion, 0),
        model=str(body.get("model") or model or ""),
    )


def reset_usage() -> None:
    _bind([])


def peek_usage() -> LlmUsage:
    return _fold(_bucket())


def add_usage(usage: LlmUsage) -> LlmUsage:
    bucket = _bucket()
    bucket.append(usage)
    return _fold(bucket)


def take_usage() -> LlmUsage:
    bucket = _bucket()
    current = _fold(bucket)
    bucket.clear()
    return current


def record_usage_from_response(body: dict[str, Any], *, model: str = "") -> LlmUsage:
    usage = parse_usage(body, model=model)
    if usage.total_tokens or usage.model:
        add_usage(usage)
    return usage
