from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from retrieval.bm25 import extract_article_no
from retrieval.rrf import FusedHit

if TYPE_CHECKING:
    from retrieval.cross_encoder import PairScorer


def _tokens(query: str, *, min_len: int = 4) -> list[str]:
    return [tok for tok in re.findall(r"\w+", query.lower(), flags=re.UNICODE) if len(tok) >= min_len]


def _article_boost(query: str, hit: FusedHit) -> float:
    article = extract_article_no(query)
    return 3.0 if article and str(hit.hit.article_no) == str(article) else 0.0


def _lexical_scores(query: str, fused: list[FusedHit]) -> list[float]:
    """Model yokken (varsayılan, testler, `rerank.enabled: false`) kullanılan
    deterministik sözcük-örtüşme sezgiseli — eski davranışın aynısı."""
    tokens = _tokens(query)
    return [
        sum(1 for tok in tokens if tok in f"{hit.hit.title or ''} {hit.hit.content or ''}".lower())
        + _article_boost(query, hit)
        for hit in fused
    ]


def _cross_encoder_scores(query: str, fused: list[FusedHit], scorer: "PairScorer") -> list[float]:
    pairs = [(query, f"{hit.hit.title or ''} {hit.hit.content or ''}".strip()) for hit in fused]
    raw = scorer.score(pairs)
    return [float(raw[i]) + _article_boost(query, hit) for i, hit in enumerate(fused)]


def rerank_fused(
    query: str,
    fused: list[FusedHit],
    *,
    limit: int | None = None,
    scorer: "PairScorer | None" = None,
) -> list[FusedHit]:
    """RRF'den çıkan adayları yeniden sırala.

    `scorer` verilmezse (varsayılan) sözcük-örtüşme sezgiseliyle sıralar —
    model indirmeden, tamamen deterministik (testler bunu kullanır).
    `scorer` verilirse (bkz. `retrieval.cross_encoder.create_reranker`) her
    adayı query ile birlikte cross-encoder'dan geçirir; skorlama sırasında
    bir hata olursa (model çökerse, API vs.) sessizce sözcük-örtüşmesine
    düşer — tek bir bozuk aramanın tüm isteği patlatmaması için. Madde
    numarası tam eşleşirse iki yöntemde de aynı +3 bonus uygulanır (cross-
    encoder aynı maddenin farklı fıkralarını karıştırabilir)."""
    if not fused:
        return []
    if scorer is not None:
        try:
            primary = _cross_encoder_scores(query, fused, scorer)
        except Exception:
            primary = _lexical_scores(query, fused)
    else:
        primary = _lexical_scores(query, fused)
    scored = sorted(
        zip(primary, (float(hit.rrf_score) for hit in fused), fused),
        key=lambda row: (row[0], row[1]),
        reverse=True,
    )
    top = scored[: limit or len(scored)]
    return [replace(hit, rank=rank) for rank, (_, _, hit) in enumerate(top, start=1)]
