from __future__ import annotations

import json
from datetime import datetime, timezone

from hakim_legal_schema.enums import IngestionStatus, ProvenanceKind, RelationType
from hakim_legal_schema.ids import article_id
from hakim_legal_schema.ingestion import IngestionReport

from courts.bedesten import ParsedDecision
from graph.citations import extract_article_citations


def write_decisions(
    conn,
    decisions: list[ParsedDecision],
    *,
    source_id: str,
    cite_law_no: str = "5237",
) -> IngestionReport:
    warnings: list[str] = []
    now = datetime.now(timezone.utc)
    known_articles = {
        row[0]
        for row in conn.execute(
            "SELECT article_no FROM articles WHERE document_id = %s",
            (f"law:{cite_law_no}",),
        ).fetchall()
    }
    written = 0
    last_id = source_id
    for decision in decisions:
        last_id = decision.id
        conn.execute(
            """
            INSERT INTO court_decisions
                (id, court_id, year, docket_no, decision_no, decision_date, title, body, source_id, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (court_id, year, docket_no, decision_no) DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                decision_date = EXCLUDED.decision_date,
                content_hash = EXCLUDED.content_hash
            """,
            (
                decision.id,
                decision.court_id,
                decision.year,
                decision.docket_no,
                decision.decision_no,
                decision.decision_date,
                decision.title,
                decision.body,
                decision.source_id,
                decision.content_hash,
            ),
        )
        conn.execute(
            """
            INSERT INTO legal_relations
                (from_id, from_type, to_id, to_type, relation_type, provenance, confidence)
            VALUES (%s, 'court', %s, 'decision', 'ISSUED_BY', 'official_text', 1.0)
            ON CONFLICT (from_id, to_id, relation_type, provenance) DO NOTHING
            """,
            (decision.court_id, decision.id),
        )
        cites = extract_article_citations(decision.body or "", from_article_no="_")
        for cite in cites:
            if cite.to_article_no not in known_articles:
                continue
            conn.execute(
                """
                INSERT INTO legal_relations
                    (from_id, from_type, to_id, to_type, relation_type, provenance, confidence)
                VALUES (%s, 'decision', %s, 'article', 'CITES', 'official_text', 1.0)
                ON CONFLICT (from_id, to_id, relation_type, provenance) DO NOTHING
                """,
                (decision.id, article_id(cite_law_no, cite.to_article_no)),
            )
        written += 1

    if not decisions:
        warnings.append("no decisions fetched")

    report = IngestionReport(
        source=source_id,
        document_id=last_id,
        status=IngestionStatus.SUCCESS if written else IngestionStatus.PARTIAL,
        articles_found=written,
        warnings=warnings,
        content_changed=True,
        parser_version="court-html-v1",
        raw_snapshot_uri=decisions[0].raw_snapshot_uri if decisions else None,
    )
    conn.execute(
        """
        INSERT INTO ingestion_runs
            (source_id, document_id, status, articles_found, warnings, content_changed, parser_version, raw_snapshot_uri, finished_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        """,
        (
            source_id,
            report.document_id,
            report.status.value,
            report.articles_found,
            json.dumps(warnings, ensure_ascii=False),
            True,
            report.parser_version,
            report.raw_snapshot_uri,
            now,
        ),
    )
    return report
