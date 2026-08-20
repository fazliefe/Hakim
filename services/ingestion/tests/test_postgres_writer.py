from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from mevzuat.parser import ParsedArticle, ParsedLaw
from ingestion.postgres_writer import write_parsed_law

DATABASE_URL = "postgresql://hakim:hakim@127.0.0.1:5433/hakim"


def _connect():
    try:
        conn = psycopg.connect(DATABASE_URL, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    conn.execute("SET search_path TO hakim, public")
    return conn


@pytest.fixture
def db():
    conn = _connect()
    conn.execute("BEGIN")
    try:
        yield conn
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def test_write_parsed_law_inserts_articles(db) -> None:
    law = ParsedLaw(
        id="law:900002",
        number="900002",
        title="Test Kanunu",
        publication_date=date(2004, 10, 12),
        gazette_number="25611",
        content_hash="abc",
        articles=[
            ParsedArticle(
                id="law:900002:article:158",
                version_id="law:900002:article:158:v1",
                article_no="158",
                title="Nitelikli dolandırıcılık",
                text="Madde 158- (1) ...",
                version=1,
                valid_from=datetime(2004, 10, 12, tzinfo=timezone.utc),
            )
        ],
        raw_snapshot_uri="file://raw/mevzuat/900002/test/content.html",
    )
    report = write_parsed_law(db, law, source_id="source:mevzuat.gov.tr")
    count = db.execute(
        "SELECT count(*) FROM article_versions WHERE article_id = %s",
        ("law:900002:article:158",),
    ).fetchone()[0]
    assert count == 1
    assert report.articles_found == 1
    assert report.document_id == "law:900002"
    assert report.status.value == "success"
