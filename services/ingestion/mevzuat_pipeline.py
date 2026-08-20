from __future__ import annotations

from pathlib import Path

from mevzuat.client import MevzuatClient
from mevzuat.parser import parse_mevzuat_html

from ingestion.postgres_writer import write_parsed_law


def ingest_mevzuat_law(
    *,
    mevzuat_no: str,
    mevzuat_tur: int = 1,
    mevzuat_tertip: int | str = 5,
    conn,
    archive_root: str | Path = "data/raw",
    html: str | None = None,
    content_hash: str | None = None,
    raw_snapshot_uri: str | None = None,
):
    """Fetch (or accept) mevzuat HTML, parse, and write into PostgreSQL."""
    if html is None:
        client = MevzuatClient(archive_root=archive_root)
        snap = client.fetch_content(
            mevzuat_no=mevzuat_no,
            mevzuat_tur=mevzuat_tur,
            mevzuat_tertip=mevzuat_tertip,
        )
        html = snap.html
        content_hash = snap.content_hash
        raw_snapshot_uri = snap.content_path

    law = parse_mevzuat_html(
        html,
        law_number=str(mevzuat_no),
        content_hash=content_hash or "",
    )
    law.raw_snapshot_uri = raw_snapshot_uri
    return write_parsed_law(conn, law)
