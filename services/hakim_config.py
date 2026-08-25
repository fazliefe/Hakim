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
    llm_input_per_million: float
    llm_output_per_million: float
    llm_disable_reasoning: bool
    embedding_model: str
    embedding_dims: int
    # Emsal karar (Yargıtay/Danıştay) için AYRI embedder — kanun maddelerinin
    # embedding_model/embedding_dims'ine (yukarıda) karışmaz, bkz. models.yaml
    # `decision_embedding` yorumu.
    decision_embedding_provider: str
    decision_embedding_model: str
    decision_embedding_dims: int
    decision_embedding_api_url: str | None
    decision_embedding_timeout: float
    rerank_enabled: bool
    rerank_model: str
    rerank_batch_size: int
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
    decision_embedding = merged.get("decision_embedding") or {}
    rerank = merged.get("rerank") or {}
    research = merged.get("research") or {}
    return ModelsConfig(
        profile=profile,
        writer=str(merged.get("writer") or "api"),
        llm_url=str(llm.get("url") or "https://api.groq.com/openai/v1").rstrip("/"),
        llm_model=str(llm.get("model") or "openai/gpt-oss-20b"),
        llm_max_tokens=int(llm.get("max_tokens") or 900),
        llm_timeout=float(llm.get("timeout") or 25),
        llm_temperature=float(llm.get("temperature") or 0.2),
        # `or` yerine `is None` kontrolü: 0.0 (ücretsiz servis) geçerli bir
        # değerdir, `x or default` bunu sessizce 0.075/0.30'a çevirirdi.
        llm_input_per_million=float(
            llm["input_per_million"] if llm.get("input_per_million") is not None else 0.075
        ),
        llm_output_per_million=float(
            llm["output_per_million"] if llm.get("output_per_million") is not None else 0.30
        ),
        llm_disable_reasoning=bool(llm.get("disable_reasoning", False)),
        embedding_model=str(embedding.get("model") or "newmindai/Mursit-Base-TR-Retrieval"),
        embedding_dims=int(embedding.get("dims") or 768),
        decision_embedding_provider=str(decision_embedding.get("provider") or "local"),
        decision_embedding_model=str(decision_embedding.get("model") or "newmindai/Mursit-Base-TR-Retrieval"),
        decision_embedding_dims=int(decision_embedding.get("dims") or 768),
        decision_embedding_api_url=(
            str(decision_embedding["url"]).rstrip("/") if decision_embedding.get("url") else None
        ),
        decision_embedding_timeout=float(decision_embedding.get("timeout") or 30),
        rerank_enabled=bool(rerank.get("enabled", True)),
        rerank_model=str(rerank.get("model") or "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"),
        rerank_batch_size=int(rerank.get("batch_size") or 16),
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


PROVIDER_LABELS = {
    "groq": "Groq",
    "ollama": "Ollama",
    "colab": "Colab",
    "evren": "Evren",
}


def model_display_name(model: str) -> str:
    raw = (model or "").strip()
    return raw.rsplit("/", 1)[-1] if raw else ""


def model_label(cfg: ModelsConfig | None = None) -> str:
    chosen = cfg or get_models()
    provider = PROVIDER_LABELS.get(chosen.profile, chosen.profile or "LLM")
    name = model_display_name(chosen.llm_model) or chosen.llm_model
    return f"{provider} · {name}"


def reload_models() -> ModelsConfig:
    get_models.cache_clear()
    return get_models()
