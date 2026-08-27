from __future__ import annotations

from hakim_bench.adapters import _extractive_answer, forward_api_chat, passes_dense_gate, resolve_law_no
from hakim_bench.schema import GoldQuestion, RetrievedHit


def test_extractive_refuses_when_unanswerable() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "u1",
            "question": "X şirketi ne zaman kuruldu?",
            "expected_answer": "Bu bilgi mevcut kaynaklarda bulunmuyor.",
            "question_type": "unanswerable",
            "difficulty": "easy",
            "answerable": False,
        }
    )
    assert "bulunmuyor" in _extractive_answer(q, [])


def test_extractive_does_not_peek_unanswerable_label() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "u1",
            "question": "X şirketi ne zaman kuruldu?",
            "expected_answer": "Bu bilgi mevcut kaynaklarda bulunmuyor.",
            "question_type": "unanswerable",
            "difficulty": "easy",
            "answerable": False,
        }
    )
    hits = [
        RetrievedHit(
            chunk_id="c1",
            document_id="law:5237",
            law_no="5237",
            article_no="1",
            score=0.1,
            rank=1,
            content="kanunun amacı",
        )
    ]
    text = _extractive_answer(q, hits)
    assert "bulunmuyor" not in text
    assert "kanunun amacı" in text


def test_extractive_cites_article_from_hits() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "f1",
            "question": "nitelikli dolandırıcılık?",
            "expected_answer": "TCK m.158",
            "relevant_articles": [{"law_no": "5237", "article_no": "158"}],
            "question_type": "factual",
            "difficulty": "easy",
            "answerable": True,
        }
    )
    hits = [
        RetrievedHit(
            chunk_id="c158",
            document_id="law:5237",
            law_no="5237",
            article_no="158",
            score=0.9,
            rank=1,
            content="Nitelikli dolandırıcılık.",
        )
    ]
    text = _extractive_answer(q, hits)
    assert "5237" in text
    assert "158" in text
    assert "Nitelikli" in text


def test_dense_gate_rejects_low_cosine() -> None:
    low = RetrievedHit("c", None, "5237", "1", 0.4, 1, "x")
    high = RetrievedHit("c", None, "5237", "1", 0.8, 1, "x")
    assert passes_dense_gate([high], 0.7) is True
    assert passes_dense_gate([low], 0.7) is False
    assert passes_dense_gate([], 0.7) is False
    assert passes_dense_gate([low], None) is True


def test_resolve_law_no_hint_and_oracle() -> None:
    hinted = GoldQuestion.from_dict(
        {
            "id": "k1",
            "question": "TCK 158 nitelikli dolandırıcılık",
            "expected_answer": "TCK m.158",
            "relevant_articles": [{"law_no": "5237", "article_no": "158"}],
            "question_type": "keyword",
            "difficulty": "easy",
            "answerable": True,
        }
    )
    plain = GoldQuestion.from_dict(
        {
            "id": "f1",
            "question": "nitelikli dolandırıcılık hangi maddede?",
            "expected_answer": "TCK m.158",
            "relevant_articles": [{"law_no": "5237", "article_no": "158"}],
            "question_type": "factual",
            "difficulty": "easy",
            "answerable": True,
        }
    )
    una = GoldQuestion.from_dict(
        {
            "id": "u1",
            "question": "X şirketi ne zaman kuruldu?",
            "expected_answer": "Bu bilgi mevcut kaynaklarda bulunmuyor.",
            "question_type": "unanswerable",
            "difficulty": "easy",
            "answerable": False,
        }
    )
    assert resolve_law_no(hinted, strategy="law_hint") == "5237"
    assert resolve_law_no(plain, strategy="law_hint") is None
    assert resolve_law_no(plain, strategy="oracle_law") == "5237"
    assert resolve_law_no(una, strategy="oracle_law") is None
    assert resolve_law_no(plain, strategy="original") is None
    assert resolve_law_no(plain, strategy="original", fallback="5271") == "5271"


def test_forward_api_chat_does_not_duplicate_json_mode(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake(messages, *, json_mode=True, **kwargs):
        seen["json_mode"] = json_mode
        seen["temperature"] = kwargs.get("temperature")
        return "ok"

    monkeypatch.setattr("llm.api_client.api_chat", fake)
    text = forward_api_chat([{"role": "user", "content": "x"}], json_mode=False, temperature=0.0)
    assert text == "ok"
    assert seen["json_mode"] is False
    assert seen["temperature"] == 0.0
