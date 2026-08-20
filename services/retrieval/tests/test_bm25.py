from __future__ import annotations

from datetime import datetime, timezone

from retrieval.bm25 import Bm25Searcher
from retrieval.indexer import LegalChunkIndexer
from retrieval.mapping import chunk_from_article_row, chunk_from_decision_row


def _clause_matches(doc: dict, clause: dict) -> bool:
    term = clause.get("term") or {}
    for field, value in term.items():
        expected = value.get("value") if isinstance(value, dict) else value
        if doc.get(field) == expected:
            return True
    return False


def _doc_matches_filters(doc: dict, filters: list) -> bool:
    for item in filters:
        if "term" in item:
            if not _clause_matches(doc, item):
                return False
        nested = (item.get("bool") or {}).get("should") or []
        if nested and not any(_clause_matches(doc, clause) for clause in nested):
            return False
    return True


class FakeIndices:
    def __init__(self) -> None:
        self.indexes: set[str] = set()
        self.created: list[str] = []

    def exists(self, *, index: str) -> bool:
        return index in self.indexes

    def delete(self, *, index: str) -> None:
        self.indexes.discard(index)

    def create(self, *, index: str, body: dict | None = None, **kwargs) -> None:
        self.indexes.add(index)
        self.created.append(index)


class FakeES:
    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.docs: dict[str, dict] = {}
        self.last_search_body: dict | None = None

    def bulk(self, *, operations: list, refresh: bool = False) -> dict:
        i = 0
        while i < len(operations):
            action = operations[i]
            doc = operations[i + 1]
            doc_id = action["index"]["_id"]
            self.docs[doc_id] = doc
            i += 2
        return {"errors": False}

    def search(self, *, index: str, body: dict) -> dict:
        self.last_search_body = body
        bool_q = body["query"]["bool"]
        should = bool_q.get("should") or []
        filters = bool_q.get("filter") or []
        query = ""
        article_boost = None
        for clause in should:
            if "multi_match" in clause:
                query = clause["multi_match"]["query"].lower()
            if "term" in clause and "article_no" in clause["term"]:
                article_boost = str(clause["term"]["article_no"]["value"])
        scored = []
        for doc_id, doc in self.docs.items():
            if not _doc_matches_filters(doc, filters):
                continue
            blob = f"{doc.get('title','')} {doc.get('content','')} {doc.get('article_no','')}".lower()
            score = 0.0
            if query and (query in blob or any(tok in blob for tok in query.split())):
                score = 10.0 if doc.get("article_no") in query else 5.0
                if "dolandırıcılık" in query and "dolandırıcılık" in blob:
                    score += 20
                if doc.get("article_no") == "158" and ("158" in query or "dolandır" in query):
                    score += 30
            if article_boost and doc.get("article_no") == article_boost:
                score += 50
            if score > 0:
                scored.append((score, doc_id, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return {
            "hits": {
                "hits": [
                    {"_id": doc_id, "_score": score, "_source": doc}
                    for score, doc_id, doc in scored[: body.get("size", 10)]
                ]
            }
        }


def test_chunk_from_article_row_builds_canonical_id() -> None:
    doc = chunk_from_article_row(
        {
            "article_id": "law:5237:article:158",
            "document_id": "law:5237",
            "article_no": "158",
            "version": 1,
            "title": "Nitelikli dolandırıcılık",
            "body": "Madde 158- (1) ...",
            "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
            "valid_until": None,
            "document_type": "law",
            "law_no": "5237",
            "authority": "official",
            "source_provider": "mevzuat.gov.tr",
        }
    )
    assert doc["chunk_id"] == "law:5237:article:158:v1"
    assert doc["law_no"] == "5237"
    assert doc["authority"] == "official"


def test_indexer_bulk_writes_chunks() -> None:
    es = FakeES()
    indexer = LegalChunkIndexer(es)
    indexer.ensure_index(recreate=True)
    n = indexer.index_rows(
        [
            {
                "article_id": "law:5237:article:158",
                "document_id": "law:5237",
                "article_no": "158",
                "version": 1,
                "title": "Nitelikli dolandırıcılık",
                "body": "Madde 158- (1) Dolandırıcılık suçunun;",
                "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
                "valid_until": None,
                "document_type": "law",
                "law_no": "5237",
                "authority": "official",
                "source_provider": "mevzuat.gov.tr",
            }
        ]
    )
    assert n == 1
    assert "law:5237:article:158:v1" in es.docs


def test_bm25_search_ranks_article_158() -> None:
    es = FakeES()
    indexer = LegalChunkIndexer(es)
    indexer.ensure_index()
    indexer.index_rows(
        [
            {
                "article_id": "law:5237:article:1",
                "document_id": "law:5237",
                "article_no": "1",
                "version": 1,
                "title": "Ceza Kanununun amacı",
                "body": "Madde 1- (1) Ceza Kanununun amacı;",
                "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
                "valid_until": None,
                "document_type": "law",
                "law_no": "5237",
                "authority": "official",
                "source_provider": "mevzuat.gov.tr",
            },
            {
                "article_id": "law:5237:article:158",
                "document_id": "law:5237",
                "article_no": "158",
                "version": 1,
                "title": "Nitelikli dolandırıcılık",
                "body": "Madde 158- (1) Dolandırıcılık suçunun;",
                "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
                "valid_until": None,
                "document_type": "law",
                "law_no": "5237",
                "authority": "official",
                "source_provider": "mevzuat.gov.tr",
            },
        ]
    )
    hits = Bm25Searcher(es).search("nitelikli dolandırıcılık", law_no="5237", size=5)
    assert hits
    assert hits[0].article_no == "158"
    assert hits[0].chunk_id == "law:5237:article:158:v1"


def test_extract_article_no_from_madde_query() -> None:
    from retrieval.bm25 import extract_article_no, parse_law_hint

    assert extract_article_no("Madde 158") == "158"
    assert extract_article_no("158") == "158"
    assert extract_article_no("CMK madde 158 ihbar ve şikayet nasıl yapılır?") == "158"
    assert extract_article_no("TCK m.158") == "158"
    assert parse_law_hint("CMK madde 158 ihbar") == "5271"
    assert parse_law_hint("TCK 158 nitelikli") == "5237"
    assert parse_law_hint("nitelikli dolandırıcılık") is None


def test_bm25_law_scope_includes_court_decisions() -> None:
    es = FakeES()
    indexer = LegalChunkIndexer(es)
    indexer.ensure_index()
    indexer.index_rows(
        [
            {
                "article_id": "law:5237:article:158",
                "document_id": "law:5237",
                "article_no": "158",
                "version": 1,
                "title": "Nitelikli dolandırıcılık",
                "body": "Madde 158- (1) Dolandırıcılık suçunun;",
                "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
                "valid_until": None,
                "document_type": "law",
                "law_no": "5237",
                "authority": "official",
                "source_provider": "mevzuat.gov.tr",
            }
        ]
    )
    decision = chunk_from_decision_row(
        {
            "id": "decision:yargitay:2023:2023/1:2023/2",
            "title": "7. Ceza Dairesi — dolandırıcılık",
            "body": "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine",
            "decision_no": "2023/2",
            "decision_date": None,
            "court_id": "court:yargitay",
            "court_slug": "yargitay",
            "source_provider": "yargitay.gov.tr",
        }
    )
    es.docs[decision["chunk_id"]] = decision
    hits = Bm25Searcher(es).search("dolandırıcılık", law_no="5237", size=10)
    ids = {hit.document_id for hit in hits}
    assert "law:5237" in ids
    assert "decision:yargitay:2023:2023/1:2023/2" in ids
    filt = (es.last_search_body or {}).get("query", {}).get("bool", {}).get("filter") or []
    assert "court_decision" in str(filt)
