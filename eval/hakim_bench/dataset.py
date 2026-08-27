from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from hakim_bench.schema import GoldQuestion

EVAL_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = EVAL_ROOT / "gold" / "rag_qa.jsonl"

TARGET_MIX = {
    "factual": 0.20,
    "semantic": 0.15,
    "keyword": 0.10,
    "comparison": 0.10,
    "multi_hop": 0.15,
    "aggregation": 0.10,
    "ambiguous": 0.05,
    "typo": 0.05,
    "unanswerable": 0.10,
}


def load_dataset(path: Path | None = None) -> list[GoldQuestion]:
    target = path or DATASET_PATH
    if not target.exists():
        return []
    rows: list[GoldQuestion] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(GoldQuestion.from_dict(json.loads(line)))
    return rows


def mix_share(counts: Counter[str], total: int) -> dict[str, float]:
    if total <= 0:
        return {}
    return {key: counts[key] / total for key in counts}


def stratified_sample(questions: list[GoldQuestion], n: int) -> list[GoldQuestion]:
    if n <= 0 or n >= len(questions):
        return list(questions)
    buckets: dict[str, list[GoldQuestion]] = {key: [] for key in TARGET_MIX}
    for item in questions:
        if item.question_type in buckets:
            buckets[item.question_type].append(item)
    chosen: list[GoldQuestion] = []
    seen: set[str] = set()
    for qtype, share in TARGET_MIX.items():
        take = max(1, round(n * share))
        for item in buckets[qtype][:take]:
            chosen.append(item)
            seen.add(item.id)
    if len(chosen) > n:
        chosen = chosen[:n]
        seen = {item.id for item in chosen}
    elif len(chosen) < n:
        for item in questions:
            if item.id in seen:
                continue
            chosen.append(item)
            seen.add(item.id)
            if len(chosen) >= n:
                break
    return chosen


def write_dataset(rows: list[GoldQuestion], path: Path | None = None) -> Path:
    target = path or DATASET_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row.to_dict(), ensure_ascii=False) for row in rows) + "\n"
    target.write_text(payload, encoding="utf-8")
    return target
