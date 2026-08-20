from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from retrieval.mapping import INDEX_NAME, corpus_filters

ARTICLE_QUERY_RE = re.compile(
    r"(?:madde\s*)?([0-9]+(?:/[A-Z])?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: str
    score: float
    law_no: str | None
    article_no: str | None
    title: str | None
    content: str
    document_id: str | None
    article_id: str | None
    authority: str | None
    rank: int


LAW_HINTS = {
    "tck": "5237",
    "cmk": "5271",
    "iyuk": "2577",
    "i̇yuk": "2577",
    "tmk": "4721",
    "tbk": "6098",
    "iik": "2004",
    "i̇ik": "2004",
}


def parse_law_hint(query: str) -> str | None:
    blob = (query or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    match = re.search(r"\b(tck|cmk|iyuk|tmk|tbk|iik)\b", blob)
    if not match:
        return None
    return LAW_HINTS.get(match.group(1))


def extract_article_no(query: str) -> str | None:
    """Pull an article number hint from queries like 'Madde 158' or 'CMK m.158'."""
    lowered = query.strip()
    if re.fullmatch(r"[0-9]+(?:/[A-Z])?", lowered, flags=re.IGNORECASE):
        return lowered.upper() if "/" in lowered else lowered
    match = re.search(
        r"\b(?:tck|cmk|iyuk|tmk|tbk|iik|kanun)\s*(?:['’]nın)?\s*(?:m\.|madde)?\s*([0-9]+(?:/[A-Z])?)\b",
        lowered,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    match = re.search(r"\bmadde\s+([0-9]+(?:/[A-Z])?)\b", lowered, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\bm\.\s*([0-9]+(?:/[A-Z])?)\b", lowered, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


class Bm25Searcher:
    def __init__(self, es_client: Any, *, index_name: str = INDEX_NAME) -> None:
        self.es = es_client
        self.index_name = index_name

    def search(
        self,
        query: str,
        *,
        size: int = 10,
        law_no: str | None = None,
        at: datetime | None = None,
    ) -> list[SearchHit]:
        filters: list[dict[str, Any]] = corpus_filters(law_no=law_no, at=at)

        should: list[dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content"],
                    "type": "best_fields",
                }
            }
        ]
        article_no = extract_article_no(query)
        if article_no:
            should.append({"term": {"article_no": {"value": article_no, "boost": 50}}})

        body: dict[str, Any] = {
            "size": size,
            "query": {
                "bool": {
                    "should": should,
                    "minimum_should_match": 1,
                    "filter": filters,
                }
            },
        }
        response = self.es.search(index=self.index_name, body=body)
        hits: list[SearchHit] = []
        for i, hit in enumerate(response["hits"]["hits"], start=1):
            src = hit["_source"]
            hits.append(
                SearchHit(
                    chunk_id=src.get("chunk_id") or hit["_id"],
                    score=float(hit.get("_score") or 0.0),
                    law_no=src.get("law_no"),
                    article_no=src.get("article_no"),
                    title=src.get("title"),
                    content=src.get("content") or "",
                    document_id=src.get("document_id"),
                    article_id=src.get("article_id"),
                    authority=src.get("authority"),
                    rank=i,
                )
            )
        return hits
