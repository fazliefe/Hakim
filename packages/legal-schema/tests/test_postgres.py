from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg")

DATABASE_URL = os.environ.get(
    "HAKIM_DATABASE_URL",
    "postgresql://hakim:hakim@127.0.0.1:5433/hakim",
)


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


def test_seeded_official_source_exists(db) -> None:
    row = db.execute(
        "SELECT official, authority FROM sources WHERE id = %s",
        ("source:mevzuat.gov.tr",),
    ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] == "official"


def test_temporal_article_lookup_and_overlap_rejection(db) -> None:
    db.execute(
        """
        INSERT INTO legal_documents (id, document_type, number, title, source_id, publication_date, gazette_number)
        VALUES ('law:900001', 'law', '900001', 'Test Kanunu', 'source:mevzuat.gov.tr', '2004-10-12', '25611')
        """
    )
    db.execute(
        """
        INSERT INTO articles (id, document_id, article_no)
        VALUES ('law:900001:article:158', 'law:900001', '158')
        """
    )
    db.execute(
        """
        INSERT INTO article_versions (id, article_id, version, title, body, valid_from, valid_until)
        VALUES
          ('law:900001:article:158:v3', 'law:900001:article:158', 3, 'Test', 'v3 text',
           '2005-06-01T00:00:00Z', '2016-07-01T00:00:00Z'),
          ('law:900001:article:158:v4', 'law:900001:article:158', 4, 'Test', 'v4 text',
           '2016-07-01T00:00:00Z', NULL)
        """
    )

    historical = db.execute(
        "SELECT version, body FROM article_version_at(%s, %s)",
        ("law:900001:article:158", "2012-01-15T00:00:00Z"),
    ).fetchone()
    current = db.execute(
        "SELECT version, body FROM article_version_at(%s, %s)",
        ("law:900001:article:158", "2021-03-01T00:00:00Z"),
    ).fetchone()

    assert historical == (3, "v3 text")
    assert current == (4, "v4 text")

    with pytest.raises(psycopg.errors.ExclusionViolation):
        db.execute(
            """
            INSERT INTO article_versions (id, article_id, version, title, body, valid_from, valid_until)
            VALUES ('law:900001:article:158:v99', 'law:900001:article:158', 99, 'overlap', 'bad',
                    '2010-01-01T00:00:00Z', '2018-01-01T00:00:00Z')
            """
        )


def test_llm_relation_cannot_claim_full_confidence(db) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            """
            INSERT INTO legal_relations
              (from_id, from_type, to_id, to_type, relation_type, provenance, confidence)
            VALUES
              ('law:5237:article:158', 'article', 'decision:x', 'decision',
               'INTERPRETED_BY', 'llm_extracted', 1.0)
            """
        )
