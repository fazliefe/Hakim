from __future__ import annotations

from hakim_bench.experiments import BASELINE, get_experiment
from hakim_bench.runner import run_experiment
from hakim_bench.schema import GoldQuestion, RetrievedHit


def _q(qid: str, article: str, *, answerable: bool = True, qtype: str = "factual") -> GoldQuestion:
    return GoldQuestion.from_dict(
        {
            "id": qid,
            "question": f"madde {article} nedir?",
            "expected_answer": f"TCK m.{article}" if answerable else "Bu bilgi mevcut kaynaklarda bulunmuyor.",
            "relevant_articles": [{"law_no": "5237", "article_no": article}] if answerable else [],
            "question_type": qtype if answerable else "unanswerable",
            "difficulty": "easy",
            "answerable": answerable,
        }
    )


class FakePipeline:
    def retrieve(self, question: GoldQuestion, *, top_k: int, **_kwargs):
        hits = [
            RetrievedHit(
                chunk_id=f"law:5237:article:{question.relevant_articles[0]['article_no'] if question.relevant_articles else '999'}:v1",
                document_id="law:5237",
                law_no="5237",
                article_no=question.relevant_articles[0]["article_no"] if question.relevant_articles else "999",
                score=0.9,
                rank=1,
                content=f"TCK m.{question.relevant_articles[0]['article_no'] if question.relevant_articles else '999'} metni",
            )
        ]
        return hits[:top_k], {"retrieve_ms": 1.0, "embed_ms": 0.5}

    def generate(self, question: GoldQuestion, hits, *, temperature: float, **_kwargs):
        if not question.answerable:
            text = "Bu bilgi mevcut kaynaklarda bulunmuyor."
        else:
            art = question.relevant_articles[0]["article_no"]
            text = f"TCK m.{art} metni"
        return text, {
            "generate_ms": 2.0,
            "input_tokens": 10,
            "output_tokens": 5,
            "context_tokens": 8,
        }


def test_hybrid_gated_uses_dense_cosine_threshold() -> None:
    cfg = get_experiment("hybrid_gated")
    assert cfg.retrieval_method == "hybrid"
    assert cfg.reranker == "none"
    assert cfg.threshold == 0.70


def test_faz9_law_filter_experiments() -> None:
    hint = get_experiment("hybrid_hint")
    assert hint.query_strategy == "law_hint"
    assert hint.retrieval_method == "hybrid"
    assert hint.threshold is None
    oracle = get_experiment("hybrid_oracle")
    assert oracle.query_strategy == "oracle_law"
    assert oracle.reranker == "none"


def test_hybrid_and_rerank_grid_experiments() -> None:
    hybrid = get_experiment("hybrid")
    assert hybrid.retrieval_method == "hybrid"
    assert hybrid.reranker == "none"
    assert hybrid.retrieve_k == 50
    fast = get_experiment("rr_10_5")
    assert fast.reranker == "cross-encoder"
    assert fast.retrieve_k == 10
    assert fast.rerank_k == 5
    mid = get_experiment("rr_20_5")
    assert mid.retrieve_k == 20
    assert mid.rerank_k == 5
    cfg = get_experiment("production")
    assert cfg.retrieval_method == "hybrid"
    assert cfg.reranker == "cross-encoder"
    assert cfg.retrieve_k == 50
    assert cfg.rerank_k == 12


def test_bm25_experiment_keeps_baseline_knobs() -> None:
    cfg = get_experiment("bm25")
    assert cfg.retrieval_method == "bm25"
    assert cfg.reranker == "none"
    assert cfg.top_k == 5
    assert cfg.temperature == 0.0
    cfg = get_experiment("baseline")
    assert cfg is BASELINE
    assert cfg.retrieval_method == "dense"
    assert cfg.top_k == 5
    assert cfg.reranker == "none"
    assert cfg.query_strategy == "original"
    assert cfg.temperature == 0.0
    assert cfg.chunk_method == "article"


def test_llm_phase_experiments() -> None:
    llm = get_experiment("hybrid_llm")
    assert llm.retrieval_method == "hybrid"
    assert llm.temperature == 0.0
    assert llm.prompt_version == "baseline"
    assert get_experiment("hybrid_temp02").temperature == 0.2
    assert get_experiment("hybrid_temp07").temperature == 0.7
    assert get_experiment("hybrid_prompt_strict").prompt_version == "strict"
    assert get_experiment("hybrid_prompt_cite").prompt_version == "cite"
    assert get_experiment("hybrid_llm_large").llm == "llm-large"
    assert get_experiment("hybrid_hyde").query_strategy == "hyde"
    assert get_experiment("hybrid_rewrite").query_strategy == "rewrite"


def test_runner_records_plan_metrics_and_config() -> None:
    questions = [_q("q001", "158"), _q("q002", "81"), _q("u001", "1", answerable=False)]
    run = run_experiment(questions, BASELINE, pipeline=FakePipeline())
    assert run.experiment_id == "baseline"
    assert run.metrics["Recall@1"] == 1.0
    assert run.metrics["Recall@5"] == 1.0
    assert run.metrics["MRR"] > 0.0
    assert "Answer Correctness" in run.metrics
    assert "Faithfulness" in run.metrics
    assert "Hallucination Rate" in run.metrics
    assert "p50_latency" in run.metrics
    assert "p95_latency" in run.metrics
    assert "cost_per_query" in run.metrics
    assert run.config["retrieval_method"] == "dense"
    assert len(run.per_question) == 3
    by_type = run.metrics_by_question_type
    assert "factual" in by_type
    assert "unanswerable" in by_type
