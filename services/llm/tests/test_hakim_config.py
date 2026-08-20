from __future__ import annotations

from pathlib import Path

from hakim_config import get_models, reload_models


def test_default_profile_is_groq() -> None:
    reload_models()
    cfg = get_models()
    assert cfg.profile == "groq"
    assert cfg.writer == "api"
    assert "groq.com" in cfg.llm_url
    assert cfg.embedding_model == "newmindai/Mursit-Base-TR-Retrieval"
    assert cfg.embedding_dims == 768
    assert cfg.research_allow_ollama is False


def test_profile_env_switches_to_ollama(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_PROFILE", "ollama")
    try:
        reload_models()
        cfg = get_models()
        assert cfg.profile == "ollama"
        assert cfg.writer == "ollama"
        assert cfg.ollama_enabled is True
        assert cfg.research_allow_ollama is True
    finally:
        monkeypatch.delenv("HAKIM_PROFILE", raising=False)
        reload_models()


def test_custom_yaml_path(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        """
active: groq
profiles:
  groq:
    writer: api
    llm:
      url: https://example.test/v1
      model: demo-llm
    embedding:
      model: demo-embed
      dims: 32
    ollama:
      enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HAKIM_MODELS_CONFIG", str(path))
    monkeypatch.delenv("HAKIM_PROFILE", raising=False)
    try:
        reload_models()
        cfg = get_models()
        assert cfg.llm_model == "demo-llm"
        assert cfg.embedding_dims == 32
    finally:
        monkeypatch.delenv("HAKIM_MODELS_CONFIG", raising=False)
        reload_models()
