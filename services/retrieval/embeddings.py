from __future__ import annotations

import hashlib
import math
import re
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
