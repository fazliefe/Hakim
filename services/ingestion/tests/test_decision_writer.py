from __future__ import annotations

from datetime import date

import pytest

psycopg = pytest.importorskip("psycopg")

from courts.bedesten import ParsedDecision
from ingestion.decision_writer import write_decisions

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
        # Testler gerçek verilere dokunmasın diye izole, sahte bir mahkeme +
        # kaynak satırı.
        conn.execute(
            "INSERT INTO sources (id, provider, official, authority, base_url) "
            "VALUES ('source:test_mahkeme', 'test.local', false, 'secondary', 'https://test.local') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO courts (id, slug, name) VALUES ('court:test_mahkeme', 'test_mahkeme', 'Test Mahkemesi') "
            "ON CONFLICT (id) DO NOTHING"
        )
        yield conn
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def _decision(**overrides) -> ParsedDecision:
    base = dict(
        id="decision:test_mahkeme:2026:100/1:200/1",
        court_slug="test_mahkeme",
        court_id="court:test_mahkeme",
        year=2026,
        docket_no="100/1",
        decision_no="200/1",
        decision_date=date(2026, 1, 15),
        title="Test Mahkemesi — 100/1 E. — 200/1 K.",
        body="Sanığın eylemi değerlendirilmiştir.",
        source_id="source:test_mahkeme",
        content_hash="deadbeef",
        provider_document_id="prov-1",
        raw_snapshot_uri=None,
        chamber="1. Ceza Dairesi",
    )
    base.update(overrides)
    return ParsedDecision(**base)


def test_write_decisions_inserts_row_with_chamber(db) -> None:
    report = write_decisions(db, [_decision()], source_id="source:test_mahkeme")
    assert report.articles_found == 1
    row = db.execute(
        "SELECT chamber, title FROM court_decisions WHERE id = %s",
        (_decision().id,),
    ).fetchone()
    assert row[0] == "1. Ceza Dairesi"
    assert "100/1" in row[1]


def test_write_decisions_upsert_updates_chamber(db) -> None:
    write_decisions(db, [_decision(chamber="1. Ceza Dairesi")], source_id="source:test_mahkeme")
    write_decisions(db, [_decision(chamber="2. Ceza Dairesi")], source_id="source:test_mahkeme")
    row = db.execute(
        "SELECT chamber FROM court_decisions WHERE id = %s",
        (_decision().id,),
    ).fetchone()
    assert row[0] == "2. Ceza Dairesi"


def test_write_decisions_issued_by_relation(db) -> None:
    write_decisions(db, [_decision()], source_id="source:test_mahkeme")
    row = db.execute(
        "SELECT 1 FROM legal_relations WHERE from_id = %s AND to_id = %s AND relation_type = 'ISSUED_BY'",
        ("court:test_mahkeme", _decision().id),
    ).fetchone()
    assert row is not None


def test_write_decisions_cites_correct_law_for_multi_law_body(db) -> None:
    """Adım 1 regresyon testi: karar hem TCK hem CMK maddesine atıf yapıyorsa
    her ikisi de kendi kanununa CITES ile bağlanmalı — eskiden sadece TCK
    (hardcoded) yakalanabiliyordu.

    write_decisions yalnızca ZATEN indekslenmiş maddelere CITES kuruyor
    (_known_articles_by_law), bu yüzden TCK m.141 ve CMK m.100'ü burada
    kendimiz seed ediyoruz — gerçek ortamda bunlar mevzuat ingestion'ından
    gelir, bu test onu varsaymadan kendi kendine yeterli olmalı.
    """
    for law_no, title, article_no in (
        ("5237", "Türk Ceza Kanunu", "141"),
        ("5271", "Ceza Muhakemesi Kanunu", "100"),
    ):
        db.execute(
            "INSERT INTO legal_documents (id, document_type, number, title, source_id) "
            "VALUES (%s, 'law', %s, %s, 'source:test_mahkeme') ON CONFLICT (id) DO NOTHING",
            (f"law:{law_no}", law_no, title),
        )
        db.execute(
            "INSERT INTO articles (id, document_id, article_no) VALUES (%s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (f"law:{law_no}:article:{article_no}", f"law:{law_no}", article_no),
        )
    body = (
        "Sanığın eylemi TCK'nın 141 inci maddesi kapsamında hırsızlık suçunu "
        "oluşturmaktadır. Tutuklama tedbiri CMK'nın 100 üncü maddesi uyarınca "
        "uygulanmıştır."
    )
    write_decisions(db, [_decision(body=body)], source_id="source:test_mahkeme")
    rows = db.execute(
        "SELECT to_id FROM legal_relations WHERE from_id = %s AND relation_type = 'CITES'",
        (_decision().id,),
    ).fetchall()
    to_ids = {row[0] for row in rows}
    assert "law:5237:article:141" in to_ids
    assert "law:5271:article:100" in to_ids


def test_write_decisions_skips_ambiguous_citations(db) -> None:
    """Kanun bağlamı belirsizse (kısaltma/numara yok) CITES hiç kurulmamalı."""
    body = "Sanığın eylemi 999999 inci maddesi kapsamında değerlendirilmiştir."
    write_decisions(db, [_decision(body=body)], source_id="source:test_mahkeme")
    rows = db.execute(
        "SELECT 1 FROM legal_relations WHERE from_id = %s AND relation_type = 'CITES'",
        (_decision().id,),
    ).fetchall()
    assert rows == []


def test_write_decisions_empty_list_reports_warning(db) -> None:
    report = write_decisions(db, [], source_id="source:test_mahkeme")
    assert report.articles_found == 0
    assert "no decisions fetched" in report.warnings
