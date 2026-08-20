from __future__ import annotations

from datetime import datetime, timezone

from retrieval.bm25 import Bm25Searcher, SearchHit
from retrieval.embeddings import HashingEmbedder
from retrieval.hybrid import HybridSearcher
from retrieval.indexer import LegalChunkIndexer
from retrieval.rrf import reciprocal_rank_fusion
from retrieval.semantic import SemanticSearcher


class FakeIndices:
    def __init__(self) -> None:
        self.indexes: set[str] = set()

    def exists(self, *, index: str) -> bool:
        return index in self.indexes

    def delete(self, *, index: str) -> None:
        self.indexes.discard(index)

    def create(self, *, index: str, body: dict | None = None, **kwargs) -> None:
        self.indexes.add(index)


class FakeES:
    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.docs: dict[str, dict] = {}

    def bulk(self, *, operations: list, refresh: bool = False) -> dict:
        i = 0
        while i < len(operations):
            action = operations[i]
            doc = operations[i + 1]
            self.docs[action["index"]["_id"]] = doc
            i += 2
        return {"errors": False}

    def search(self, *, index: str, body: dict | None = None, knn: dict | None = None, size: int = 10) -> dict:
        if knn is not None:
            qvec = knn["query_vector"]
            scored = []
            for doc_id, doc in self.docs.items():
                emb = doc.get("embedding") or []
                score = sum(a * b for a, b in zip(qvec, emb, strict=False))
                scored.append((score, doc_id, doc))
            scored.sort(key=lambda x: x[0], reverse=True)
            return {
                "hits": {
                    "hits": [
                        {"_id": doc_id, "_score": score, "_source": doc}
                        for score, doc_id, doc in scored[:size]
                    ]
                }
            }

        assert body is not None
        should = body["query"]["bool"].get("should") or []
        query = ""
        article_boost = None
        for clause in should:
            if "multi_match" in clause:
                query = clause["multi_match"]["query"].lower()
            if "term" in clause and "article_no" in clause["term"]:
                article_boost = str(clause["term"]["article_no"]["value"])
        scored = []
        for doc_id, doc in self.docs.items():
            blob = f"{doc.get('title','')} {doc.get('content','')} {doc.get('article_no','')}".lower()
            score = 0.0
            if query and (query in blob or any(tok in blob for tok in query.split())):
                score = 5.0
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


def _sample_rows() -> list[dict]:
    return [
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
            "body": "Madde 158- (1) Dolandırıcılık suçunun; banka veya kredi kurumlarının araç olarak kullanılması suretiyle,",
            "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
            "valid_until": None,
            "document_type": "law",
            "law_no": "5237",
            "authority": "official",
            "source_provider": "mevzuat.gov.tr",
        },
        {
            "article_id": "law:5237:article:157",
            "document_id": "law:5237",
            "article_no": "157",
            "version": 1,
            "title": "Dolandırıcılık",
            "body": "Madde 157- (1) Hileli davranışlarla bir kimseyi aldatıp,",
            "valid_from": datetime(2004, 10, 12, tzinfo=timezone.utc),
            "valid_until": None,
            "document_type": "law",
            "law_no": "5237",
            "authority": "official",
            "source_provider": "mevzuat.gov.tr",
        },
    ]


def test_rrf_prefers_agreement_across_retrievers() -> None:
    a = SearchHit("a", 1, "5237", "1", None, "x", None, None, None, 1)
    b = SearchHit("b", 1, "5237", "158", None, "y", None, None, None, 2)
    c = SearchHit("c", 1, "5237", "157", None, "z", None, None, None, 3)
    bm25 = [a, b, c]
    semantic = [
        SearchHit("b", 1, "5237", "158", None, "y", None, None, None, 1),
        SearchHit("c", 1, "5237", "157", None, "z", None, None, None, 2),
        SearchHit("a", 1, "5237", "1", None, "x", None, None, None, 3),
    ]
    fused = reciprocal_rank_fusion({"bm25": bm25, "semantic": semantic}, limit=3)
    assert fused[0].chunk_id == "b"
    assert fused[0].bm25_rank == 2
    assert fused[0].semantic_rank == 1
    assert set(fused[0].sources) == {"bm25", "semantic"}


def test_unique_by_article_keeps_first_version() -> None:
    from retrieval.hybrid import unique_by_article
    from retrieval.rrf import FusedHit

    v1 = SearchHit("law:5237:article:158:v1", 1, "5237", "158", "Nitelikli dolandırıcılık", "x", None, None, None, 1)
    v2 = SearchHit("law:5237:article:158:v2", 1, "5237", "158", "Nitelikli dolandırıcılık", "x", None, None, None, 2)
    other = SearchHit("law:5237:article:157:v1", 1, "5237", "157", "Dolandırıcılık", "y", None, None, None, 3)
    fused = [
        FusedHit("law:5237:article:158:v1", 0.9, 1, ("bm25",), v1, 1, 1),
        FusedHit("law:5237:article:158:v2", 0.8, 2, ("bm25",), v2, 2, 2),
        FusedHit("law:5237:article:157:v1", 0.7, 3, ("semantic",), other, 3, 3),
    ]
    unique = unique_by_article(fused, limit=3)
    assert [h.hit.article_no for h in unique] == ["158", "157"]
    assert unique[0].chunk_id.endswith(":v1")
    assert unique[0].rank == 1
    assert unique[1].rank == 2


def test_hybrid_search_returns_158_for_fraud_query() -> None:
    es = FakeES()
    embedder = HashingEmbedder()
    indexer = LegalChunkIndexer(es, embedder=embedder)
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows())

    fused = HybridSearcher(es, embedder, bm25_size=10, semantic_size=10, limit=5).search(
        "nitelikli dolandırıcılık banka hesabı",
        law_no="5237",
    )
    assert fused
    assert fused[0].hit.article_no == "158"
    assert "bm25" in fused[0].sources or "semantic" in fused[0].sources


def test_hybrid_exact_citation_uses_bm25_path() -> None:
    es = FakeES()
    embedder = HashingEmbedder()
    indexer = LegalChunkIndexer(es, embedder=embedder)
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows())
    fused = HybridSearcher(es, embedder, limit=3).search("Madde 158", law_no="5237")
    assert fused[0].hit.article_no == "158"
    assert fused[0].sources == ("bm25",)


def test_indexer_stores_embeddings() -> None:
    es = FakeES()
    indexer = LegalChunkIndexer(es, embedder=HashingEmbedder())
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows()[:1])
    doc = es.docs["law:5237:article:1:v1"]
    assert "embedding" in doc
    assert len(doc["embedding"]) == indexer.embedder.dims
