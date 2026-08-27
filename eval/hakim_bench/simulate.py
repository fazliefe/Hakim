from __future__ import annotations

from hakim_bench.metrics import mean, ndcg_at, percentile, precision_at, recall_at, reciprocal_rank
from hakim_bench.schema import GoldQuestion, RetrievedHit


def hits_from_row(row: dict) -> list[RetrievedHit]:
    out: list[RetrievedHit] = []
    for item in row.get("retrieved") or []:
        out.append(
            RetrievedHit(
                chunk_id=str(item.get("chunk_id") or ""),
                document_id=item.get("document_id"),
                law_no=item.get("law_no"),
                article_no=item.get("article_no"),
                score=float(item.get("score") or 0.0),
                rank=int(item.get("rank") or 0),
                content="",
            )
        )
    return out


def apply_threshold(hits: list[RetrievedHit], threshold: float | None) -> list[RetrievedHit]:
    if threshold is None:
        kept = list(hits)
    else:
        kept = [h for h in hits if h.score >= threshold]
    return [
        RetrievedHit(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            law_no=h.law_no,
            article_no=h.article_no,
            score=h.score,
            rank=i,
            content=h.content,
            title=h.title,
        )
        for i, h in enumerate(kept, start=1)
    ]


def apply_topk(hits: list[RetrievedHit], k: int) -> list[RetrievedHit]:
    return apply_threshold(hits[:k], None)


def retrieval_snapshot(gold: GoldQuestion, hits: list[RetrievedHit]) -> dict[str, float]:
    if not gold.answerable:
        return {
            "Recall@5": 0.0,
            "Recall@10": 0.0,
            "MRR": 0.0,
            "nDCG@10": 0.0,
            "Precision@5": 0.0,
            "correct_refusal": 1.0 if not hits else 0.0,
            "empty": 1.0 if not hits else 0.0,
        }
    return {
        "Recall@5": recall_at(gold, hits, 5),
        "Recall@10": recall_at(gold, hits, 10),
        "MRR": reciprocal_rank(gold, hits),
        "nDCG@10": ndcg_at(gold, hits, 10),
        "Precision@5": precision_at(gold, hits, 5),
        "correct_refusal": 0.0,
        "empty": 1.0 if not hits else 0.0,
    }


def sweep_threshold(
    gold_by_id: dict[str, GoldQuestion],
    rows: list[dict],
    thresholds: list[float | None],
) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for threshold in thresholds:
        answerable: list[dict[str, float]] = []
        unans: list[dict[str, float]] = []
        for row in rows:
            gold = gold_by_id[row["id"]]
            hits = apply_threshold(hits_from_row(row), threshold)
            snap = retrieval_snapshot(gold, hits)
            (unans if not gold.answerable else answerable).append(snap)
        out.append(
            {
                "threshold": None if threshold is None else float(threshold),
                "Recall@5": mean([s["Recall@5"] for s in answerable]),
                "MRR": mean([s["MRR"] for s in answerable]),
                "correct_refusal": mean([s["correct_refusal"] for s in unans]),
                "answerable_empty": mean([s["empty"] for s in answerable]),
            }
        )
    return out


def sweep_topk(
    gold_by_id: dict[str, GoldQuestion],
    rows: list[dict],
    ks: list[int],
) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    answerable_rows = [row for row in rows if gold_by_id[row["id"]].answerable]
    for k in ks:
        snaps = []
        recalls: list[float] = []
        for row in answerable_rows:
            gold = gold_by_id[row["id"]]
            hits = apply_topk(hits_from_row(row), k)
            snaps.append(retrieval_snapshot(gold, hits))
            recalls.append(recall_at(gold, hits, k))
        out.append(
            {
                "k": float(k),
                "Recall@K": mean(recalls),
                "MRR": mean([s["MRR"] for s in snaps]),
                "nDCG@10": mean([s["nDCG@10"] for s in snaps]),
                "Precision@5": mean([s["Precision@5"] for s in snaps]),
            }
        )
    return out


def top1_scores(
    gold_by_id: dict[str, GoldQuestion],
    rows: list[dict],
) -> tuple[list[float], list[float]]:
    answerable: list[float] = []
    unanswerable: list[float] = []
    for row in rows:
        hits = hits_from_row(row)
        top = hits[0].score if hits else 0.0
        if gold_by_id[row["id"]].answerable:
            answerable.append(top)
        else:
            unanswerable.append(top)
    return answerable, unanswerable
