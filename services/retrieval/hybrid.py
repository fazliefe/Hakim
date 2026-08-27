from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from typing import Any

from retrieval.bm25 import Bm25Searcher, SearchHit, extract_article_no, parse_law_hint
from retrieval.embeddings import Embedder
from retrieval.mapping import INDEX_NAME
from retrieval.rrf import FusedHit, reciprocal_rank_fusion
from retrieval.semantic import SemanticSearcher


def _missing_es_index(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "index_not_found" in text or "no such index" in text


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
    """BM25 + semantic → RRF (Phase 3 hybrid core).

    Kanun maddeleri (varsayılan `es_client`/`embedder`) ve emsal kararlar
    (opsiyonel `decision_index`/`decision_embedder`) AYRI ES index'lerinde
    tutulur (boyut farkı — bkz. `retrieval/mapping.py::DECISION_INDEX_NAME`).
    `decision_index`/`decision_embedder` verilmezse davranış tamamen eskisiyle
    aynıdır. `law_no` set edildiğinde kararlar hiç sorgulanmaz — bir madde
    arayan kullanıcı sadece madde metnini görsün (kullanıcı kararı)."""

    def __init__(
        self,
        es_client: Any,
        embedder: Embedder,
        *,
        bm25_size: int = 50,
        semantic_size: int = 50,
        rrf_k: int = 60,
        limit: int = 30,
        decision_index: str | None = None,
        decision_embedder: Embedder | None = None,
        index_name: str | None = None,
        bm25_weight: float = 1.0,
        dense_weight: float = 1.0,
    ) -> None:
        idx = index_name or INDEX_NAME
        self.bm25 = Bm25Searcher(es_client, index_name=idx)
        self.semantic = SemanticSearcher(es_client, embedder, index_name=idx)
        self.bm25_size = bm25_size
        self.semantic_size = semantic_size
        self.rrf_k = rrf_k
        self.limit = limit
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight
        self.decision_bm25: Bm25Searcher | None = None
        self.decision_semantic: SemanticSearcher | None = None
        if decision_index and decision_embedder is not None:
            self.decision_bm25 = Bm25Searcher(es_client, index_name=decision_index)
            self.decision_semantic = SemanticSearcher(es_client, decision_embedder, index_name=decision_index)

    def search_bm25(
        self,
        query: str,
        *,
        law_no: str | None = None,
        at: datetime | None = None,
    ) -> list[SearchHit]:
        return self.bm25.search(query, size=self.bm25_size, law_no=law_no, at=at)

    def search_semantic(
        self,
        query: str,
        *,
        law_no: str | None = None,
        at: datetime | None = None,
    ) -> list[SearchHit]:
        return self.semantic.search(query, size=self.semantic_size, law_no=law_no, at=at)

    def search_decision_bm25(self, query: str, *, at: datetime | None = None) -> list[SearchHit]:
        if self.decision_bm25 is None:
            return []
        try:
            return self.decision_bm25.search(query, size=self.bm25_size, at=at)
        except Exception as exc:
            if _missing_es_index(exc):
                return []
            raise

    def search_decision_semantic(self, query: str, *, at: datetime | None = None) -> list[SearchHit]:
        if self.decision_semantic is None:
            return []
        try:
            return self.decision_semantic.search(query, size=self.semantic_size, at=at)
        except Exception as exc:
            if _missing_es_index(exc):
                return []
            raise

    def fuse(
        self,
        query: str,
        bm25_hits: list[SearchHit],
        semantic_hits: list[SearchHit] | None,
        *,
        limit: int | None = None,
        decision_bm25_hits: list[SearchHit] | None = None,
        decision_semantic_hits: list[SearchHit] | None = None,
    ) -> list[FusedHit]:
        top_n = limit or self.limit
        pool = max(top_n * 3, top_n)
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

        ranked_lists: dict[str, list[SearchHit]] = {"bm25": bm25_hits, "semantic": semantic_hits or []}
        if decision_bm25_hits:
            ranked_lists["bm25_decisions"] = decision_bm25_hits
        if decision_semantic_hits:
            ranked_lists["semantic_decisions"] = decision_semantic_hits

        fused = reciprocal_rank_fusion(
            ranked_lists,
            k=self.rrf_k,
            limit=pool,
            weights=self._rrf_weights(list(ranked_lists)),
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

    def search(
        self,
        query: str,
        *,
        law_no: str | None = None,
        at: datetime | None = None,
        limit: int | None = None,
    ) -> list[FusedHit]:
        bm25_hits = self.search_bm25(query, law_no=law_no, at=at)
        if _is_exact_citation_query(query):
            return self.fuse(query, bm25_hits, [], limit=limit)
        semantic_hits = self.search_semantic(query, law_no=law_no, at=at)
        decision_bm25_hits: list[SearchHit] = []
        decision_semantic_hits: list[SearchHit] = []
        if law_no is None:
            decision_bm25_hits = self.search_decision_bm25(query, at=at)
            decision_semantic_hits = self.search_decision_semantic(query, at=at)
        return self.fuse(
            query,
            bm25_hits,
            semantic_hits,
            limit=limit,
            decision_bm25_hits=decision_bm25_hits,
            decision_semantic_hits=decision_semantic_hits,
        )

    def search_multi(
        self,
        queries: list[str],
        *,
        law_no: str | None = None,
        at: datetime | None = None,
        limit: int | None = None,
    ) -> list[FusedHit]:
        if len(queries) <= 1:
            return self.search(queries[0] if queries else "", law_no=law_no, at=at, limit=limit)
        ranked: dict[str, list[SearchHit]] = {}
        for i, query in enumerate(queries):
            ranked[f"bm25_{i}"] = self.search_bm25(query, law_no=law_no, at=at)
            if not _is_exact_citation_query(query):
                ranked[f"semantic_{i}"] = self.search_semantic(query, law_no=law_no, at=at)
        top_n = limit or self.limit
        pool = max(top_n * 3, top_n)
        fused = reciprocal_rank_fusion(
            ranked,
            k=self.rrf_k,
            limit=pool,
            weights=self._rrf_weights(list(ranked)),
        )
        return unique_by_article(fused, limit=top_n)

    def _rrf_weights(self, names: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for name in names:
            out[name] = self.bm25_weight if name.startswith("bm25") else self.dense_weight
        return out


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
