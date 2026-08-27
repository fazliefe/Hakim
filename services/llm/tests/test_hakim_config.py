from __future__ import annotations

from pathlib import Path

import pytest

from hakim_config import ModelsConfigError, get_models, reload_models


def test_effective_max_tokens_unbounded_when_missing() -> None:
    from hakim_config import UNBOUNDED_MAX_TOKENS, effective_max_tokens

    assert effective_max_tokens(None) == UNBOUNDED_MAX_TOKENS
    assert effective_max_tokens(0) == UNBOUNDED_MAX_TOKENS
    assert effective_max_tokens(900) == 900
    """HAKİM'in varsayılan profili TEKNOFEST'in kotasız/ücretsiz H200
    servisidir (bkz. config/models.yaml: active)."""
    reload_models()
    cfg = get_models()
    assert cfg.profile == "evren"
    assert cfg.writer == "api"
    assert "evren-llmapi" in cfg.llm_url
    assert cfg.llm_model == "llm-fast"
    assert cfg.embedding_model == "newmindai/Mursit-Base-TR-Retrieval"
    assert cfg.embedding_dims == 768
    # Emsal karar (Yargıtay/Danıştay) embedder'ı AYRI bir alan seti kullanır —
    # kanun maddelerinin (yukarıdaki embedding_model/dims) yerel modeline
    # karışmamalı. Bu regresyon canlı yakalandı: `decision_embedding` yerine
    # `embedding` anahtarı kullanılsaydı `_merge()` kanun index'inin
    # embedder'ını bge-m3-embed'e (geçersiz yerel model adı) çevirirdi.
    assert cfg.embedding_model != cfg.decision_embedding_model
    assert cfg.decision_embedding_provider == "api"
    assert cfg.decision_embedding_model == "bge-m3-embed"
    assert cfg.decision_embedding_dims == 1024
    assert cfg.decision_embedding_api_url == "https://evren-llmapi.ssyz.org.tr/v1"
    assert cfg.rerank_enabled is False
    assert cfg.rerank_model == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    assert cfg.rerank_batch_size == 16
    assert cfg.dense_gate == 0.70
    assert cfg.multi_query_aggregation is True
    # Deneysel özellik — mevcut kurulumların sınıflandırma davranışını
    # sessizce değiştirmemesi için varsayılan kapalı (bkz. prototype_classifier.py).
    assert cfg.classification_fallback_enabled is False
    assert cfg.research_allow_ollama is False
    # Kotasız/ücretsiz servis; groq'un USD tarifesi burada geçerli değil.
    assert cfg.llm_input_per_million == 0.0
    assert cfg.llm_output_per_million == 0.0
    assert cfg.vision_model == "llm-fast"
    assert cfg.vision_max_images == 2
    assert cfg.llm_max_tokens is None
    assert cfg.vision_max_tokens is None


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
        # rerank bloğu yoksa varsayılana düşmeli (KeyError değil).
        assert cfg.rerank_enabled is True
        assert cfg.rerank_model == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    finally:
        monkeypatch.delenv("HAKIM_MODELS_CONFIG", raising=False)
        reload_models()


def test_decision_embedding_equal_to_embedding_raises_when_api(monkeypatch, tmp_path: Path) -> None:
    """`decision_embedding:` yerine yanlışlıkla `embedding:` yazılırsa
    (canlıda bir kez yaşanan regresyon) config yüklenirken AÇIK bir hatayla
    patlamalı — SentenceTransformer'ın derinlerde alakasız bir hata
    fırlatmasını beklemek yerine."""
    path = tmp_path / "models.yaml"
    path.write_text(
        """
active: broken
profiles:
  broken:
    writer: api
    llm:
      url: https://example.test/v1
      model: demo-llm
    embedding:
      model: bge-m3-embed
      dims: 1024
    decision_embedding:
      provider: api
      model: bge-m3-embed
      dims: 1024
      url: https://example.test/v1
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HAKIM_MODELS_CONFIG", str(path))
    monkeypatch.delenv("HAKIM_PROFILE", raising=False)
    try:
        with pytest.raises(ModelsConfigError):
            reload_models()
    finally:
        monkeypatch.delenv("HAKIM_MODELS_CONFIG", raising=False)
        reload_models()


def test_decision_embedding_equal_to_embedding_is_fine_when_local(monkeypatch, tmp_path: Path) -> None:
    """provider: local (API kullanmayan groq/ollama/colab profilleri) iken
    iki alanın aynı yerel model adını paylaşması normaldir — o durumda
    decision index zaten HashingEmbedder fallback'ine düşer (bkz.
    retrieval/embeddings.py::create_decision_embedder), guard burada
    tetiklenmemeli."""
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
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HAKIM_MODELS_CONFIG", str(path))
    monkeypatch.delenv("HAKIM_PROFILE", raising=False)
    try:
        reload_models()
        cfg = get_models()
        assert cfg.decision_embedding_provider == "local"
        assert cfg.decision_embedding_model == cfg.embedding_model
    finally:
        monkeypatch.delenv("HAKIM_MODELS_CONFIG", raising=False)
        reload_models()
