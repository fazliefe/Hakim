#!/usr/bin/env python3
"""Ingest official open-legal sources listed in the TEKNOFEST catalog."""

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

from agencies.listings import AgencyClient
from courts.bedesten import BedestenClient, SOURCE_IDS
from ingestion.decision_writer import write_decisions

MIGRATION = ROOT / "infra" / "postgres" / "migrations" / "002_open_legal_sources.sql"


def _write(conn, label: str, decisions, source_id: str) -> None:
    report = write_decisions(conn, decisions, source_id=source_id)
    conn.commit()
    print(
        f"{label}: status={report.status.value} fetched={report.articles_found} "
        f"warnings={report.warnings}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="dolandırıcılık")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument("--archive-root", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument(
        "--skip-bedesten",
        action="store_true",
        help="Skip UYAP Emsal (yerel / istinaf / KYB) Bedesten pulls",
    )
    args = parser.parse_args()

    with psycopg.connect(args.database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        conn.execute(MIGRATION.read_text(encoding="utf-8"))
        conn.commit()
        print("applied 002_open_legal_sources.sql")

        if not args.skip_bedesten:
            bedesten = BedestenClient(archive_root=args.archive_root)
            for court in ("yerelhukuk", "istinafhukuk", "kyb"):
                try:
                    decisions = bedesten.ingest_hits(court=court, phrase=args.query, limit=args.limit)
                except Exception as exc:
                    print(f"{court}: fetch failed ({exc})")
                    decisions = []
                _write(conn, court, decisions, SOURCE_IDS[court])

        agencies = AgencyClient(archive_root=args.archive_root)
        jobs = [
            ("rekabet", agencies.ingest_rekabet, "source:rekabet.gov.tr"),
            ("kvkk", agencies.ingest_kvkk, "source:kvkk.gov.tr"),
            ("uyusmazlik", agencies.ingest_uyusmazlik, "source:uyusmazlik.gov.tr"),
            ("resmi_gazete", agencies.ingest_resmi_gazete, "source:resmigazete.gov.tr"),
            ("tbmm", agencies.ingest_tbmm, "source:tbmm.gov.tr"),
            ("sayistay", agencies.ingest_sayistay, "source:sayistay.gov.tr"),
        ]
        for label, fn, source_id in jobs:
            try:
                limit = 1 if label == "tbmm" else args.limit
                decisions = fn(limit=limit)
            except Exception as exc:
                print(f"{label}: fetch failed ({exc})")
                decisions = []
            _write(conn, label, decisions, source_id)


if __name__ == "__main__":
    main()
