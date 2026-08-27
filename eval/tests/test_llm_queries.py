from __future__ import annotations

from hakim_bench.llm_queries import hyde_document, prompt_messages, rewrite_query
from hakim_bench.schema import GoldQuestion, RetrievedHit


def test_rewrite_query_uses_llm_and_falls_back() -> None:
    calls: list[list[dict]] = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        return "nitelikli dolandırıcılık TCK madde 158"

    assert rewrite_query("dolandırıcılık cezası nedir", chat=chat) == "nitelikli dolandırıcılık TCK madde 158"
    assert calls and "dolandırıcılık" in calls[0][-1]["content"]
    assert calls and calls[0]  # kwargs captured separately below
    seen: dict[str, object] = {}

    def chat_timeout(messages, **kwargs):
        seen.update(kwargs)
        return "ok"

    assert rewrite_query("q", chat=chat_timeout) == "ok"
    assert float(seen.get("timeout") or 0) >= 90.0
    long = ("kelime " * 400).strip()
    shortened = rewrite_query("q", chat=lambda *_a, **_k: long)
    assert 0 < len(shortened) <= 180
    assert rewrite_query("x", chat=lambda *_a, **_k: "  ") == "x"


def test_hyde_document_is_passage_not_question() -> None:
    def chat(messages, **_kwargs):
        assert "hipotetik" in messages[0]["content"].casefold() or "kanun maddesi" in messages[0]["content"].casefold()
        return "Nitelikli dolandırıcılık kamu görevlisi sıfatı kullanılarak işlenirse ceza artırılır."

    text = hyde_document("nitelikli dolandırıcılık nedir", chat=chat)
    assert "dolandırıcılık" in text.casefold()
    assert hyde_document("x", chat=lambda *_a, **_k: "") == "x"


def test_cite_prompt_requires_bracket_citations() -> None:
    q = GoldQuestion.from_dict(
        {
            "id": "f1",
            "question": "kast nedir?",
            "expected_answer": "TCK m.21",
            "relevant_articles": [{"law_no": "5237", "article_no": "21"}],
            "question_type": "factual",
            "difficulty": "easy",
            "answerable": True,
        }
    )
    hits = [
        RetrievedHit("c", "law:5237", "5237", "21", 0.9, 1, "Kast, suçun kanuni tanımındaki unsurların bilerek ve istenerek gerçekleştirilmesidir."),
    ]
    cite = prompt_messages(q, hits, "cite")
    strict = prompt_messages(q, hits, "strict")
    assert "[kanun" in cite[0]["content"].casefold() or "m." in cite[0]["content"]
    assert "bulunmuyor" in strict[0]["content"]
    assert "kast nedir" in cite[1]["content"]
