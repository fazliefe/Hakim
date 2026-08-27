from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from hakim_bench.metrics import (
    answer_metrics,
    citation_metrics,
    context_metrics,
    mean,
    ndcg_at,
    percentile,
    precision_at,
    recall_at,
    reciprocal_rank,
)
from hakim_bench.schema import ExperimentConfig, ExperimentRun, GoldQuestion, RetrievedHit


class Pipeline(Protocol):
    def retrieve(
        self,
        question: GoldQuestion,
        *,
        top_k: int,
        retrieve_k: int,
        retrieval_method: str,
        threshold: float | None,
        reranker: str,
        rerank_k: int,
        query_strategy: str = "original",
    ) -> tuple[list[RetrievedHit], dict[str, float]]: ...

    def generate(
        self,
        question: GoldQuestion,
        hits: list[RetrievedHit],
        *,
        temperature: float,
        llm: str,
        prompt_version: str,
    ) -> tuple[str, dict[str, float]]: ...


def _cost(input_tokens: float, output_tokens: float, cfg: ExperimentConfig) -> float:
    return (input_tokens / 1_000_000.0) * cfg.input_per_million + (
        output_tokens / 1_000_000.0
    ) * cfg.output_per_million


def _question_record(
    question: GoldQuestion,
    hits: list[RetrievedHit],
    answer: str,
    *,
    context_hits: list[RetrievedHit] | None = None,
    retrieve_ms: float,
    generate_ms: float,
    input_tokens: float,
    output_tokens: float,
    context_tokens: float,
    cost: float,
) -> dict[str, Any]:
    used = context_hits if context_hits is not None else hits
    ctx = " ".join(h.content for h in used)
    ans = answer_metrics(question, answer, context=ctx)
    cites = citation_metrics(question, answer)
    ctx_m = context_metrics(question, hits)
    total_ms = retrieve_ms + generate_ms
    row: dict[str, Any] = {
        "id": question.id,
        "question_type": question.question_type,
        "answerable": question.answerable,
        "answer": answer,
        "Recall@1": recall_at(question, hits, 1) if question.answerable else None,
        "Recall@3": recall_at(question, hits, 3) if question.answerable else None,
        "Recall@5": recall_at(question, hits, 5) if question.answerable else None,
        "Recall@10": recall_at(question, hits, 10) if question.answerable else None,
        "Precision@5": precision_at(question, hits, 5) if question.answerable else None,
        "MRR": reciprocal_rank(question, hits) if question.answerable else None,
        "nDCG@10": ndcg_at(question, hits, 10) if question.answerable else None,
        "Context Precision": ctx_m["context_precision"] if question.answerable else None,
        "Context Recall": ctx_m["context_recall"] if question.answerable else None,
        "Answer Correctness": ans["correctness"],
        "Answer Relevance": ans["relevance"],
        "Faithfulness": ans["faithfulness"],
        "Hallucination Rate": ans["hallucination"],
        "correct_refusal": ans["correct_refusal"],
        "Citation Precision": cites["citation_precision"],
        "Citation Recall": cites["citation_recall"],
        "latency_ms": total_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "context_tokens": context_tokens,
        "cost_per_query": cost,
        "retrieved": [
            {
                "chunk_id": h.chunk_id,
                "law_no": h.law_no,
                "article_no": h.article_no,
                "rank": h.rank,
                "score": h.score,
            }
            for h in hits
        ],
    }
    return row


def _avg_key(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return mean(values)


def summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    lat = [float(row["latency_ms"]) for row in rows]
    una = [row for row in rows if not row.get("answerable")]
    ans = [row for row in rows if row.get("answerable")]
    return {
        "Recall@1": _avg_key(rows, "Recall@1"),
        "Recall@3": _avg_key(rows, "Recall@3"),
        "Recall@5": _avg_key(rows, "Recall@5"),
        "Recall@10": _avg_key(rows, "Recall@10"),
        "Precision@5": _avg_key(rows, "Precision@5"),
        "MRR": _avg_key(rows, "MRR"),
        "nDCG@10": _avg_key(rows, "nDCG@10"),
        "Context Precision": _avg_key(rows, "Context Precision"),
        "Context Recall": _avg_key(rows, "Context Recall"),
        "Answer Correctness": _avg_key(rows, "Answer Correctness"),
        "Answer Relevance": _avg_key(rows, "Answer Relevance"),
        "Faithfulness": _avg_key(rows, "Faithfulness"),
        "Hallucination Rate": _avg_key(rows, "Hallucination Rate"),
        "Citation Precision": _avg_key(rows, "Citation Precision"),
        "Citation Recall": _avg_key(rows, "Citation Recall"),
        "correct_refusal": mean(
            [1.0 if row.get("correct_refusal") else 0.0 for row in una]
        )
        if una
        else 0.0,
        "answerable_empty": mean(
            [1.0 if not (row.get("retrieved") or []) else 0.0 for row in ans]
        )
        if ans
        else 0.0,
        "p50_latency": percentile(lat, 50),
        "p95_latency": percentile(lat, 95),
        "input_tokens": _avg_key(rows, "input_tokens"),
        "output_tokens": _avg_key(rows, "output_tokens"),
        "context_tokens": _avg_key(rows, "context_tokens"),
        "cost_per_query": _avg_key(rows, "cost_per_query"),
    }


def run_experiment(
    questions: list[GoldQuestion],
    config: ExperimentConfig,
    *,
    pipeline: Pipeline,
    on_item: Callable[[int, int, dict[str, Any]], None] | None = None,
) -> ExperimentRun:
    rows: list[dict[str, Any]] = []
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        hits, retrieve_obs = pipeline.retrieve(
            question,
            top_k=config.top_k,
            retrieve_k=config.retrieve_k,
            retrieval_method=config.retrieval_method,
            threshold=config.threshold,
            reranker=config.reranker,
            rerank_k=config.rerank_k,
            query_strategy=config.query_strategy,
        )
        gen_hits = hits[: config.top_k]
        answer, gen_obs = pipeline.generate(
            question,
            gen_hits,
            temperature=config.temperature,
            llm=config.llm,
            prompt_version=config.prompt_version,
        )
        input_tokens = float(gen_obs.get("input_tokens") or 0.0)
        output_tokens = float(gen_obs.get("output_tokens") or 0.0)
        row = _question_record(
            question,
            hits,
            answer,
            context_hits=gen_hits,
            retrieve_ms=float(retrieve_obs.get("retrieve_ms") or 0.0),
            generate_ms=float(gen_obs.get("generate_ms") or 0.0),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            context_tokens=float(gen_obs.get("context_tokens") or 0.0),
            cost=_cost(input_tokens, output_tokens, config),
        )
        rows.append(row)
        by_type[question.question_type].append(row)
        if on_item is not None:
            on_item(len(rows), len(questions), row)
    return ExperimentRun(
        experiment_id=config.experiment_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=config.to_dict(),
        metrics=summarize(rows),
        metrics_by_question_type={key: summarize(items) for key, items in by_type.items()},
        per_question=rows,
    )
