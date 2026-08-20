#!/usr/bin/env python3
"""Fetch official court decisions (Yargıtay, Danıştay, AYM) into HAKİM."""

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

from courts.aym import AymClient
from courts.bedesten import BedestenClient
from ingestion.decision_writer import write_decisions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="dolandırıcılık")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--courts",
        default="yargitay,danistay,aym",
        help="Comma-separated: yargitay,danistay,aym,yerelhukuk,istinafhukuk,kyb",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument("--archive-root", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    wanted = {item.strip().lower() for item in args.courts.split(",") if item.strip()}

    bedesten = BedestenClient(archive_root=args.archive_root)
    aym = AymClient(archive_root=args.archive_root)

    with psycopg.connect(args.database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        bedesten_courts = (
            ("yargitay", "source:yargitay.gov.tr"),
            ("danistay", "source:danistay.gov.tr"),
            ("yerelhukuk", "source:emsal.uyap.gov.tr"),
            ("istinafhukuk", "source:emsal.uyap.gov.tr"),
            ("kyb", "source:emsal.uyap.gov.tr"),
        )
        for court, source_id in bedesten_courts:
            if court not in wanted:
                continue
            decisions = bedesten.ingest_hits(court=court, phrase=args.query, limit=args.limit)
            report = write_decisions(conn, decisions, source_id=source_id)
            conn.commit()
            print(
                f"{court}: status={report.status.value} fetched={report.articles_found} "
                f"warnings={report.warnings}"
            )
        if "aym" in wanted:
            try:
                aym_decisions = aym.ingest(args.query, limit=args.limit)
            except Exception as exc:
                print(f"aym: fetch failed ({exc})")
                aym_decisions = []
            report = write_decisions(conn, aym_decisions, source_id="source:anayasa.gov.tr")
            conn.commit()
            print(
                f"aym: status={report.status.value} fetched={report.articles_found} "
                f"warnings={report.warnings}"
            )


if __name__ == "__main__":
    main()
