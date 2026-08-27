from __future__ import annotations

from hakim_bench.schema import GoldQuestion
from hakim_bench.simulate import sweep_threshold, sweep_topk


def _gold(qid: str, article: str, *, answerable: bool = True) -> GoldQuestion:
    return GoldQuestion.from_dict(
        {
            "id": qid,
            "question": "q",
            "expected_answer": "a",
            "relevant_articles": [{"law_no": "5237", "article_no": article}] if answerable else [],
            "question_type": "factual" if answerable else "unanswerable",
            "difficulty": "easy",
            "answerable": answerable,
        }
    )


def _row(qid: str, scores: list[tuple[str, float]]) -> dict:
    return {
        "id": qid,
        "retrieved": [
            {
                "chunk_id": f"c{i}",
                "law_no": "5237",
                "article_no": art,
                "score": score,
                "rank": i,
            }
            for i, (art, score) in enumerate(scores, start=1)
        ],
    }


def test_threshold_filters_unanswerable_without_killing_gold() -> None:
    gold = {
        "a": _gold("a", "158"),
        "u": _gold("u", "1", answerable=False),
    }
    rows = [
        _row("a", [("158", 0.9), ("81", 0.4)]),
        _row("u", [("81", 0.5), ("82", 0.4)]),
    ]
    none, hi = sweep_threshold(gold, rows, [None, 0.8])
    assert none["Recall@5"] == 1.0
    assert none["correct_refusal"] == 0.0
    assert hi["Recall@5"] == 1.0
    assert hi["correct_refusal"] == 1.0


def test_topk_sweep_recall_rises_then_plateaus() -> None:
    gold = {"a": _gold("a", "158")}
    rows = [_row("a", [("81", 0.9), ("158", 0.8), ("82", 0.7)])]
    k1, k2, k3 = sweep_topk(gold, rows, [1, 2, 3])
    assert k1["Recall@K"] == 0.0
    assert k2["Recall@K"] == 1.0
    assert k3["Recall@K"] == 1.0
    assert k2["MRR"] == 0.5


def test_top1_scores_split_answerable_and_unanswerable() -> None:
    gold = {
        "a": _gold("a", "158"),
        "u": _gold("u", "1", answerable=False),
    }
    rows = [_row("a", [("158", 0.9)]), _row("u", [("81", 0.2)])]
    from hakim_bench.simulate import top1_scores

    ans, una = top1_scores(gold, rows)
    assert ans == [0.9]
    assert una == [0.2]
