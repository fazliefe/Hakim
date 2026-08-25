from __future__ import annotations

from pathlib import Path

from hakim_config import reload_models
from retrieval.cross_encoder import create_reranker

# NOT: create_reranker(prefer_neural=True) başarı yolu (gerçek model yükleme)
# burada test EDİLMEZ — repo genelinde aynı ilke: testler create_embedder()
# gibi ağ/model bağımlı fabrikaları hiç çağırmaz, hep bir sahte enjekte eder
# (bkz. HashingEmbedder kullanımları). Burada yalnızca ağdan bağımsız,
# deterministik "devre dışı" yolları doğrulanıyor.


def test_prefer_neural_false_returns_none_without_importing() -> None:
    assert create_reranker(prefer_neural=False) is None


def test_rerank_disabled_in_config_returns_none(monkeypatch, tmp_path: Path) -> None:
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
    rerank:
      enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HAKIM_MODELS_CONFIG", str(path))
    monkeypatch.delenv("HAKIM_PROFILE", raising=False)
    try:
        reload_models()
        assert create_reranker(prefer_neural=True) is None
    finally:
        monkeypatch.delenv("HAKIM_MODELS_CONFIG", raising=False)
        reload_models()
