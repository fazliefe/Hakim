#!/usr/bin/env python3
"""Run a BM25 query against the HAKİM legal chunk index."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services")]

from retrieval.bm25 import Bm25Searcher
from retrieval.es_client import create_es_client


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--law-no", default=None)
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument(
        "--es-url",
        default=os.environ.get("HAKIM_ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
    )
    args = parser.parse_args()

    hits = Bm25Searcher(create_es_client(args.es_url)).search(
        args.query, size=args.size, law_no=args.law_no
    )
    for hit in hits:
        snippet = hit.content.replace("\n", " ")[:140]
        print(
            f"#{hit.rank} score={hit.score:.3f} "
            f"TCK/madde={hit.law_no}/{hit.article_no} title={hit.title!r}\n"
            f"    {snippet}"
        )


if __name__ == "__main__":
    main()
