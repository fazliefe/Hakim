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


class _FakeScorer:
    """create_reranker() gerçek model indirmeden test edilebilsin diye
    enjekte edilen sahte cross-encoder — sırası `fused` listesiyle aynı."""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores
        self.calls: list[list[tuple[str, str]]] = []

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.calls.append(list(pairs))
        return list(self._scores[: len(pairs)])


class _BrokenScorer:
    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        raise RuntimeError("model indirilemedi")


def test_rerank_uses_scorer_when_given() -> None:
    weak = _fused("125", "Hakaret", "Hakaret", 1, 0.9)
    strong = _fused("158", "Nitelikli dolandırıcılık", "Banka veya kredi kurumlarının araç olarak kullanılması", 2, 0.1)
    # Sözcük-örtüşmesi "strong"u öne çıkarırdı; scorer tam tersini söylüyor —
    # sıralamanın gerçekten scorer'dan geldiğini kanıtlar.
    scorer = _FakeScorer([9.0, 0.1])
    ranked = rerank_fused("nitelikli dolandırıcılıkta banka hesabı", [weak, strong], scorer=scorer)
    assert ranked[0].hit.article_no == "125"
    assert len(scorer.calls) == 1
    assert scorer.calls[0][0][0] == "nitelikli dolandırıcılıkta banka hesabı"


def test_rerank_article_boost_applies_on_top_of_scorer() -> None:
    other = _fused("125", "Hakaret", "Hakaret", 1, 0.9)
    cited = _fused("158", "Nitelikli dolandırıcılık", "İçerik", 2, 0.1)
    # Scorer ikisine de eşit puan verse bile madde 158 sorusunda 158 kazanmalı.
    scorer = _FakeScorer([1.0, 1.0])
    ranked = rerank_fused("madde 158", [other, cited], scorer=scorer)
    assert ranked[0].hit.article_no == "158"


def test_rerank_falls_back_to_lexical_when_scorer_errors() -> None:
    weak = _fused("125", "Hakaret", "Hakaret", 1, 0.9)
    strong = _fused("158", "Nitelikli dolandırıcılık", "Banka veya kredi kurumlarının araç olarak kullanılması", 2, 0.1)
    ranked = rerank_fused(
        "nitelikli dolandırıcılıkta banka hesabı", [weak, strong], scorer=_BrokenScorer()
    )
    # Scorer patladı: sonuç scorer'sız (lexical) durumla aynı olmalı.
    assert ranked[0].hit.article_no == "158"


def test_rerank_empty_input_never_calls_scorer() -> None:
    scorer = _FakeScorer([])
    assert rerank_fused("herhangi bir sorgu", [], scorer=scorer) == []
    assert scorer.calls == []
