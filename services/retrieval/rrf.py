from __future__ import annotations

from dataclasses import dataclass

from retrieval.bm25 import SearchHit


@dataclass(frozen=True, slots=True)
class FusedHit:
    chunk_id: str
    rrf_score: float
    rank: int
    sources: tuple[str, ...]
    hit: SearchHit
    bm25_rank: int | None = None
    semantic_rank: int | None = None


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[SearchHit]],
    *,
    k: int = 60,
    limit: int = 30,
) -> list[FusedHit]:
    """Classic RRF: score(d) = sum 1 / (k + rank_i(d))."""
    scores: dict[str, float] = {}
    best_hit: dict[str, SearchHit] = {}
    sources: dict[str, set[str]] = {}
    ranks: dict[str, dict[str, int]] = {}

    for source_name, hits in ranked_lists.items():
        for hit in hits:
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + hit.rank)
            sources.setdefault(hit.chunk_id, set()).add(source_name)
            ranks.setdefault(hit.chunk_id, {})[source_name] = hit.rank
            prev = best_hit.get(hit.chunk_id)
            if prev is None or hit.score > prev.score:
                best_hit[hit.chunk_id] = hit

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    fused: list[FusedHit] = []
    for i, (chunk_id, score) in enumerate(ordered, start=1):
        fused.append(
            FusedHit(
                chunk_id=chunk_id,
                rrf_score=score,
                rank=i,
                sources=tuple(sorted(sources[chunk_id])),
                hit=best_hit[chunk_id],
                bm25_rank=ranks[chunk_id].get("bm25"),
                semantic_rank=ranks[chunk_id].get("semantic"),
            )
        )
    return fused
