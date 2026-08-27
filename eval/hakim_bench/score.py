from __future__ import annotations

import json
from pathlib import Path

from hakim_bench.dataset import load_dataset
from hakim_bench.metrics import citation_metrics, mean
from hakim_bench.simulate import sweep_topk

RESULTS = Path(__file__).resolve().parents[1] / "results"

# Quality uses Recall@5 (extractive correctness is not an LLM signal).
WEIGHTS = {
    "quality": 0.40,
    "faithfulness": 0.20,
    "retrieval": 0.15,
    "latency": 0.10,
    "cost": 0.10,
    "robustness": 0.05,
}


def production_score(metrics: dict) -> dict[str, float]:
    recall = float(metrics.get("Recall@5") or 0.0)
    faith = float(metrics.get("Faithfulness") or 0.0)
    mrr = float(metrics.get("MRR") or 0.0)
    p50 = float(metrics.get("p50_latency") or 0.0)
    cost = float(metrics.get("cost_per_query") or 0.0)
    refuse = float(metrics.get("correct_refusal") or 0.0)
    latency = 1.0 / (1.0 + p50 / 1000.0)
    cost_s = 1.0 if cost <= 0 else 1.0 / (1.0 + cost * 1000.0)
    total = (
        WEIGHTS["quality"] * recall
        + WEIGHTS["faithfulness"] * faith
        + WEIGHTS["retrieval"] * mrr
        + WEIGHTS["latency"] * latency
        + WEIGHTS["cost"] * cost_s
        + WEIGHTS["robustness"] * refuse
    )
    return {
        "production_score": total,
        "quality": recall,
        "faithfulness": faith,
        "retrieval": mrr,
        "latency": latency,
        "cost": cost_s,
        "robustness": refuse,
    }


def _citations(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    gold = {q.id: q for q in load_dataset()}
    rows = payload.get("per_question") or []
    if payload.get("Citation Precision") is not None:
        return {
            "citation_precision": float(payload["Citation Precision"]),
            "citation_recall": float(payload.get("Citation Recall") or 0.0),
        }
    prec: list[float] = []
    rec: list[float] = []
    for row in rows:
        q = gold.get(row["id"])
        if q is None:
            continue
        m = citation_metrics(q, row.get("answer") or "")
        prec.append(m["citation_precision"])
        rec.append(m["citation_recall"])
    return {"citation_precision": mean(prec), "citation_recall": mean(rec)}


def _types(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by = payload.get("metrics_by_question_type") or {}
    return {key: float((by.get(key) or {}).get("Recall@5") or 0.0) for key in by}


def build_leaderboard(results_dir: Path | None = None) -> dict:
    folder = results_dir or RESULTS
    rows: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("threshold") or path.name.startswith("topk"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "Recall@5" not in payload:
            continue
        score = production_score(payload)
        cites = _citations(path)
        rows.append(
            {
                "file": path.name,
                "experiment_id": payload.get("experiment_id") or path.stem,
                "Recall@5": payload["Recall@5"],
                "Recall@1": payload.get("Recall@1"),
                "MRR": payload.get("MRR"),
                "Faithfulness": payload.get("Faithfulness"),
                "p50_latency": payload.get("p50_latency"),
                "correct_refusal": payload.get("correct_refusal"),
                **score,
                **cites,
                "by_type": _types(path),
            }
        )
    rows.sort(key=lambda item: item["production_score"], reverse=True)
    topk = None
    hybrid = folder / "hybrid.json"
    if hybrid.exists():
        gold = {q.id: q for q in load_dataset()}
        payload = json.loads(hybrid.read_text(encoding="utf-8"))
        topk = sweep_topk(gold, payload["per_question"], [1, 3, 5, 10, 20, 50])
    return {"leaderboard": rows, "topk_hybrid": topk}


def write_leaderboard(path: Path | None = None) -> Path:
    target = path or RESULTS / "leaderboard.json"
    payload = build_leaderboard()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
