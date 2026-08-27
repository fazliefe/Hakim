from __future__ import annotations

import io
import json
import urllib.error

from retrieval.embeddings import EvrenEmbedder, HashingEmbedder, create_decision_embedder


class _Resp:
    def __init__(self, body: dict) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self._body).encode("utf-8")


def _embedding_body(n: int, dims: int = 1024) -> dict:
    return {
        "data": [{"index": i, "embedding": [0.1 * i] * dims} for i in range(n)],
        "model": "bge-m3-embed",
    }


def test_evren_embedder_dims_and_model_from_config() -> None:
    embedder = EvrenEmbedder()
    assert embedder.dims == 1024
    assert embedder.model_name == "bge-m3-embed"


def test_evren_embedder_embed_returns_vectors(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    calls: list[dict] = []

    def fake_urlopen(request, timeout=None):
        calls.append(json.loads(request.data.decode("utf-8")))
        return _Resp(_embedding_body(len(calls[-1]["input"])))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = EvrenEmbedder(batch_size=32)
    vectors = embedder.embed(["metin bir", "metin iki"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert calls[0]["model"] == "bge-m3-embed"
    assert calls[0]["input"] == ["metin bir", "metin iki"]


def test_evren_embedder_batches_requests(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    calls: list[list[str]] = []

    def fake_urlopen(request, timeout=None):
        batch = json.loads(request.data.decode("utf-8"))["input"]
        calls.append(batch)
        return _Resp(_embedding_body(len(batch)))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = EvrenEmbedder(batch_size=2)
    texts = ["a", "b", "c", "d", "e"]
    vectors = embedder.embed(texts)
    assert len(vectors) == 5
    assert len(calls) == 3  # 2 + 2 + 1
    assert calls[0] == ["a", "b"]
    assert calls[-1] == ["e"]


def test_evren_embedder_missing_api_key_raises(monkeypatch) -> None:
    from llm.client import OllamaError

    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    embedder = EvrenEmbedder()
    try:
        embedder.embed(["x"])
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "HAKIM_LLM_API_KEY" in str(exc)


def test_evren_embedder_retries_with_backoff_on_5xx_then_raises(monkeypatch) -> None:
    # services/llm/retry.py::call_with_retry ile tekilleştirildi (bkz. o
    # dosya) — artık 1 sabit retry değil, üstel geri çekilmeyle 3 deneme.
    from llm.client import OllamaError

    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(
            "https://evren-llmapi.ssyz.org.tr/v1/embeddings",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "server busy"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = EvrenEmbedder()
    try:
        embedder.embed(["x"])
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "503" in str(exc)
    assert attempts["n"] == 3  # varsayılan call_with_retry(attempts=3)


def test_evren_embedder_recovers_after_one_transient_5xx(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise urllib.error.HTTPError(
                "https://evren-llmapi.ssyz.org.tr/v1/embeddings",
                503,
                "Service Unavailable",
                hdrs=None,
                fp=io.BytesIO(b'{"error": "server busy"}'),
            )
        return _Resp(_embedding_body(1))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = EvrenEmbedder()
    vectors = embedder.embed(["x"])
    assert len(vectors) == 1
    assert attempts["n"] == 2


def test_evren_embedder_does_not_retry_on_4xx(monkeypatch) -> None:
    from llm.client import OllamaError

    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    attempts = {"n": 0}

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(
            "https://evren-llmapi.ssyz.org.tr/v1/embeddings",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "bad input"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    embedder = EvrenEmbedder()
    try:
        embedder.embed(["x"])
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "400" in str(exc)
    assert attempts["n"] == 1  # 4xx'te retry yok


def test_create_decision_embedder_uses_evren_when_key_present(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    embedder = create_decision_embedder()
    assert isinstance(embedder, EvrenEmbedder)
    assert embedder.dims == 1024


def test_create_decision_embedder_falls_back_without_key(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    embedder = create_decision_embedder()
    assert isinstance(embedder, HashingEmbedder)
    assert embedder.dims == 1024
