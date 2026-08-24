from retrieval.bm25 import SearchHit
from retrieval.rerank import rerank_fused
from retrieval.rrf import FusedHit


def _fused(article: str, title: str, content: str, rank: int, score: float = 0.1) -> FusedHit:
    hit = SearchHit(
        chunk_id=f"c-{article}",
        score=1.0,
        law_no="5237",
        article_no=article,
        title=title,
        content=content,
        document_id="law:5237",
        article_id=f"5237:{article}",
        authority="TBMM",
        rank=rank,
    )
    return FusedHit(
        chunk_id=hit.chunk_id,
        rrf_score=score,
        rank=rank,
        sources=("bm25",),
        hit=hit,
        bm25_rank=rank,
        semantic_rank=None,
    )


def test_rerank_promotes_query_overlap() -> None:
    weak = _fused("125", "Hakaret", "Hakaret", 1, 0.9)
    strong = _fused("158", "Nitelikli dolandırıcılık", "Banka veya kredi kurumlarının araç olarak kullanılması", 2, 0.1)
    ranked = rerank_fused("nitelikli dolandırıcılıkta banka hesabı", [weak, strong])
    assert ranked[0].hit.article_no == "158"
    assert ranked[0].rank == 1
    assert ranked[1].hit.article_no == "125"
