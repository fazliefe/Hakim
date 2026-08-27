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
    """Gerçek ES gibi index-izole: `self.docs` index adına göre ayrı bucket'lar
    tutar — iki-index (kanun + karar) hibrit aramayı doğru test edebilmek
    için (`Bm25Searcher`/`SemanticSearcher`'ın `index_name`'i gerçekten
    izole etmesi gerekiyor, tek düz sözlükte karışırlardı)."""

    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.docs: dict[str, dict[str, dict]] = {}
        self.bulk_calls = 0

    def bulk(self, *, operations: list, refresh: bool = False) -> dict:
        self.bulk_calls += 1
        i = 0
        while i < len(operations):
            action = operations[i]
            doc = operations[i + 1]
            index_name = action["index"]["_index"]
            self.docs.setdefault(index_name, {})[action["index"]["_id"]] = doc
            i += 2
        return {"errors": False}

    def search(
        self,
        *,
        index: str,
        body: dict | None = None,
        knn: dict | None = None,
        size: int = 10,
        aggs: dict | None = None,
    ) -> dict:
        pool = self.docs.get(index, {})
        if aggs is not None:
            # `_existing_chunk_ids()`'in terms aggregation'ı — sadece
            # `chunk_id` alanının değerlerini (gerçek doc sayısı kadar)
            # bucket olarak döndürmesi yeterli, gerçek ES agg mantığını
            # taklit etmeye gerek yok.
            field = next(iter(aggs.values()))["terms"]["field"]
            keys = {doc.get(field) for doc in pool.values() if doc.get(field)}
            return {"aggregations": {next(iter(aggs)): {"buckets": [{"key": k} for k in keys]}}}
        if knn is not None:
            qvec = knn["query_vector"]
            scored = []
            for doc_id, doc in pool.items():
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
        for doc_id, doc in pool.items():
            blob = f"{doc.get('title','')} {doc.get('content','')} {doc.get('article_no','')}".lower()
            score = 0.0
            if query and (query in blob or any(tok in blob for tok in query.split())):
                score = 5.0
                if "dolandırıcılık" in query and "dolandırıcılık" in blob:
                    score += 20
                if doc.get("article_no") == "158" and ("158" in query or "dolandır" in query):
                    score += 30
                if "yargıtay" in blob and "yargıtay" in query:
                    score += 25
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


def test_weighted_rrf_prefers_heavier_list() -> None:
    a = SearchHit("a", 1, "5237", "1", None, "x", None, None, None, 1)
    b = SearchHit("b", 1, "5237", "158", None, "y", None, None, None, 1)
    fused = reciprocal_rank_fusion(
        {"bm25": [a], "semantic": [b]},
        limit=2,
        weights={"bm25": 0.9, "semantic": 0.1},
    )
    assert fused[0].chunk_id == "a"


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


def test_index_rows_sends_bulk_per_batch_not_one_giant_request() -> None:
    """Regresyon: tüm satırları biriktirip TEK bir es.bulk() çağrısında
    göndermek büyük korpuslarda (örn. 11K+ emsal karar) ES/proxy'nin gövde
    boyutu sınırını (413) aşıyordu — canlı doğrulandı. Her batch kendi
    bulk() çağrısını göndermeli."""
    es = FakeES()
    indexer = LegalChunkIndexer(es, embedder=HashingEmbedder(), batch_size=1)
    indexer.ensure_index(recreate=True)
    rows = _sample_rows()
    indexer.index_rows(rows)
    assert es.bulk_calls == len(rows)
    assert len(es.docs[indexer.index_name]) == len(rows)


def test_index_decisions_from_postgres_skips_already_indexed(monkeypatch) -> None:
    """Regresyon: artımlı çalıştırmalarda (11K+ karar zaten indekslenmişken
    N tane daha eklemek) tüm korpusu yeniden embed etmek saatler sürerdi —
    canlı doğrulandı. `skip_existing=True` (varsayılan) zaten var olan
    chunk_id'leri atlamalı, embed sadece yeni kararlar için çağrılmalı."""
    from retrieval.mapping import DECISION_INDEX_NAME, chunk_from_decision_row, decision_index_settings

    es = FakeES()
    embedder = HashingEmbedder(dims=8)
    indexer = LegalChunkIndexer(
        es, index_name=DECISION_INDEX_NAME, embedder=embedder, settings_builder=decision_index_settings
    )
    indexer.ensure_index(recreate=True)

    # Zaten indekslenmiş bir karar (elle ES'e yazıldı, Postgres'te de var).
    existing_row = {**_sample_decision_row(), "id": "decision:yargitay:2020:1/1:1/1"}
    doc = chunk_from_decision_row(existing_row, embedding=embedder.embed([existing_row["body"]])[0])
    es.bulk(operations=[{"index": {"_index": DECISION_INDEX_NAME, "_id": doc["chunk_id"]}}, doc], refresh=True)
    assert es.bulk_calls == 1

    class _FakeConn:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchall(self):
            new_row = {**_sample_decision_row(), "id": "decision:yargitay:2021:2/2:2/2"}
            rows = [existing_row, new_row]
            cols = [
                "id", "title", "body", "decision_no", "decision_date",
                "court_id", "court_slug", "source_provider", "chamber", "docket_no",
            ]
            return [tuple(r.get(c) for c in cols) for r in rows]

    embed_calls: list[list[str]] = []
    original_embed = embedder.embed

    def _tracking_embed(texts):
        embed_calls.append(list(texts))
        return original_embed(texts)

    monkeypatch.setattr(embedder, "embed", _tracking_embed)
    written = indexer.index_decisions_from_postgres(_FakeConn())

    assert written == 1  # sadece yeni karar
    assert len(embed_calls) == 1 and len(embed_calls[0]) == 1  # embed sadece 1 metin için çağrıldı
    assert len(es.docs[DECISION_INDEX_NAME]) == 2  # eski + yeni


def test_indexer_stores_embeddings() -> None:
    es = FakeES()
    indexer = LegalChunkIndexer(es, embedder=HashingEmbedder())
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows()[:1])
    doc = es.docs[indexer.index_name]["law:5237:article:1:v1"]
    assert "embedding" in doc
    assert len(doc["embedding"]) == indexer.embedder.dims


def _sample_decision_row() -> dict:
    return {
        "id": "decision:yargitay:2024:100/1:200/1",
        "title": "Yargıtay 9. Ceza Dairesi — 100/1 E. — 200/1 K.",
        "body": "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verilmesi Yargıtay tarafından onanmıştır.",
        "decision_no": "200/1",
        "decision_date": datetime(2024, 3, 1, tzinfo=timezone.utc),
        "court_id": "court:yargitay",
        "court_slug": "yargitay",
        "source_provider": "bedesten.adalet.gov.tr",
        "chamber": "9. Ceza Dairesi",
        "docket_no": "100/1",
    }


def _build_dual_index_searcher(es: FakeES) -> HybridSearcher:
    from retrieval.mapping import DECISION_INDEX_NAME, chunk_from_decision_row, decision_index_settings

    law_embedder = HashingEmbedder()
    law_indexer = LegalChunkIndexer(es, embedder=law_embedder)
    law_indexer.ensure_index(recreate=True)
    law_indexer.index_rows(_sample_rows())

    decision_embedder = HashingEmbedder(dims=16)
    decision_indexer = LegalChunkIndexer(
        es,
        index_name=DECISION_INDEX_NAME,
        embedder=decision_embedder,
        settings_builder=decision_index_settings,
    )
    decision_indexer.ensure_index(recreate=True)
    row = _sample_decision_row()
    doc = chunk_from_decision_row(
        row, embedding=decision_embedder.embed([row["body"]])[0], embedding_model="HashingEmbedder"
    )
    es.bulk(operations=[{"index": {"_index": DECISION_INDEX_NAME, "_id": doc["chunk_id"]}}, doc], refresh=True)
    return HybridSearcher(
        es,
        law_embedder,
        limit=10,
        decision_index=DECISION_INDEX_NAME,
        decision_embedder=decision_embedder,
    )


def test_hybrid_search_merges_law_and_decision_indices_when_law_no_is_none() -> None:
    es = FakeES()
    searcher = _build_dual_index_searcher(es)
    fused = searcher.search("nitelikli dolandırıcılık Yargıtay kararı", law_no=None)
    document_ids = {h.hit.document_id for h in fused}
    assert any(str(doc_id).startswith("decision:") for doc_id in document_ids)
    assert any(str(doc_id) == "law:5237" for doc_id in document_ids)


def test_hybrid_search_excludes_decisions_when_law_no_given() -> None:
    """Kullanıcı onaylı davranış: madde arayan biri sadece madde metnini
    görsün — eski (tek-index) çıktı birebir korunur, regresyon yok."""
    es = FakeES()
    searcher = _build_dual_index_searcher(es)
    fused = searcher.search("nitelikli dolandırıcılık banka hesabı", law_no="5237")
    assert fused
    for hit in fused:
        assert not str(hit.hit.document_id).startswith("decision:")


def test_hybrid_searcher_without_decision_index_is_unaffected() -> None:
    """decision_index/decision_embedder verilmezse davranış tam eskisi gibi."""
    es = FakeES()
    embedder = HashingEmbedder()
    indexer = LegalChunkIndexer(es, embedder=embedder)
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows())
    searcher = HybridSearcher(es, embedder, limit=5)
    assert searcher.decision_bm25 is None
    assert searcher.decision_semantic is None
    fused = searcher.search("nitelikli dolandırıcılık banka hesabı", law_no=None)
    assert fused
    assert fused[0].hit.article_no == "158"


def test_hybrid_missing_decision_index_does_not_fail_law_search() -> None:
    from retrieval.mapping import DECISION_INDEX_NAME

    es = FakeES()
    embedder = HashingEmbedder()
    indexer = LegalChunkIndexer(es, embedder=embedder)
    indexer.ensure_index(recreate=True)
    indexer.index_rows(_sample_rows())
    searcher = HybridSearcher(
        es,
        embedder,
        limit=5,
        decision_index=DECISION_INDEX_NAME,
        decision_embedder=HashingEmbedder(dims=16),
    )

    def _missing(*_args, **_kwargs):
        raise Exception(
            "NotFoundError(404, 'index_not_found_exception', "
            "'no such index [hakim-court-decisions]', hakim-court-decisions, index_or_alias)"
        )

    searcher.decision_bm25.search = _missing  # type: ignore[method-assign]
    searcher.decision_semantic.search = _missing  # type: ignore[method-assign]
    fused = searcher.search("nitelikli dolandırıcılık banka hesabı", law_no=None)
    assert fused
    assert fused[0].hit.article_no == "158"
