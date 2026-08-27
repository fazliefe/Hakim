from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

from hakim_bench.dataset import load_dataset, mix_share, stratified_sample
from hakim_bench.experiments import get_experiment, list_experiments
from hakim_bench.metrics import percentile
from hakim_bench.runner import run_experiment
from hakim_bench.simulate import sweep_threshold, sweep_topk, top1_scores


def _load_dotenv() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _write_run(run, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": run.experiment_id,
        "timestamp": run.timestamp,
        **run.config,
        **run.metrics,
        "metrics_by_question_type": run.metrics_by_question_type,
        "per_question": run.per_question,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sweep_file(path: Path, *, out: Path | None) -> int:
    from hakim_bench.dataset import load_dataset as load_gold

    payload = json.loads(path.read_text(encoding="utf-8"))
    gold = {q.id: q for q in load_gold()}
    rows = payload["per_question"]
    ans, una = top1_scores(gold, rows)
    stats = {
        "answerable_p10": percentile(ans, 10),
        "answerable_p50": percentile(ans, 50),
        "unanswerable_p50": percentile(una, 50),
        "unanswerable_p90": percentile(una, 90),
        "unanswerable_p95": percentile(una, 95),
    }
    scores = sorted({h["score"] for row in rows for h in row.get("retrieved") or []})
    if len(scores) > 40:
        step = max(1, len(scores) // 20)
        candidates = scores[::step]
    else:
        candidates = scores
    thresholds: list[float | None] = [None, *candidates]
    curve = sweep_threshold(gold, rows, thresholds)
    report = {"source": str(path), "top1": stats, "curve": curve}
    target = out or path.with_name(path.stem + "_threshold.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"top1 answerable p50={stats['answerable_p50']:.4f} unanswerable p90={stats['unanswerable_p90']:.4f}")
    print(f"{'thr':>12} {'R@5':>8} {'MRR':>8} {'refusal':>8} {'empty':>8}")
    for item in curve:
        thr = "none" if item["threshold"] is None else f"{item['threshold']:.4f}"
        print(
            f"{thr:>12} {item['Recall@5']:8.3f} {item['MRR']:8.3f} "
            f"{item['correct_refusal']:8.3f} {item['answerable_empty']:8.3f}"
        )
    print(f"wrote {target}")
    return 0


def _sweep_topk_file(path: Path, *, out: Path | None) -> int:
    from hakim_bench.dataset import load_dataset as load_gold

    payload = json.loads(path.read_text(encoding="utf-8"))
    gold = {q.id: q for q in load_gold()}
    curve = sweep_topk(gold, payload["per_question"], [1, 3, 5, 10, 20, 50])
    target = out or path.with_name(path.stem + "_topk.json")
    target.write_text(json.dumps(curve, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{'k':>6} {'R@K':>8} {'MRR':>8}")
    for item in curve:
        print(f"{item['k']:6.0f} {item['Recall@K']:8.3f} {item['MRR']:8.3f}")
    print(f"wrote {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="HÂKİM RAG benchmark")
    parser.add_argument("--experiment", default="baseline", choices=list_experiments())
    parser.add_argument("--limit", type=int, default=0, help="0 = tüm dataset")
    parser.add_argument("--stratified", type=int, default=0, help="plan oranında N soru")
    parser.add_argument("--generator", choices=("extractive", "llm"), default="extractive")
    parser.add_argument("--law-no", default="", help="ES filtresi; boş = tüm kanunlar")
    parser.add_argument("--threshold", type=float, default=None, help="config eşiğini ezer")
    parser.add_argument("--sweep-threshold", type=Path, default=None, help="kayıtlı run JSON")
    parser.add_argument("--sweep-topk", type=Path, default=None, help="kayıtlı run JSON")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--leaderboard", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--mix-only", action="store_true", help="dataset karışımını yaz, koşturma")
    args = parser.parse_args(argv)

    if args.leaderboard:
        from hakim_bench.score import write_leaderboard

        target = args.out or Path("eval/results/leaderboard.json")
        write_leaderboard(target)
        print(f"wrote {target}")
        return 0
    if args.sweep_threshold:
        return _sweep_file(args.sweep_threshold, out=args.out)
    if args.sweep_topk:
        return _sweep_topk_file(args.sweep_topk, out=args.out)

    questions = load_dataset(args.dataset) if args.dataset else load_dataset()
    if args.stratified and args.stratified > 0:
        questions = stratified_sample(questions, args.stratified)
    elif args.limit and args.limit > 0:
        questions = questions[: args.limit]
    if args.mix_only:
        counts = Counter(q.question_type for q in questions)
        json.dump(
            {"n": sum(counts.values()), "counts": dict(counts), "share": mix_share(counts, sum(counts.values()))},
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    cfg = get_experiment(args.experiment)
    if args.threshold is not None:
        cfg = replace(cfg, threshold=args.threshold, experiment_id=f"{cfg.experiment_id}_thr")
    llm_experiments = {
        "hybrid_llm",
        "hybrid_temp02",
        "hybrid_temp07",
        "hybrid_prompt_strict",
        "hybrid_prompt_cite",
        "hybrid_llm_large",
        "hybrid_hyde",
        "hybrid_rewrite",
    }
    generator = "llm" if cfg.experiment_id in llm_experiments else args.generator
    needs_llm = generator == "llm" or cfg.query_strategy in {"hyde", "rewrite"}
    if needs_llm:
        from llm.api_client import api_configured

        if not api_configured():
            print("HAKIM_LLM_API_KEY yok; LLM deneyleri çalışmaz.", file=sys.stderr)
            return 2

    from hakim_bench.adapters import LivePipeline
    from hakim_bench.chunking import METHODS, ensure_chunk_index

    reranker = None
    if cfg.reranker == "cross-encoder":
        from retrieval.cross_encoder import create_reranker

        reranker = create_reranker(prefer_neural=True)
        print(
            f"reranker={'cross-encoder' if reranker is not None else 'lexical-fallback'}",
            flush=True,
        )

    index_name = None
    if cfg.experiment_id in METHODS:
        from retrieval.es_client import create_es_client

        index_name = ensure_chunk_index(create_es_client(), cfg.experiment_id)
        print(f"index={index_name}", flush=True)

    neural = cfg.retrieval_method != "bm25" and "Hashing" not in (cfg.embedding_model or "")
    pipeline = LivePipeline(
        generator=generator,
        law_no=args.law_no or None,
        reranker=reranker,
        prefer_neural=neural,
        index_name=index_name,
    )
    pipeline.hybrid.bm25_weight = cfg.bm25_weight
    pipeline.hybrid.dense_weight = cfg.dense_weight

    def _progress(i: int, n: int, row: dict) -> None:
        if i == 1 or i % 25 == 0 or i == n:
            print(
                f"[{i}/{n}] {row['id']} r@5={row.get('Recall@5')} hallu={row.get('Hallucination Rate'):.2f}",
                flush=True,
            )

    run = run_experiment(questions, cfg, pipeline=pipeline, on_item=_progress)
    out = args.out or Path("eval/results") / f"{cfg.experiment_id}.json"
    _write_run(run, out)
    summary = {"experiment_id": run.experiment_id, "n": len(run.per_question), **run.metrics}
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write(f"\nwrote {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
