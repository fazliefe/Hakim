from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import os

import yaml


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def models_config_path() -> Path:
    override = os.environ.get("HAKIM_MODELS_CONFIG", "").strip()
    if override:
        return Path(override)
    return repo_root() / "config" / "models.yaml"


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass(frozen=True)
class ModelsConfig:
    profile: str
    writer: str
    llm_url: str
    llm_model: str
    llm_max_tokens: int
    llm_timeout: float
    llm_temperature: float
    embedding_model: str
    embedding_dims: int
    ollama_enabled: bool
    ollama_url: str
    ollama_model: str
    ollama_keep_alive: str
    research_allow_ollama: bool


def _parse(raw: dict[str, Any]) -> ModelsConfig:
    profile = (os.environ.get("HAKIM_PROFILE") or raw.get("active") or "groq").strip()
    defaults = raw.get("defaults") or {}
    profiles = raw.get("profiles") or {}
    chosen = profiles.get(profile) or {}
    merged = _merge(defaults, chosen)
    llm = merged.get("llm") or {}
    ollama = merged.get("ollama") or {}
    embedding = merged.get("embedding") or {}
    research = merged.get("research") or {}
    return ModelsConfig(
        profile=profile,
        writer=str(merged.get("writer") or "api"),
        llm_url=str(llm.get("url") or "https://api.groq.com/openai/v1").rstrip("/"),
        llm_model=str(llm.get("model") or "openai/gpt-oss-20b"),
        llm_max_tokens=int(llm.get("max_tokens") or 900),
        llm_timeout=float(llm.get("timeout") or 25),
        llm_temperature=float(llm.get("temperature") or 0.2),
        embedding_model=str(embedding.get("model") or "newmindai/Mursit-Base-TR-Retrieval"),
        embedding_dims=int(embedding.get("dims") or 768),
        ollama_enabled=bool(ollama.get("enabled", False)),
        ollama_url=str(ollama.get("url") or "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=str(ollama.get("model") or "llama3.2:3b"),
        ollama_keep_alive=str(ollama.get("keep_alive") or "30m"),
        research_allow_ollama=bool(research.get("allow_ollama", False)),
    )


@lru_cache(maxsize=1)
def get_models() -> ModelsConfig:
    path = models_config_path()
    if not path.is_file():
        return _parse({"active": "groq", "defaults": {}, "profiles": {}})
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"models.yaml nesne değil: {path}")
    return _parse(raw)


def reload_models() -> ModelsConfig:
    get_models.cache_clear()
    return get_models()
