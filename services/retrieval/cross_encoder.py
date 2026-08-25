from __future__ import annotations

from typing import Protocol

from hakim_config import get_models


class PairScorer(Protocol):
    """(query, belge) çiftini tek geçişte skorlayan cross-encoder arayüzü."""

    def score(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class CrossEncoderScorer:
    """sentence-transformers CrossEncoder — query ve adayı BİRLİKTE kodlayıp
    doğrudan bir alaka skoru üretir (bi-encoder embedder'lardan farklı olarak
    önceden indekslenemez). Bu yüzden yalnızca RRF'den çıkan küçük aday
    havuzunu (tipik olarak <=12) yeniden sıralamak için kullanılır; ilk
    aramayı bu YAPMAZ — tüm index üzerinde çok yavaş olurdu."""

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import CrossEncoder

        cfg = get_models()
        self.model_name = model_name or cfg.rerank_model
        self.batch_size = cfg.rerank_batch_size
        self._model = CrossEncoder(self.model_name, max_length=512)

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        raw = self._model.predict(
            list(pairs), batch_size=self.batch_size, show_progress_bar=False
        )
        return [float(x) for x in raw]


def create_reranker(*, prefer_neural: bool = True) -> PairScorer | None:
    """Cross-encoder'ı yükler; `rerank.enabled: false` ise veya model
    indirilemez/yüklenemezse (offline, ilk çalıştırmada internet yok, vs.)
    sessizce None döner. Çağıran taraf (`retrieval.rerank.rerank_fused`)
    None'ı "sözcük-örtüşme sezgiseline düş" şeklinde yorumlar — aynı zarafet
    deseni `retrieval.embeddings.create_embedder`'da da var."""
    cfg = get_models()
    if not prefer_neural or not cfg.rerank_enabled:
        return None
    try:
        return CrossEncoderScorer()
    except Exception:
        return None
