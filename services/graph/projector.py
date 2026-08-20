from __future__ import annotations

from typing import Any

from hakim_legal_schema.enums import ProvenanceKind, RelationType
from hakim_legal_schema.ids import article_id, law_id
from hakim_legal_schema.relations import LegalRelation

from graph.citations import citations_to_relations, extract_article_citations
from graph.neo4j_client import ensure_schema

ARTICLE_SQL = """
SELECT
    a.id AS article_id,
    a.document_id,
    a.article_no,
    av.title,
    av.body,
    ld.number AS law_no,
    ld.title AS law_title
FROM article_versions av
JOIN articles a ON a.id = av.article_id
JOIN legal_documents ld ON ld.id = a.document_id
WHERE av.valid_until IS NULL
  AND (%s::text IS NULL OR a.document_id = %s)
ORDER BY a.article_no
"""

DECISION_SQL = """
SELECT
    cd.id,
    cd.title,
    cd.year,
    cd.docket_no,
    cd.decision_no,
    c.id AS court_id,
    c.slug AS court_slug,
    c.name AS court_name
FROM court_decisions cd
JOIN courts c ON c.id = cd.court_id
"""

RELATION_SQL = """
SELECT from_id, to_id, relation_type
FROM legal_relations
WHERE relation_type IN ('CITES', 'ISSUED_BY')
"""


class LegalGraphProjector:
    """Project laws/articles/HAS_ARTICLE/REFERENCES into Neo4j + Postgres relations."""

    def __init__(self, neo4j_driver: Any) -> None:
        self.driver = neo4j_driver

    def project_from_postgres(
        self,
        conn,
        *,
        document_id: str | None = None,
        persist_postgres_relations: bool = True,
    ) -> dict[str, int]:
        ensure_schema(self.driver)
        rows = conn.execute(ARTICLE_SQL, (document_id, document_id)).fetchall()
        cols = [
            "article_id",
            "document_id",
            "article_no",
            "title",
            "body",
            "law_no",
            "law_title",
        ]
        articles = [dict(zip(cols, row, strict=True)) for row in rows]
        if not articles:
            return {
                "laws": 0,
                "articles": 0,
                "has_article": 0,
                "references": 0,
                **self._project_decisions(conn),
            }

        law_no = str(articles[0]["law_no"])
        law_node_id = law_id(law_no)
        law_title = articles[0]["law_title"]

        relations: list[LegalRelation] = []
        for article in articles:
            relations.append(
                LegalRelation(
                    from_id=law_node_id,
                    from_type="law",
                    to_id=article["article_id"],
                    to_type="article",
                    relation_type=RelationType.HAS_ARTICLE,
                    provenance=ProvenanceKind.OFFICIAL_TEXT,
                    confidence=1.0,
                )
            )
            cites = extract_article_citations(article["body"] or "", from_article_no=article["article_no"])
            # Keep only citations to articles that exist in this law snapshot.
            known = {a["article_no"] for a in articles}
            cites = [c for c in cites if c.to_article_no in known]
            relations.extend(citations_to_relations(cites, law_number=law_no))

        self._upsert_neo4j(law_node_id, law_no, law_title, articles, relations)
        decision_stats = self._project_decisions(conn)

        if persist_postgres_relations:
            self._upsert_postgres_relations(conn, relations)

        return {
            "laws": 1,
            "articles": len(articles),
            "has_article": sum(1 for r in relations if r.relation_type == RelationType.HAS_ARTICLE),
            "references": sum(1 for r in relations if r.relation_type == RelationType.REFERENCES),
            **decision_stats,
        }

    def _upsert_neo4j(
        self,
        law_node_id: str,
        law_no: str,
        law_title: str,
        articles: list[dict[str, Any]],
        relations: list[LegalRelation],
    ) -> None:
        with self.driver.session() as session:
            session.run(
                """
                MERGE (l:Law {id: $id})
                SET l.number = $number, l.title = $title
                """,
                id=law_node_id,
                number=law_no,
                title=law_title,
            )
            for article in articles:
                session.run(
                    """
                    MERGE (a:Article {id: $id})
                    SET a.article_no = $article_no,
                        a.title = $title,
                        a.law_id = $law_id
                    WITH a
                    MATCH (l:Law {id: $law_id})
                    MERGE (l)-[r:HAS_ARTICLE]->(a)
                    SET r.provenance = 'official_text', r.confidence = 1.0
                    """,
                    id=article["article_id"],
                    article_no=article["article_no"],
                    title=article.get("title"),
                    law_id=law_node_id,
                )
            for rel in relations:
                if rel.relation_type != RelationType.REFERENCES:
                    continue
                session.run(
                    """
                    MATCH (a:Article {id: $from_id})
                    MATCH (b:Article {id: $to_id})
                    MERGE (a)-[r:REFERENCES]->(b)
                    SET r.provenance = $provenance, r.confidence = $confidence
                    """,
                    from_id=rel.from_id,
                    to_id=rel.to_id,
                    provenance=rel.provenance.value,
                    confidence=float(rel.confidence),
                )

    def _project_decisions(self, conn) -> dict[str, int]:
        decision_rows = conn.execute(DECISION_SQL).fetchall()
        decision_cols = [
            "id",
            "title",
            "year",
            "docket_no",
            "decision_no",
            "court_id",
            "court_slug",
            "court_name",
        ]
        decisions = [dict(zip(decision_cols, row, strict=True)) for row in decision_rows]
        rel_rows = conn.execute(RELATION_SQL).fetchall()
        issued = [(row[0], row[1]) for row in rel_rows if row[2] == "ISSUED_BY"]
        cites = [(row[0], row[1]) for row in rel_rows if row[2] == "CITES"]
        with self.driver.session() as session:
            for decision in decisions:
                session.run(
                    """
                    MERGE (c:Court {id: $id})
                    SET c.slug = $slug, c.name = $name
                    """,
                    id=decision["court_id"],
                    slug=decision["court_slug"],
                    name=decision["court_name"],
                )
                session.run(
                    """
                    MERGE (d:Decision {id: $id})
                    SET d.title = $title,
                        d.year = $year,
                        d.docket_no = $docket_no,
                        d.decision_no = $decision_no,
                        d.court_id = $court_id
                    """,
                    id=decision["id"],
                    title=decision.get("title"),
                    year=decision.get("year"),
                    docket_no=decision.get("docket_no"),
                    decision_no=decision.get("decision_no"),
                    court_id=decision["court_id"],
                )
            for from_id, to_id in issued:
                session.run(
                    """
                    MATCH (c:Court {id: $from_id})
                    MATCH (d:Decision {id: $to_id})
                    MERGE (c)-[r:ISSUED_BY]->(d)
                    SET r.provenance = 'official_text', r.confidence = 1.0
                    """,
                    from_id=from_id,
                    to_id=to_id,
                )
            for from_id, to_id in cites:
                session.run(
                    """
                    MATCH (d:Decision {id: $from_id})
                    MATCH (a:Article {id: $to_id})
                    MERGE (d)-[r:CITES]->(a)
                    SET r.provenance = 'official_text', r.confidence = 1.0
                    """,
                    from_id=from_id,
                    to_id=to_id,
                )
        return {
            "decisions": len(decisions),
            "issued_by": len(issued),
            "cites": len(cites),
        }

    def _upsert_postgres_relations(self, conn, relations: list[LegalRelation]) -> None:
        for rel in relations:
            if rel.relation_type == RelationType.HAS_ARTICLE:
                continue  # already written during ingest
            conn.execute(
                """
                INSERT INTO legal_relations
                    (from_id, from_type, to_id, to_type, relation_type, provenance, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (from_id, to_id, relation_type, provenance) DO UPDATE SET
                    confidence = EXCLUDED.confidence
                """,
                (
                    rel.from_id,
                    rel.from_type,
                    rel.to_id,
                    rel.to_type,
                    rel.relation_type.value,
                    rel.provenance.value,
                    rel.confidence,
                ),
            )


def neighborhood(driver: Any, article_node_id: str, *, depth: int = 1) -> dict[str, Any]:
    """Return article neighborhood for UI / retrieval signal."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Article {id: $id})
            OPTIONAL MATCH (a)-[r:REFERENCES]->(out:Article)
            OPTIONAL MATCH (inn:Article)-[rin:REFERENCES]->(a)
            OPTIONAL MATCH (l:Law)-[:HAS_ARTICLE]->(a)
            OPTIONAL MATCH (d:Decision)-[:CITES]->(a)
            RETURN a.id AS id, a.article_no AS article_no, a.title AS title,
                   l.id AS law_id,
                   collect(DISTINCT {id: out.id, article_no: out.article_no, title: out.title, direction: 'out', kind: 'article'}) AS outs,
                   collect(DISTINCT {id: inn.id, article_no: inn.article_no, title: inn.title, direction: 'in', kind: 'article'})
                     + collect(DISTINCT {id: d.id, article_no: d.decision_no, title: d.title, direction: 'in', kind: 'decision'}) AS ins
            """,
            id=article_node_id,
        )
        record = result.single()
        if record is None:
            return {"id": article_node_id, "neighbors": []}
        neighbors = [n for n in (record["outs"] + record["ins"]) if n.get("id")]
        return {
            "id": record["id"],
            "article_no": record["article_no"],
            "title": record["title"],
            "law_id": record["law_id"],
            "neighbors": neighbors,
            "depth": depth,
        }


def neighborhood_decision(driver: Any, decision_id: str, *, depth: int = 1) -> dict[str, Any]:
    """Return articles cited by a court decision."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Decision {id: $id})
            OPTIONAL MATCH (d)-[:CITES]->(a:Article)
            OPTIONAL MATCH (c:Court)-[:ISSUED_BY]->(d)
            RETURN d.id AS id, d.decision_no AS decision_no, d.title AS title,
                   c.id AS court_id,
                   collect(DISTINCT {id: a.id, article_no: a.article_no, title: a.title, direction: 'out', kind: 'article'}) AS cites
            """,
            id=decision_id,
        )
        record = result.single()
        if record is None:
            return {"id": decision_id, "neighbors": []}
        return {
            "id": record["id"],
            "article_no": record["decision_no"],
            "title": record["title"],
            "court_id": record["court_id"],
            "neighbors": [n for n in record["cites"] if n.get("id")],
            "depth": depth,
        }


def dump_graph(driver: Any) -> dict[str, Any]:
    """Return the full Neo4j legal graph for visualization."""
    with driver.session() as session:
        node_rows = session.run(
            """
            MATCH (n)
            WHERE n.id IS NOT NULL
            RETURN n.id AS id,
                   labels(n) AS labels,
                   n.article_no AS article_no,
                   n.title AS title,
                   n.decision_no AS decision_no,
                   n.number AS number,
                   n.name AS name
            """
        )
        nodes: list[dict[str, Any]] = []
        for rec in node_rows:
            labels = list(rec["labels"] or [])
            if "Article" in labels:
                kind = "article"
            elif "Decision" in labels:
                kind = "decision"
            elif "Law" in labels:
                kind = "law"
            elif "Court" in labels:
                kind = "court"
            else:
                kind = "other"
            node_id = str(rec["id"])
            if kind == "article":
                code = "TCK" if ":5237:" in node_id else "CMK" if ":5271:" in node_id else "m."
                label = f"{code} {rec['article_no']}" if rec["article_no"] else node_id
            elif kind == "law":
                number = str(rec["number"] or "")
                label = "TCK" if number == "5237" or node_id.endswith("5237") else "CMK" if number == "5271" or node_id.endswith("5271") else number or node_id
            elif kind == "decision":
                title = str(rec["title"] or rec["decision_no"] or node_id)
                label = title[:22] + ("…" if len(title) > 22 else "")
            else:
                label = str(rec["name"] or rec["title"] or node_id)
            nodes.append(
                {
                    "id": node_id,
                    "label": label,
                    "kind": kind,
                    "title": rec["title"] or rec["name"] or label,
                    "article_no": rec["article_no"],
                }
            )
        edge_rows = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE a.id IS NOT NULL AND b.id IS NOT NULL
            RETURN a.id AS source, b.id AS target, type(r) AS type
            """
        )
        edges = [
            {"source": rec["source"], "target": rec["target"], "label": rec["type"]}
            for rec in edge_rows
        ]
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node["kind"]] = counts.get(node["kind"], 0) + 1
    return {"nodes": nodes, "edges": edges, "counts": counts}
