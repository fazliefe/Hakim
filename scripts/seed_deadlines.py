#!/usr/bin/env python3
"""Seed deterministic deadline rules into PostgreSQL."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "packages" / "legal-schema" / "src")]

from deadline.catalog import DEFAULT_RULES


def main() -> None:
    url = os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim")
    with psycopg.connect(url) as conn:
        conn.execute("SET search_path TO hakim, public")
        conn.execute(
            """
            INSERT INTO procedures (id, name, domain) VALUES
                ('procedure:ceza_sorusturma', 'Ceza soruşturması', 'ceza'),
                ('procedure:ceza_kovusturma', 'Ceza kovuşturması', 'ceza'),
                ('procedure:ceza_istinaf', 'Ceza istinaf', 'ceza'),
                ('procedure:anayasa_bireysel', 'Bireysel başvuru', 'anayasa')
            ON CONFLICT (id) DO NOTHING
            """
        )
        for rule in DEFAULT_RULES:
            conn.execute(
                """
                INSERT INTO deadline_rules
                    (id, procedure, trigger, duration, unit, calendar_type, legal_basis, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'official_text')
                ON CONFLICT (id) DO UPDATE SET
                    duration = EXCLUDED.duration,
                    legal_basis = EXCLUDED.legal_basis
                """,
                (
                    rule["id"],
                    rule["procedure"],
                    rule["trigger"],
                    rule["duration"],
                    rule["unit"].value,
                    rule["calendar"].value,
                    list(rule["legal_basis"]),
                ),
            )
        conn.commit()
        n = conn.execute("SELECT count(*) FROM deadline_rules").fetchone()[0]
    print(f"deadline_rules={n}")


if __name__ == "__main__":
    main()
