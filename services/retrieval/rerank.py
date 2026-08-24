from __future__ import annotations

import re
from dataclasses import replace

from retrieval.bm25 import extract_article_no
from retrieval.rrf import FusedHit


def _tokens(query: str, *, min_len: int = 4) -> list[str]:
    return [tok for tok in re.findall(r"\w+", query.lower(), flags=re.UNICODE) if len(tok) >= min_len]


def rerank_fused(query: str, fused: list[FusedHit], *, limit: int | None = None) -> list[FusedHit]:
    if not fused:
        return []
    tokens = _tokens(query)
    article = extract_article_no(query)
    scored: list[tuple[int, float, FusedHit]] = []
    for hit in fused:
        blob = f"{hit.hit.title or ''} {hit.hit.content or ''}".lower()
        overlap = sum(1 for tok in tokens if tok in blob)
        boost = 3 if article and str(hit.hit.article_no) == str(article) else 0
        scored.append((overlap + boost, float(hit.rrf_score), hit))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    top = scored[: limit or len(scored)]
    out: list[FusedHit] = []
    for rank, (_, _, hit) in enumerate(top, start=1):
        out.append(replace(hit, rank=rank))
    return out
