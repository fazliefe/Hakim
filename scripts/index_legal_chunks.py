#!/usr/bin/env python3
"""Index current-in-force legal chunks from PostgreSQL into Elasticsearch."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "packages" / "legal-schema" / "src")]


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

from retrieval.embeddings import create_decision_embedder, create_embedder
from retrieval.es_client import create_es_client
from retrieval.indexer import LegalChunkIndexer
from retrieval.mapping import DECISION_INDEX_NAME, decision_index_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", default="law:5237")
    parser.add_argument("--all", action="store_true", help="Index every law in Postgres")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--decisions-only", action="store_true")
    parser.add_argument(
        "--skip-decisions",
        action="store_true",
        help="Sadece kanun maddelerini indeksle, karar index'ine dokunma",
    )
    parser.add_argument("--hash-embeddings", action="store_true")
    parser.add_argument("--pdf-laws", action="store_true", help="Also index data/raw/pdf_laws chunks.jsonl")
    parser.add_argument(
        "--pdf-laws-only",
        action="store_true",
        help="Index only OCR/PDF jsonl (skip Postgres)",
    )
    parser.add_argument(
        "--pdf-laws-root",
        type=Path,
        default=ROOT / "data" / "raw" / "pdf_laws",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument(
        "--es-url",
        default=os.environ.get("HAKIM_ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
    )
    args = parser.parse_args()

    embedder = create_embedder(prefer_neural=not args.hash_embeddings)
    es = create_es_client(args.es_url)
    indexer = LegalChunkIndexer(es, embedder=embedder)
    indexer.ensure_index(recreate=args.recreate)

    # Kararlar AYRI bir index'e (`hakim-court-decisions`) ve AYRI bir
    # embedder'a (Evren bge-m3-embed, 1024 dims) gider — kanun index'inin
    # 768-dim yerel modeliyle karışmaz, bkz. retrieval/mapping.py.
    decision_embedder = create_decision_embedder()
    decision_indexer = LegalChunkIndexer(
        es,
        index_name=DECISION_INDEX_NAME,
        embedder=decision_embedder,
        settings_builder=decision_index_settings,
    )
    decision_indexer.ensure_index(recreate=args.recreate)

    n = 0
    d = 0
    p = 0
    document_id = None if args.all else args.document_id
    if not args.pdf_laws_only:
        with psycopg.connect(args.database_url) as conn:
            conn.execute("SET search_path TO hakim, public")
            if not args.decisions_only:
                n = indexer.index_from_postgres(conn, document_id=document_id)
            if not args.skip_decisions:
                d = decision_indexer.index_decisions_from_postgres(conn)
    if args.pdf_laws or args.pdf_laws_only:
        p = indexer.index_pdf_law_jsonl(args.pdf_laws_root)

    model = getattr(embedder, "model_name", type(embedder).__name__)
    decision_model = getattr(decision_embedder, "model_name", type(decision_embedder).__name__)
    print(
        f"indexed_articles={n} indexed_decisions={d} indexed_pdf_laws={p} "
        f"index={indexer.index_name} document_id={document_id or 'all'} "
        f"embedder={model} dims={embedder.dims} "
        f"decision_index={decision_indexer.index_name} decision_embedder={decision_model} "
        f"decision_dims={decision_embedder.dims}"
    )


if __name__ == "__main__":
    main()
