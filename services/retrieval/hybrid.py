from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from typing import Any

from retrieval.bm25 import Bm25Searcher, SearchHit, extract_article_no, parse_law_hint
from retrieval.embeddings import Embedder
from retrieval.rrf import FusedHit, reciprocal_rank_fusion
from retrieval.semantic import SemanticSearcher


def unique_by_article(hits: list[FusedHit], *, limit: int | None = None) -> list[FusedHit]:
    """Keep the first hit per (law_no, article_no); re-index after a duplicate ingest."""
    seen: set[tuple[str, ...]] = set()
    out: list[FusedHit] = []
    for hit in hits:
        if hit.hit.law_no and hit.hit.article_no:
            key = ("law", hit.hit.law_no, hit.hit.article_no)
        else:
            key = ("id", hit.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            FusedHit(
                chunk_id=hit.chunk_id,
                rrf_score=hit.rrf_score,
                rank=len(out) + 1,
                sources=hit.sources,
                hit=hit.hit,
                bm25_rank=hit.bm25_rank,
                semantic_rank=hit.semantic_rank,
            )
        )
        if limit is not None and len(out) >= limit:
            break
    return out


def _is_exact_citation_query(query: str) -> bool:
    article_no = extract_article_no(query)
    if not article_no:
        return False
    compact = query.lower().strip()
    return bool(
        re.fullmatch(
            rf"(?:(?:tck|cmk|iyuk|tmk|tbk|iik|kanun)\s+)?(?:m\.\s*)?(?:madde\s+)?{re.escape(article_no)}\s*",
            compact,
            flags=re.IGNORECASE,
        )
    )


class HybridSearcher:
    """BM25 + semantic → RRF (Phase 3 hybrid core)."""

    def __init__(
        self,
        es_client: Any,
        embedder: Embedder,
        *,
        bm25_size: int = 50,
        semantic_size: int = 50,
        rrf_k: int = 60,
        limit: int = 30,
    ) -> None:
        self.bm25 = Bm25Searcher(es_client)
        self.semantic = SemanticSearcher(es_client, embedder)
        self.bm25_size = bm25_size
        self.semantic_size = semantic_size
        self.rrf_k = rrf_k
        self.limit = limit

    def search(
        self,
        query: str,
        *,
        law_no: str | None = None,
        at: datetime | None = None,
        limit: int | None = None,
    ) -> list[FusedHit]:
        top_n = limit or self.limit
        pool = max(top_n * 3, top_n)
        bm25_hits = self.bm25.search(
            query, size=self.bm25_size, law_no=law_no, at=at
        )

        # Exact citation queries are lexical; semantic vectors add noise.
        if _is_exact_citation_query(query):
            cited = [
                FusedHit(
                    chunk_id=hit.chunk_id,
                    rrf_score=1.0 / (self.rrf_k + hit.rank),
                    rank=i,
                    sources=("bm25",),
                    hit=hit,
                    bm25_rank=hit.rank,
                    semantic_rank=None,
                )
                for i, hit in enumerate(bm25_hits[:pool], start=1)
            ]
            return unique_by_article(cited, limit=top_n)

        semantic_hits = self.semantic.search(
            query, size=self.semantic_size, law_no=law_no, at=at
        )
        fused = reciprocal_rank_fusion(
            {"bm25": bm25_hits, "semantic": semantic_hits},
            k=self.rrf_k,
            limit=pool,
        )
        article_no = extract_article_no(query)
        if article_no:
            hinted = parse_law_hint(query)
            exact = [
                h
                for h in fused
                if h.hit.article_no == article_no and (not hinted or h.hit.law_no == hinted)
            ]
            rest = [h for h in fused if h not in exact]
            fused = exact + rest
        return unique_by_article(fused, limit=top_n)



def fused_to_dict(hit: FusedHit) -> dict[str, Any]:
    base = asdict(hit.hit)
    return {
        **base,
        "rrf_score": hit.rrf_score,
        "rrf_rank": hit.rank,
        "retrievers": list(hit.sources),
        "bm25_rank": hit.bm25_rank,
        "semantic_rank": hit.semantic_rank,
    }
