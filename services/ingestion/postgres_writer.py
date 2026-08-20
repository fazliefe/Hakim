from __future__ import annotations

import json
from datetime import datetime, timezone

from hakim_legal_schema.enums import IngestionStatus
from hakim_legal_schema.ingestion import IngestionReport
from mevzuat.parser import ParsedLaw


def write_parsed_law(conn, law: ParsedLaw, *, source_id: str = "source:mevzuat.gov.tr") -> IngestionReport:
    """Upsert a parsed law and its article versions into PostgreSQL."""
    warnings: list[str] = []
    now = datetime.now(timezone.utc)
    pub = (
        law.articles[0].valid_from
        if law.articles
        else datetime(law.publication_date.year, law.publication_date.month, law.publication_date.day, tzinfo=timezone.utc)
    )

    existing = conn.execute(
        """
        SELECT id, version, content_hash
        FROM document_versions
        WHERE document_id = %s
        ORDER BY version DESC
        LIMIT 1
        """,
        (law.id,),
    ).fetchone()
    content_changed = existing is None or existing[2] != (law.content_hash or "unknown")

    conn.execute(
        """
        INSERT INTO legal_documents (id, document_type, number, title, source_id, publication_date, gazette_number, updated_at)
        VALUES (%s, 'law', %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            publication_date = EXCLUDED.publication_date,
            gazette_number = EXCLUDED.gazette_number,
            updated_at = EXCLUDED.updated_at
        """,
        (law.id, law.number, law.title, source_id, law.publication_date, law.gazette_number, now),
    )

    if existing is None:
        doc_version = 1
        doc_version_id = f"{law.id}:v1"
        valid_from = pub
        conn.execute(
            """
            INSERT INTO document_versions
                (id, document_id, version, valid_from, valid_until, content_hash, raw_snapshot_uri)
            VALUES (%s, %s, %s, %s, NULL, %s, %s)
            """,
            (doc_version_id, law.id, doc_version, valid_from, law.content_hash or "unknown", law.raw_snapshot_uri),
        )
    elif content_changed:
        doc_version = int(existing[1]) + 1
        doc_version_id = f"{law.id}:v{doc_version}"
        valid_from = now
        conn.execute(
            """
            UPDATE document_versions
            SET valid_until = %s
            WHERE id = %s AND valid_until IS NULL AND valid_from < %s
            """,
            (valid_from, existing[0], valid_from),
        )
        conn.execute(
            """
            INSERT INTO document_versions
                (id, document_id, version, valid_from, valid_until, content_hash, raw_snapshot_uri)
            VALUES (%s, %s, %s, %s, NULL, %s, %s)
            """,
            (doc_version_id, law.id, doc_version, valid_from, law.content_hash or "unknown", law.raw_snapshot_uri),
        )
    else:
        doc_version = int(existing[1])
        doc_version_id = existing[0]
        valid_from = pub
        conn.execute(
            "UPDATE document_versions SET raw_snapshot_uri = %s WHERE id = %s",
            (law.raw_snapshot_uri, doc_version_id),
        )

    for article in law.articles:
        article_version = doc_version
        version_id = f"{article.id}:v{article_version}"
        conn.execute(
            """
            INSERT INTO articles (id, document_id, article_no)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (article.id, law.id, article.article_no),
        )
        # Close previous open article version when creating a new document version.
        if content_changed and existing is not None:
            conn.execute(
                """
                UPDATE article_versions
                SET valid_until = %s
                WHERE article_id = %s AND valid_until IS NULL AND valid_from < %s
                """,
                (valid_from, article.id, valid_from),
            )
        conn.execute(
            """
            INSERT INTO article_versions
                (id, article_id, document_version_id, version, title, body, valid_from, valid_until)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                document_version_id = EXCLUDED.document_version_id
            """,
            (
                version_id,
                article.id,
                doc_version_id,
                article_version,
                article.title,
                article.text,
                valid_from if (content_changed and existing is not None) else article.valid_from,
            ),
        )
        conn.execute(
            """
            INSERT INTO legal_relations
                (from_id, from_type, to_id, to_type, relation_type, provenance, confidence)
            VALUES (%s, 'law', %s, 'article', 'HAS_ARTICLE', 'official_text', 1.0)
            ON CONFLICT (from_id, to_id, relation_type, provenance) DO NOTHING
            """,
            (law.id, article.id),
        )

    if not law.articles:
        warnings.append("no articles found")

    report = IngestionReport(
        source="mevzuat",
        document_id=law.id,
        status=IngestionStatus.SUCCESS if law.articles else IngestionStatus.PARTIAL,
        articles_found=len(law.articles),
        warnings=warnings,
        content_changed=content_changed,
        parser_version="mevzuat-html-v1",
        raw_snapshot_uri=law.raw_snapshot_uri,
    )
    conn.execute(
        """
        INSERT INTO ingestion_runs
            (source_id, document_id, status, articles_found, warnings, content_changed, parser_version, raw_snapshot_uri, finished_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        """,
        (
            source_id,
            law.id,
            report.status.value,
            report.articles_found,
            json.dumps(warnings),
            report.content_changed,
            report.parser_version,
            report.raw_snapshot_uri,
            now,
        ),
    )
    return report
