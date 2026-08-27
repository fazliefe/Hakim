from __future__ import annotations

from hakim_bench.metrics import (
    answer_metrics,
    context_metrics,
    is_refusal,
    ndcg_at,
    percentile,
    precision_at,
    recall_at,
    reciprocal_rank,
)
from hakim_bench.schema import GoldQuestion, RetrievedHit


def _gold(**kwargs) -> GoldQuestion:
    base = {
        "id": "q1",
        "question": "Nitelikli dolandırıcılık maddesi?",
        "expected_answer": "TCK m.158",
        "relevant_articles": [{"law_no": "5237", "article_no": "158"}],
        "question_type": "factual",
        "difficulty": "easy",
        "answerable": True,
    }
    base.update(kwargs)
    return GoldQuestion.from_dict(base)


def _hit(law_no: str, article_no: str, *, rank: int, chunk_id: str = "") -> RetrievedHit:
    return RetrievedHit(
        chunk_id=chunk_id or f"law:{law_no}:article:{article_no}:v1",
        document_id=f"law:{law_no}",
        law_no=law_no,
        article_no=article_no,
        score=1.0 / rank,
        rank=rank,
        content=f"TCK m.{article_no} metni",
    )


def test_recall_at_k_finds_gold_article() -> None:
    gold = _gold()
    hits = [_hit("5237", "157", rank=1), _hit("5237", "158", rank=2)]
    assert recall_at(gold, hits, k=1) == 0.0
    assert recall_at(gold, hits, k=2) == 1.0
    assert recall_at(gold, hits, k=5) == 1.0


def test_citation_precision_and_recall() -> None:
    from hakim_bench.metrics import citation_metrics

    gold = _gold()
    good = citation_metrics(gold, "Cevap [5237 m.158] metin")
    assert good["citation_precision"] == 1.0
    assert good["citation_recall"] == 1.0
    extra = citation_metrics(gold, "[5237 m.158] [5237 m.81]")
    assert extra["citation_precision"] == 0.5
    una = _gold(question_type="unanswerable", answerable=False, expected_answer="yok", relevant_articles=[])
    assert citation_metrics(una, "Bu bilgi mevcut kaynaklarda bulunmuyor.")["citation_precision"] == 1.0


def test_precision_mrr_ndcg() -> None:
    gold = _gold()
    hits = [_hit("5237", "158", rank=1), _hit("5237", "157", rank=2)]
    assert precision_at(gold, hits, k=5) == 0.2
    assert reciprocal_rank(gold, hits) == 1.0
    assert ndcg_at(gold, hits, k=10) == 1.0


def test_mrr_is_zero_when_gold_missing() -> None:
    gold = _gold()
    hits = [_hit("5237", "81", rank=1)]
    assert reciprocal_rank(gold, hits) == 0.0
    assert ndcg_at(gold, hits, k=10) == 0.0


def test_ndcg_never_exceeds_one_with_duplicate_hits() -> None:
    gold = _gold()
    hits = [_hit("5237", "158", rank=1, chunk_id="a"), _hit("5237", "158", rank=2, chunk_id="b")]
    assert ndcg_at(gold, hits, k=10) == 1.0


def test_refusal_detector_and_unanswerable_metrics() -> None:
    gold = _gold(
        question_type="unanswerable",
        answerable=False,
        expected_answer="Bu bilgi mevcut kaynaklarda bulunmuyor.",
        relevant_articles=[],
    )
    assert is_refusal("Bu bilgi mevcut kaynaklarda bulunmuyor.")
    metrics = answer_metrics(gold, "Bu bilgi mevcut kaynaklarda bulunmuyor.", context="")
    assert metrics["correct_refusal"] == 1.0
    assert metrics["hallucination"] == 0.0
    fake = answer_metrics(gold, "Şirket 2019 yılında kurulmuştur.", context="")
    assert fake["correct_refusal"] == 0.0
    assert fake["hallucination"] == 1.0


def test_faithfulness_penalizes_answer_outside_context() -> None:
    gold = _gold()
    ctx = "TCK 158 nitelikli dolandırıcılığı düzenler."
    good = answer_metrics(gold, "Nitelikli dolandırıcılık TCK 158'de düzenlenir.", context=ctx)
    bad = answer_metrics(gold, "Cezası müebbet hapistir ve 2019'da kurulmuştur.", context=ctx)
    assert good["faithfulness"] > bad["faithfulness"]
    assert bad["hallucination"] > good["hallucination"]


def test_correctness_accepts_article_mention_not_verbatim_gold() -> None:
    gold = _gold()
    paraphrased = answer_metrics(
        gold,
        "Nitelikli dolandırıcılık 5237 sayılı kanunun 158. maddesinde düzenlenir.",
        context="Nitelikli dolandırıcılık.",
    )
    dump = answer_metrics(
        gold,
        "Kanunun amacı kamu düzenini korumaktır ve başka konular da vardır.",
        context="Kanunun amacı kamu düzenini korumaktır.",
    )
    assert paraphrased["correctness"] == 1.0
    assert dump["correctness"] < 0.5


def test_comparison_correctness_needs_all_gold_articles() -> None:
    gold = _gold(
        expected_answer="Kasten öldürme TCK m.81. Nitelikli TCK m.82.",
        relevant_articles=[{"law_no": "5237", "article_no": "81"}, {"law_no": "5237", "article_no": "82"}],
        question_type="comparison",
    )
    half = answer_metrics(gold, "Kasten öldürme TCK m.81'dedir.", context="metin")
    both = answer_metrics(gold, "m.81 kasten öldürme, m.82 nitelikli haldir.", context="metin")
    assert half["correctness"] < 1.0
    assert both["correctness"] == 1.0


def test_context_precision_and_recall() -> None:
    gold = _gold()
    hits = [_hit("5237", "158", rank=1), _hit("5237", "81", rank=2)]
    m = context_metrics(gold, hits)
    assert m["context_recall"] == 1.0
    assert m["context_precision"] == 0.5


def test_context_recall_does_not_exceed_one() -> None:
    gold = _gold()
    hits = [_hit("5237", "158", rank=1, chunk_id="a"), _hit("5237", "158", rank=2, chunk_id="b")]
    assert context_metrics(gold, hits)["context_recall"] == 1.0


def test_percentile_p50_p95() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 100.0]
    assert percentile(values, 50) == 3.0
    assert percentile(values, 95) == 100.0
    assert percentile([], 50) == 0.0
