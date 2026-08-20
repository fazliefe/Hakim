from __future__ import annotations

import os
from typing import Any


def _host() -> str:
    return (
        os.environ.get("LANGFUSE_HOST")
        or os.environ.get("LANGFUSE_BASE_URL")
        or "https://cloud.langfuse.com"
    ).rstrip("/")


def langfuse_configured() -> bool:
    return bool(os.environ.get("LANGFUSE_SECRET_KEY", "").strip()) and bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    )


def init_langfuse() -> None:
    if not langfuse_configured():
        return
    os.environ.setdefault("LANGFUSE_HOST", _host())
    try:
        from langfuse import Langfuse

        Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"].strip(),
            secret_key=os.environ["LANGFUSE_SECRET_KEY"].strip(),
            host=_host(),
        )
    except Exception:
        return


def trace_url(trace_id: str | None) -> str | None:
    if not trace_id:
        return None
    return f"{_host()}/trace/{trace_id}"


def current_trace_id() -> str | None:
    if not langfuse_configured():
        return None
    try:
        from langfuse import get_client

        tid = get_client().get_current_trace_id()
        return str(tid) if tid else None
    except Exception:
        return None


def flush_langfuse() -> None:
    if not langfuse_configured():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        return


def observe_generation(name: str, messages: list[dict[str, str]], fn):
    """Wrap an LLM call as a Langfuse generation when keys exist."""
    if not langfuse_configured():
        return fn()
    try:
        from langfuse import get_client

        lf = get_client()
        with lf.start_as_current_observation(as_type="generation", name=name) as gen:
            gen.update(input=messages)
            out = fn()
            gen.update(output=str(out)[:4000])
            return out
    except Exception:
        return fn()
