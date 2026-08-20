from __future__ import annotations

from datetime import datetime
from typing import Any

from retrieval.bm25 import SearchHit
from retrieval.embeddings import Embedder
from retrieval.mapping import INDEX_NAME, corpus_filters


class SemanticSearcher:
    def __init__(
        self,
        es_client: Any,
        embedder: Embedder,
        *,
        index_name: str = INDEX_NAME,
    ) -> None:
        self.es = es_client
        self.embedder = embedder
        self.index_name = index_name

    def search(
        self,
        query: str,
        *,
        size: int = 50,
        law_no: str | None = None,
        at: datetime | None = None,
    ) -> list[SearchHit]:
        vector = self.embedder.embed([query])[0]
        filters: list[dict[str, Any]] = corpus_filters(law_no=law_no, at=at)

        knn: dict[str, Any] = {
            "field": "embedding",
            "query_vector": vector,
            "k": size,
            "num_candidates": max(100, size * 2),
        }
        if filters:
            knn["filter"] = {"bool": {"filter": filters}}

        response = self.es.search(index=self.index_name, knn=knn, size=size)
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
