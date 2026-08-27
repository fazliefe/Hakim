from __future__ import annotations

import pytest

from hakim_bench.schema import GoldQuestion, SchemaError


def test_gold_question_parses_plan_record() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "q001",
            "question": "Nitelikli dolandırıcılık hangi maddede düzenlenir?",
            "expected_answer": "TCK m.158",
            "relevant_documents": ["law:5237"],
            "relevant_chunks": ["law:5237:article:158:v1"],
            "relevant_articles": [{"law_no": "5237", "article_no": "158"}],
            "question_type": "factual",
            "difficulty": "easy",
            "answerable": True,
        }
    )
    assert q.id == "q001"
    assert q.question_type == "factual"
    assert q.answerable is True
    assert ("5237", "158") in q.article_keys


def test_gold_question_rejects_unknown_type() -> None:
    with pytest.raises(SchemaError):
        GoldQuestion.from_dict(
            {
                "id": "q-bad",
                "question": "?",
                "expected_answer": "",
                "question_type": "trivia",
                "difficulty": "easy",
                "answerable": True,
            }
        )


def test_unanswerable_record_has_empty_gold_and_refusal_answer() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "q-u1",
            "question": "X şirketi ne zaman kuruldu?",
            "expected_answer": "Bu bilgi mevcut kaynaklarda bulunmuyor.",
            "relevant_documents": [],
            "relevant_chunks": [],
            "question_type": "unanswerable",
            "difficulty": "easy",
            "answerable": False,
        }
    )
    assert q.answerable is False
    assert q.article_keys == frozenset()
