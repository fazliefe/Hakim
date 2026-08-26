from __future__ import annotations

from hakim_legal_schema.enums import ProvenanceKind, RelationType
from hakim_legal_schema.relations import LegalRelation

from graph.projector import LegalGraphProjector


class FakeResult:
    def __init__(self, record=None) -> None:
        self._record = record

    def single(self):
        return self._record


class FakeSession:
    def __init__(self, store: dict) -> None:
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, query: str, **params):
        q = " ".join(query.split())
        if "CONSTRAINT" in q:
            return FakeResult()
        if "MERGE (l:Law" in q:
            self.store.setdefault("laws", {})[params["id"]] = params
            return FakeResult()
        if "MERGE (a:Article" in q:
            self.store.setdefault("articles", {})[params["id"]] = params
            self.store.setdefault("has_article", []).append((params["law_id"], params["id"]))
            return FakeResult()
        if "MERGE (a)-[r:REFERENCES]->(b)" in q:
            self.store.setdefault("references", []).append((params["from_id"], params["to_id"]))
            return FakeResult()
        if "MERGE (c:Court" in q:
            self.store.setdefault("courts", {})[params["id"]] = params
            return FakeResult()
        if "MERGE (d:Decision" in q:
            self.store.setdefault("decisions", {})[params["id"]] = params
            return FakeResult()
        if "MERGE (c)-[r:ISSUED_BY]->(d)" in q:
            self.store.setdefault("issued_by", []).append((params["from_id"], params["to_id"]))
            return FakeResult()
        if "MERGE (d)-[r:CITES]->(a)" in q:
            self.store.setdefault("cites", []).append((params["from_id"], params["to_id"]))
            return FakeResult()
        if "OPTIONAL MATCH (d:Decision)-[:CITES]->(a)" in q or "MATCH (a:Article {id: $id})" in q:
            article = self.store.get("articles", {}).get(params["id"])
            if not article:
                return FakeResult(None)
            outs = [
                {"id": to_id, "article_no": self.store["articles"][to_id]["article_no"], "title": None, "direction": "out"}
                for frm, to_id in self.store.get("references", [])
                if frm == params["id"] and to_id in self.store.get("articles", {})
            ]
            citing = [
                {
                    "id": from_id,
                    "article_no": self.store.get("decisions", {}).get(from_id, {}).get("decision_no"),
                    "title": self.store.get("decisions", {}).get(from_id, {}).get("title"),
                    "direction": "in",
                    "kind": "decision",
                }
                for from_id, to_id in self.store.get("cites", [])
                if to_id == params["id"]
            ]
            return FakeResult(
                {
                    "id": params["id"],
                    "article_no": article["article_no"],
                    "title": article.get("title"),
                    "law_id": article.get("law_id"),
                    "outs": outs,
                    "ins": citing,
                }
            )
        return FakeResult()


class FakeDriver:
    def __init__(self) -> None:
        self.store: dict = {}

    def session(self):
        return FakeSession(self.store)


class FakePg:
    def __init__(self, articles: list[tuple], *, decisions: list[tuple] | None = None, relations: list[tuple] | None = None) -> None:
        self.articles = articles
        self.decisions = decisions or []
        self.relations = relations or []
        self.executed: list[tuple] = []

    def execute(self, sql: str, params=None):
        self.executed.append((sql, params))
        if "FROM article_versions" in sql:
            return FakeCursor(self.articles)
        if "FROM court_decisions" in sql:
            return FakeCursor(self.decisions)
        if "FROM legal_relations" in sql:
            return FakeCursor(self.relations)
        return FakeCursor([])


class FakeCursor:
    def __init__(self, rows) -> None:
        self.rows = rows

    def fetchall(self):
        return self.rows


def test_projector_writes_law_articles_and_references() -> None:
    # article 11 cites 13
    rows = [
        ("law:5237:article:11", "law:5237", "11", "Vatandaş tarafından işlenmesi", "13 üncü maddede yazılı suçlar", "5237", "TCK"),
        ("law:5237:article:13", "law:5237", "13", "Seçililik", "Madde 13 metni", "5237", "TCK"),
    ]
    driver = FakeDriver()
    pg = FakePg(rows)
    stats = LegalGraphProjector(driver).project_from_postgres(pg, document_id="law:5237")
    assert stats["articles"] == 2
    assert stats["has_article"] == 2
    assert stats["references"] >= 1
    assert "law:5237" in driver.store["laws"]
    assert ("law:5237:article:11", "law:5237:article:13") in driver.store["references"]


def test_projector_writes_decisions_and_cites() -> None:
    from graph.projector import neighborhood

    articles = [
        ("law:5237:article:158", "law:5237", "158", "Nitelikli dolandırıcılık", "Madde 158 metni", "5237", "TCK"),
    ]
    decisions = [
        (
            "decision:yargitay:2023:2023/1:2023/2",
            "7. Ceza Dairesi — dolandırıcılık",
            2023,
            "2023/1",
            "2023/2",
            "court:yargitay",
            "yargitay",
            "Yargıtay",
        )
    ]
    relations = [
        ("court:yargitay", "decision:yargitay:2023:2023/1:2023/2", "ISSUED_BY"),
        ("decision:yargitay:2023:2023/1:2023/2", "law:5237:article:158", "CITES"),
    ]
    driver = FakeDriver()
    pg = FakePg(articles, decisions=decisions, relations=relations)
    stats = LegalGraphProjector(driver).project_from_postgres(pg, document_id="law:5237")
    assert stats["decisions"] == 1
    assert stats["cites"] == 1
    assert "decision:yargitay:2023:2023/1:2023/2" in driver.store["decisions"]
    assert ("court:yargitay", "decision:yargitay:2023:2023/1:2023/2") in driver.store["issued_by"]
    assert ("decision:yargitay:2023:2023/1:2023/2", "law:5237:article:158") in driver.store["cites"]
    neigh = neighborhood(driver, "law:5237:article:158")
    asserting = [n for n in neigh["neighbors"] if n.get("kind") == "decision"]
    assert asserting
    assert asserting[0]["id"] == "decision:yargitay:2023:2023/1:2023/2"


class _DumpGraphSession:
    """Minimal fake for dump_graph()'s two plain `session.run(...)` calls —
    kayıt eder ve boş sonuç döner; asıl amaç sorgu metnini denetlemek."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, query: str, **params):
        self.queries.append((" ".join(query.split()), params))
        return []


class _DumpGraphDriver:
    def __init__(self) -> None:
        self.session_obj = _DumpGraphSession()

    def session(self):
        return self.session_obj


def test_dump_graph_excludes_decisions_and_caps_size() -> None:
    """Regresyon: dump_graph() eskiden filtresizdi ve arşivdeki ~50.000
    Decision (emsal karar) düğümünü de "Bilgi grafı" arka planına dump
    ediyordu — vis-network'ün fizik motoru bu kadar düğümle tarayıcı
    sekmesini tamamen kilitliyordu (canlı doğrulandı). Arka plan grafiği
    artık yalnızca kodifiye hukuk iskeletini (Article/Law/Court) içeriyor;
    Decision'lar sorguya özel yoldan (LegalGraphView.tsx'teki evidence/
    graph_neighbors) ayrıca geliyor."""
    from graph.projector import dump_graph

    driver = _DumpGraphDriver()
    dump_graph(driver, node_limit=123)
    node_query, node_params = driver.session_obj.queries[0]
    edge_query, edge_params = driver.session_obj.queries[1]
    assert "NOT n:Decision" in node_query
    assert "LIMIT $node_limit" in node_query
    assert node_params == {"node_limit": 123}
    assert "NOT a:Decision AND NOT b:Decision" in edge_query
    assert "LIMIT $edge_limit" in edge_query
    assert edge_params == {"edge_limit": 123 * 4}
