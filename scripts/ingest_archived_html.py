#!/usr/bin/env python3
"""Load already-archived HTML (mevzuat + court snapshots) into PostgreSQL. No refetch, no OCR."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "connectors"),
    str(ROOT / "services"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

from courts.bedesten import SOURCE_IDS, ParsedDecision, html_to_text, parse_tr_date
from hakim_legal_schema.ids import court_id, decision_id
from ingestion.decision_writer import write_decisions
from ingestion.mevzuat_pipeline import ingest_mevzuat_law

MIGRATION_002 = ROOT / "infra" / "postgres" / "migrations" / "002_open_legal_sources.sql"
BEDESTEN_COURTS = ("yargitay", "danistay", "yerelhukuk", "istinafhukuk", "kyb")
MEVZUAT_LAWS = (("5237", 1, "5"), ("5271", 1, "5"))


def _latest_snapshot(doc_dir: Path) -> Path | None:
    dated = sorted((p for p in doc_dir.iterdir() if p.is_dir()), reverse=True)
    for folder in dated:
        if (folder / "content.html").exists() and (folder / "metadata.json").exists():
            return folder
    return None


def _decision_from_bedesten(court: str, snap: Path) -> ParsedDecision | None:
    meta = json.loads((snap / "metadata.json").read_text(encoding="utf-8"))
    html = (snap / "content.html").read_text(encoding="utf-8")
    hit = meta.get("hit") or {}
    document_id = str(meta.get("document_id") or hit.get("documentId") or snap.parent.name)
    esas = str(hit.get("esasNo") or f"{hit.get('esasNoYil') or ''}/{hit.get('esasNoSira') or document_id}")
    karar = str(hit.get("kararNo") or f"{hit.get('kararNoYil') or ''}/{hit.get('kararNoSira') or '0'}")
    year = int(hit.get("kararNoYil") or hit.get("esasNoYil") or 0) or 1970
    chamber = hit.get("birimAdi")
    title = " — ".join(part for part in [chamber, f"{esas} E.", f"{karar} K."] if part)
    body = html_to_text(html)
    if not body:
        return None
    content_hash = str(meta.get("content_hash") or "")
    return ParsedDecision(
        id=decision_id(court=court, year=year, docket=esas, decision_no=karar),
        court_slug=court,
        court_id=court_id(court),
        year=year,
        docket_no=esas,
        decision_no=karar,
        decision_date=parse_tr_date(hit.get("kararTarihiStr")),
        title=title,
        body=body,
        source_id=SOURCE_IDS[court],
        content_hash=content_hash,
        provider_document_id=document_id,
        raw_snapshot_uri=str(snap / "content.html"),
        chamber=chamber,
    )


def _decision_from_aym(snap: Path) -> ParsedDecision | None:
    meta = json.loads((snap / "metadata.json").read_text(encoding="utf-8"))
    html = (snap / "content.html").read_text(encoding="utf-8")
    hit = meta.get("hit") or {}
    docket = str(hit.get("basvuruNo") or snap.parent.name)
    raw_date = str(hit.get("kararTarihi") or "")[:10]
    karar_date = None
    if raw_date:
        try:
            karar_date = date.fromisoformat(raw_date)
        except ValueError:
            karar_date = None
    year = karar_date.year if karar_date else int(raw_date[:4] or "1970")
    title = str(hit.get("basvuruAdi") or docket)
    body = html_to_text(html)
    if not body:
        return None
    return ParsedDecision(
        id=decision_id(court="aym", year=year, docket=docket, decision_no=docket),
        court_slug="aym",
        court_id=court_id("aym"),
        year=year,
        docket_no=docket,
        decision_no=docket,
        decision_date=karar_date,
        title=title,
        body=body,
        source_id="source:anayasa.gov.tr",
        content_hash=str(meta.get("content_hash") or ""),
        provider_document_id=docket,
        raw_snapshot_uri=str(snap / "content.html"),
        chamber=hit.get("kararVerenBirimLabel"),
    )


def _load_court_archive(root: Path, court: str) -> list[ParsedDecision]:
    base = root / court
    if not base.exists():
        return []
    out: list[ParsedDecision] = []
    for doc_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        snap = _latest_snapshot(doc_dir)
        if snap is None:
            continue
        parsed = _decision_from_aym(snap) if court == "aym" else _decision_from_bedesten(court, snap)
        if parsed:
            out.append(parsed)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument("--archive-root", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()

    with psycopg.connect(args.database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        conn.execute(MIGRATION_002.read_text(encoding="utf-8"))
        conn.commit()
        print("applied 002_open_legal_sources.sql")

        for no, tur, tertip in MEVZUAT_LAWS:
            html_path = args.archive_root / "mevzuat" / no
            dated = _latest_snapshot(html_path) if html_path.exists() else None
            if dated is None:
                print(f"mevzuat {no}: SKIP no local HTML")
                continue
            html_file = dated / "content.html"
            html = html_file.read_text(encoding="utf-8")
            import hashlib

            report = ingest_mevzuat_law(
                mevzuat_no=no,
                mevzuat_tur=tur,
                mevzuat_tertip=tertip,
                conn=conn,
                archive_root=args.archive_root,
                html=html,
                content_hash=hashlib.sha256(html.encode("utf-8")).hexdigest(),
                raw_snapshot_uri=str(html_file),
            )
            conn.commit()
            print(
                f"mevzuat {no}: status={report.status.value} document_id={report.document_id} "
                f"articles={report.articles_found}"
            )

        for court in (*BEDESTEN_COURTS, "aym"):
            decisions = _load_court_archive(args.archive_root, court)
            source_id = "source:anayasa.gov.tr" if court == "aym" else SOURCE_IDS[court]
            report = write_decisions(conn, decisions, source_id=source_id)
            conn.commit()
            print(f"{court}: archived={len(decisions)} status={report.status.value} wrote={report.articles_found}")


if __name__ == "__main__":
    main()
