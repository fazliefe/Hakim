from __future__ import annotations

import math
import re
from collections import Counter

from hakim_bench.schema import GoldQuestion, RetrievedHit

_WORD_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", re.UNICODE)
_REFUSAL_MARKERS = (
    "mevcut kaynaklarda bulunmuyor",
    "kaynaklarda bulunmuyor",
    "bilgi bulunamadı",
    "bilgi mevcut değil",
    "cevaplanamıyor",
    "kaynaklarda yok",
    "bağlamda yer almıyor",
    "belgede yok",
)


def tokens(text: str) -> list[str]:
    return [tok.lower() for tok in _WORD_RE.findall(text or "")]


def is_relevant(gold: GoldQuestion, hit: RetrievedHit) -> bool:
    if hit.chunk_id and hit.chunk_id in gold.relevant_chunks:
        return True
    key = (str(hit.law_no or ""), str(hit.article_no or ""))
    if gold.article_keys and key in gold.article_keys:
        return True
    if gold.article_keys:
        return False
    doc = hit.document_id or ""
    return bool(doc and doc in gold.relevant_documents and not doc.startswith("law:"))


def _topk(hits: list[RetrievedHit], k: int) -> list[RetrievedHit]:
    return sorted(hits, key=lambda h: h.rank)[:k]


def recall_at(gold: GoldQuestion, hits: list[RetrievedHit], k: int) -> float:
    relevant = gold.article_keys or frozenset()
    if not relevant and gold.relevant_chunks:
        retrieved = {h.chunk_id for h in _topk(hits, k)}
        need = set(gold.relevant_chunks)
        return len(need & retrieved) / len(need)
    if not relevant:
        return 0.0
    found: set[tuple[str, str]] = set()
    for hit in _topk(hits, k):
        key = (str(hit.law_no or ""), str(hit.article_no or ""))
        if is_relevant(gold, hit):
            found.add(key)
    return len(found & relevant) / len(relevant)


def precision_at(gold: GoldQuestion, hits: list[RetrievedHit], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for hit in _topk(hits, k) if is_relevant(gold, hit)) / k


def reciprocal_rank(gold: GoldQuestion, hits: list[RetrievedHit]) -> float:
    for hit in sorted(hits, key=lambda h: h.rank):
        if is_relevant(gold, hit):
            return 1.0 / hit.rank
    return 0.0


def ndcg_at(gold: GoldQuestion, hits: list[RetrievedHit], k: int) -> float:
    seen: set[tuple[str, str] | str] = set()
    gains: list[float] = []
    for hit in _topk(hits, k):
        key = _gold_key(gold, hit)
        if key and key not in seen:
            seen.add(key)
            gains.append(1.0)
        else:
            gains.append(0.0)
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal_n = min(k, len(gold.article_keys) or len(gold.relevant_chunks) or 0)
    if ideal_n <= 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_n))
    return min(1.0, dcg / idcg) if idcg else 0.0


def _gold_key(gold: GoldQuestion, hit: RetrievedHit) -> tuple[str, str] | str | None:
    if gold.article_keys:
        key = (str(hit.law_no or ""), str(hit.article_no or ""))
        return key if key in gold.article_keys else None
    if hit.chunk_id and hit.chunk_id in gold.relevant_chunks:
        return hit.chunk_id
    return None


def context_metrics(gold: GoldQuestion, hits: list[RetrievedHit]) -> dict[str, float]:
    if not hits:
        return {"context_precision": 0.0, "context_recall": 0.0}
    found = {_gold_key(gold, hit) for hit in hits}
    found.discard(None)
    relevant_hits = sum(1 for hit in hits if is_relevant(gold, hit))
    need = len(gold.article_keys) or len(gold.relevant_chunks) or 0
    return {
        "context_precision": relevant_hits / len(hits),
        "context_recall": min(1.0, (len(found) / need) if need else 0.0),
    }


_CITE_RE = re.compile(r"\[(\d+)\s*m\.?\s*([0-9]+(?:/[A-Za-z])?)\]", re.IGNORECASE)


def citation_metrics(gold: GoldQuestion, answer: str) -> dict[str, float]:
    found = {(law, art) for law, art in _CITE_RE.findall(answer or "")}
    need = gold.article_keys
    if not gold.answerable:
        return {
            "citation_precision": 1.0 if not found else 0.0,
            "citation_recall": 1.0 if not found else 0.0,
        }
    if not found:
        return {"citation_precision": 0.0, "citation_recall": 0.0}
    if not need:
        return {"citation_precision": 0.0, "citation_recall": 0.0}
    hit = found & need
    return {
        "citation_precision": len(hit) / len(found),
        "citation_recall": len(hit) / len(need),
    }


def is_refusal(text: str) -> bool:
    compact = (text or "").strip().lower()
    return any(marker in compact for marker in _REFUSAL_MARKERS)


def mentions_gold_articles(gold: GoldQuestion, answer: str) -> bool:
    """True when every gold madde shows up (m.158 / madde 158 / 158. madde)."""
    if not gold.article_keys:
        return False
    text = answer or ""
    return all(_article_mentioned(text, article_no) for _law, article_no in gold.article_keys)


def _article_mentioned(text: str, article_no: str) -> bool:
    art = re.escape(article_no)
    patterns = (
        rf"\bm\.\s*{art}\b",
        rf"\bmadde\s+{art}\b",
        rf"\b{art}\.\s*madd",
        rf"(?:tck|cmk|iyuk|tmk|tbk|iik)\s+m?\.?\s*{art}\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _f1(pred: str, gold: str) -> float:
    pred_t = tokens(pred)
    gold_t = tokens(gold)
    if not pred_t or not gold_t:
        return 0.0
    overlap = sum((Counter(pred_t) & Counter(gold_t)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_t)
    rec = overlap / len(gold_t)
    return 2 * precision * rec / (precision + rec)


def answer_metrics(gold: GoldQuestion, answer: str, *, context: str) -> dict[str, float]:
    refused = is_refusal(answer)
    if not gold.answerable:
        return {
            "correctness": 1.0 if refused else 0.0,
            "relevance": 1.0 if refused else 0.0,
            "faithfulness": 1.0 if refused else 0.0,
            "hallucination": 0.0 if refused else 1.0,
            "correct_refusal": 1.0 if refused else 0.0,
        }
    expected = gold.expected_answer.casefold()
    compact = (answer or "").casefold()
    correctness = 1.0 if expected and expected in compact else _f1(answer, gold.expected_answer)
    if mentions_gold_articles(gold, answer):
        correctness = 1.0
    q_overlap = _f1(answer, gold.question)
    ctx_tokens = set(tokens(context))
    ans_tokens = tokens(answer)
    if not ans_tokens:
        faithfulness = 0.0
    elif not ctx_tokens:
        faithfulness = 0.0
    else:
        faithfulness = sum(1 for tok in ans_tokens if tok in ctx_tokens) / len(ans_tokens)
    return {
        "correctness": correctness,
        "relevance": q_overlap,
        "faithfulness": faithfulness,
        "hallucination": 1.0 - faithfulness,
        "correct_refusal": 0.0,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((p / 100.0) * len(ordered)))
    return float(ordered[rank - 1])


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
