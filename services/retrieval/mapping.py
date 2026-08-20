from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

INDEX_NAME = "hakim-legal-chunks"


def embedding_dims() -> int:
    from hakim_config import get_models

    return get_models().embedding_dims


EMBEDDING_DIMS = 768


def index_settings(*, dims: int | None = None) -> dict[str, Any]:
    settings = copy.deepcopy(INDEX_SETTINGS)
    settings["mappings"]["properties"]["embedding"]["dims"] = int(dims or embedding_dims())
    return settings


def corpus_filters(*, law_no: str | None = None, at: datetime | None = None) -> list[dict[str, Any]]:
    """Restrict search to a law corpus while still including court decisions."""
    filters: list[dict[str, Any]] = []
    if law_no:
        filters.append(
            {
                "bool": {
                    "should": [
                        {"term": {"law_no": law_no}},
                        {"term": {"document_type": "court_decision"}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if at is not None:
        filters.append({"range": {"valid_from": {"lte": at.isoformat()}}})
        filters.append(
            {
                "bool": {
                    "should": [
                        {"bool": {"must_not": {"exists": {"field": "valid_until"}}}},
                        {"range": {"valid_until": {"gt": at.isoformat()}}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    return filters

INDEX_SETTINGS: dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "turkish_stop": {"type": "stop", "stopwords": "_turkish_"},
                "turkish_stemmer": {"type": "stemmer", "language": "turkish"},
            },
            "analyzer": {
                "hakim_turkish": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "turkish_stop", "turkish_stemmer", "asciifolding"],
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "article_id": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "law_no": {"type": "keyword"},
            "article_no": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "hakim_turkish",
                "fields": {"raw": {"type": "keyword"}},
            },
            "content": {"type": "text", "analyzer": "hakim_turkish"},
            "valid_from": {"type": "date"},
            "valid_until": {"type": "date"},
            "court": {"type": "keyword"},
            "authority": {"type": "keyword"},
            "source_provider": {"type": "keyword"},
            "version": {"type": "integer"},
            "indexed_at": {"type": "date"},
            "embedding": {
                "type": "dense_vector",
                "dims": EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "embedding_model": {"type": "keyword"},
        }
    },
}


def chunk_from_article_row(
    row: dict[str, Any],
    *,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> dict[str, Any]:
    """Build an ES document from a Postgres article_versions join row."""
    article_id = row["article_id"]
    version = int(row["version"])
    chunk_id = f"{article_id}:v{version}"
    valid_from: datetime | None = row.get("valid_from")
    valid_until: datetime | None = row.get("valid_until")
    doc: dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": row["document_id"],
        "article_id": article_id,
        "document_type": row.get("document_type") or "law",
        "law_no": row.get("law_no") or row.get("number"),
        "article_no": row["article_no"],
        "title": row.get("title"),
        "content": row["body"],
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_until": valid_until.isoformat() if valid_until else None,
        "court": row.get("court"),
        "authority": row.get("authority") or "official",
        "source_provider": row.get("source_provider") or "mevzuat.gov.tr",
        "version": version,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    if embedding is not None:
        doc["embedding"] = embedding
        doc["embedding_model"] = embedding_model or "unknown"
    return doc


def chunk_from_decision_row(
    row: dict[str, Any],
    *,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> dict[str, Any]:
    chunk_id = f"{row['id']}:v1"
    decision_date = row.get("decision_date")
    return chunk_from_article_row(
        {
            "article_id": row["id"],
            "document_id": row["id"],
            "article_no": row.get("decision_no"),
            "version": 1,
            "title": row.get("title"),
            "body": row.get("body") or "",
            "valid_from": decision_date,
            "valid_until": None,
            "document_type": "court_decision",
            "law_no": None,
            "source_provider": row.get("source_provider"),
            "authority": "official",
            "court": row.get("court_slug") or row.get("court_id"),
        },
        embedding=embedding,
        embedding_model=embedding_model,
    )
