"""Apply Legal Data Model SQL to a running PostgreSQL instance."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "infra" / "postgres" / "migrations"
DATABASE_URL = os.environ.get(
    "HAKIM_DATABASE_URL",
    "postgresql://hakim:hakim@127.0.0.1:5433/hakim",
)


def apply_file(conn, path: Path) -> None:
    conn.execute(path.read_text(encoding="utf-8"))
    print(f"applied {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Apply a single migration file name, e.g. 002_open_legal_sources.sql")
    args = parser.parse_args()
    files = sorted(SQL_DIR.glob("*.sql"))
    if args.only:
        files = [SQL_DIR / args.only]
        if not files[0].exists():
            raise FileNotFoundError(files[0])
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for path in files:
            apply_file(conn, path)
    print(f"applied {len(files)} migration(s) to {DATABASE_URL}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        sys.exit(1)
