#!/usr/bin/env python3
"""Project a law from PostgreSQL into Neo4j legal knowledge graph."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "services"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

from graph.neo4j_client import create_neo4j_driver
from graph.projector import LegalGraphProjector


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", default="law:5237")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    args = parser.parse_args()

    driver = create_neo4j_driver()
    try:
        with psycopg.connect(args.database_url) as conn:
            conn.execute("SET search_path TO hakim, public")
            stats = LegalGraphProjector(driver).project_from_postgres(
                conn, document_id=args.document_id
            )
            conn.commit()
    finally:
        driver.close()

    print(
        f"projected document_id={args.document_id} "
        f"laws={stats['laws']} articles={stats['articles']} "
        f"has_article={stats['has_article']} references={stats['references']} "
        f"decisions={stats.get('decisions', 0)} cites={stats.get('cites', 0)}"
    )


if __name__ == "__main__":
    main()
