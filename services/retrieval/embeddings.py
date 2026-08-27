from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from typing import Protocol


from hakim_config import get_models

DEFAULT_DIMS = 768


class Embedder(Protocol):
    dims: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic bag-of-tokens embedder for tests and offline fallback."""

    def __init__(self, dims: int = DEFAULT_DIMS) -> None:
        self.dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str | None = None, dims: int | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        cfg = get_models()
        self.model_name = model_name or cfg.embedding_model
        fallback_dims = dims or cfg.embedding_dims
        self._model = SentenceTransformer(self.model_name)
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        if callable(get_dim):
            self.dims = int(get_dim() or fallback_dims)
        else:
            self.dims = int(self._model.get_sentence_embedding_dimension() or fallback_dims)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # e5 models prefer query:/passage: prefixes; MiniLM does not.
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [list(map(float, row)) for row in vectors]


def create_embedder(*, prefer_neural: bool = True) -> Embedder:
    if prefer_neural:
        try:
            return SentenceTransformerEmbedder()
        except Exception:
            pass
    return HashingEmbedder()


class EvrenEmbedder:
    """Evren `/v1/embeddings` (OpenAI-uyumlu, bge-m3-embed, 1024 dims) — emsal
    karar (Yargıtay/Danıştay) semantic aramasında kullanılır. Kanun maddeleri
    hâlâ yerel `SentenceTransformerEmbedder` (768 dims) kullanıyor; bu iki
    embedder'ın boyutları FARKLI, aynı ES index'e yazılamazlar (bkz.
    `retrieval/mapping.py::DECISION_INDEX_NAME`)."""

    def __init__(self, *, batch_size: int = 32, timeout: float | None = None) -> None:
        cfg = get_models()
        if not cfg.decision_embedding_api_url:
            raise ValueError("decision_embedding.url yapılandırılmamış (config/models.yaml)")
        self.model_name = cfg.decision_embedding_model
        self.dims = cfg.decision_embedding_dims
        self.batch_size = batch_size
        self._url = f"{cfg.decision_embedding_api_url}/embeddings"
        self._timeout = timeout or cfg.decision_embedding_timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            out.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return out

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        from llm.api_client import _headers
        from llm.client import OllamaError
        from llm.retry import call_with_retry

        key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
        if not key:
            raise OllamaError("HAKIM_LLM_API_KEY yok")
        payload = {"model": self.model_name, "input": batch}
        data = json.dumps(payload).encode("utf-8")

        def _call() -> dict:
            request = urllib.request.Request(
                self._url, data=data, headers=_headers(key), method="POST"
            )
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            body = call_with_retry(_call, label="Evren embeddings API")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Evren embeddings API {exc.code}: {detail[:180]}") from exc
        except urllib.error.URLError as exc:
            raise OllamaError(str(exc)) from exc

        items = body.get("data") or []
        if len(items) != len(batch):
            raise OllamaError(
                f"Evren embeddings API beklenmeyen sonuç sayısı: {len(items)} != {len(batch)}"
            )
        ordered = sorted(items, key=lambda item: item.get("index", 0))
        return [list(map(float, item["embedding"])) for item in ordered]


def create_decision_embedder() -> Embedder:
    """Emsal karar index'i için embedder — Evren API yapılandırılmışsa onu
    kullanır, yoksa (offline dev/test) boyutu tutarlı bir deterministik
    fallback'e düşer."""
    cfg = get_models()
    key = os.environ.get("HAKIM_LLM_API_KEY", "").strip()
    if cfg.decision_embedding_provider == "api" and cfg.decision_embedding_api_url and key:
        try:
            return EvrenEmbedder()
        except Exception:
            pass
    return HashingEmbedder(dims=cfg.decision_embedding_dims)
