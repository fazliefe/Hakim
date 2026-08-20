#!/usr/bin/env python3
"""Ingest a single mevzuat.gov.tr law into HAKİM PostgreSQL (default: TCK 5237)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "connectors"),
    str(ROOT / "services"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

from ingestion.mevzuat_pipeline import ingest_mevzuat_law


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest mevzuat law into HAKİM")
    parser.add_argument("--mevzuat-no", default="5237")
    parser.add_argument("--mevzuat-tur", type=int, default=1)
    parser.add_argument("--mevzuat-tertip", default="5")
    parser.add_argument("--html", type=Path, default=None, help="Use local HTML instead of network fetch")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument("--archive-root", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()

    html = None
    content_hash = None
    raw_uri = None
    if args.html:
        html = args.html.read_text(encoding="utf-8")
        import hashlib

        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        raw_uri = str(args.html)

    with psycopg.connect(args.database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        report = ingest_mevzuat_law(
            mevzuat_no=args.mevzuat_no,
            mevzuat_tur=args.mevzuat_tur,
            mevzuat_tertip=args.mevzuat_tertip,
            conn=conn,
            archive_root=args.archive_root,
            html=html,
            content_hash=content_hash,
            raw_snapshot_uri=raw_uri,
        )
        conn.commit()

    print(
        f"status={report.status.value} document_id={report.document_id} "
        f"articles={report.articles_found} content_changed={report.content_changed} "
        f"warnings={report.warnings}"
    )


if __name__ == "__main__":
    main()
