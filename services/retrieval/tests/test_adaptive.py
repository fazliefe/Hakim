from retrieval.bm25 import SearchHit
from retrieval.hybrid import _is_exact_citation_query
from retrieval.adaptive import bm25_is_enough, query_is_off_topic


def _hit(*, article="158", title="Nitelikli dolandırıcılık", content="banka hesabı", score=12.0, rank=1) -> SearchHit:
    return SearchHit(
        chunk_id=f"chunk-{article}",
        score=score,
        law_no="5237",
        article_no=article,
        title=title,
        content=content,
        document_id="law:5237",
        article_id=f"5237:{article}",
        authority="TBMM",
        rank=rank,
    )


def test_exact_citation_is_enough_without_semantic() -> None:
    assert _is_exact_citation_query("madde 158")
    assert bm25_is_enough("madde 158", [_hit()]) is True


def test_short_legal_query_with_strong_hit_skips_semantic() -> None:
    assert bm25_is_enough("hakaret", [_hit(article="125", title="Hakaret", content="Hakaret suçu")]) is True


def test_detailed_fact_query_needs_semantic() -> None:
    assert (
        bm25_is_enough(
            "nitelikli dolandırıcılıkta banka hesabının kullanılması",
            [_hit()],
        )
        is False
    )


def test_empty_bm25_needs_semantic() -> None:
    assert bm25_is_enough("hakaret", []) is False


def test_exact_citation_enough_even_without_hits() -> None:
    assert bm25_is_enough("madde 158", []) is True


def test_off_topic_sports_and_weather() -> None:
    assert query_is_off_topic("fenerbahçe maçı ne olur") is True
    assert query_is_off_topic("fenerbahce mac sonucu") is True
    assert query_is_off_topic("hava durumu nasıl") is True


def test_off_topic_food_and_generic_chat() -> None:
    assert query_is_off_topic("yaprak sarma") is True
    assert query_is_off_topic("pizza tarifi") is True
    assert query_is_off_topic("bugün ne yesem") is True


def test_legal_queries_are_not_off_topic() -> None:
    assert query_is_off_topic("hakaret suçu") is False
    assert query_is_off_topic("nitelikli dolandırıcılıkta banka hesabı") is False
    assert query_is_off_topic("madde 158") is False
    assert query_is_off_topic("banka hesabından izinsiz para çekme") is False
    assert query_is_off_topic("trafik güvenliğini tehlikeye sokma") is False


def test_aggregation_queries_need_multi() -> None:
    from retrieval.query_expand import query_needs_multi

    assert query_needs_multi("öldürme suçları hangileridir?") is True
    assert query_needs_multi("nitelikli dolandırıcılıkta banka hesabı") is False
