#!/usr/bin/env python3
"""Hybrid BM25 + semantic search with RRF fusion."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services")]

from retrieval.embeddings import create_embedder
from retrieval.es_client import create_es_client
from retrieval.hybrid import HybridSearcher


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--law-no", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--hash-embeddings", action="store_true", help="Force offline HashingEmbedder")
    parser.add_argument(
        "--es-url",
        default=os.environ.get("HAKIM_ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
    )
    args = parser.parse_args()

    embedder = create_embedder(prefer_neural=not args.hash_embeddings)
    fused = HybridSearcher(create_es_client(args.es_url), embedder, limit=args.limit).search(
        args.query, law_no=args.law_no, limit=args.limit
    )
    for hit in fused:
        snippet = hit.hit.content.replace("\n", " ")[:140]
        print(
            f"#{hit.rank} rrf={hit.rrf_score:.5f} "
            f"bm25={hit.bm25_rank} sem={hit.semantic_rank} "
            f"src={'+'.join(hit.sources)} "
            f"{hit.hit.law_no}/{hit.hit.article_no} {hit.hit.title!r}\n"
            f"    {snippet}"
        )


if __name__ == "__main__":
    main()
