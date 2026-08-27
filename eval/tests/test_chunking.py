from __future__ import annotations

from hakim_bench.chunking import sentence_chunks, window_chunks
from hakim_bench.experiments import get_experiment
from hakim_bench.score import production_score


def test_window_chunks_respect_size_and_overlap() -> None:
    text = "a" * 100
    parts = window_chunks(text, 40, 10)
    assert parts[0] == "a" * 40
    assert all(len(p) <= 40 for p in parts)
    assert len(parts) >= 3


def test_sentence_chunks_pack_until_limit() -> None:
    text = "Birinci cümle. İkinci cümle. Üçüncü cümle."
    packed = sentence_chunks(text, max_chars=40)
    assert len(packed) >= 1
    assert "Birinci" in packed[0]


def test_new_experiments_are_registered() -> None:
    assert get_experiment("hybrid_mq").query_strategy == "multi_query"
    assert get_experiment("hybrid_bm25w").bm25_weight == 0.8
    assert get_experiment("chunk512").chunk_size == 512
    assert get_experiment("dense_hash").embedding_model == "HashingEmbedder"


def test_production_score_prefers_fast_accurate() -> None:
    fast = production_score({"Recall@5": 0.8, "Faithfulness": 0.9, "MRR": 0.7, "p50_latency": 100, "cost_per_query": 0, "correct_refusal": 0.9})
    slow = production_score({"Recall@5": 0.8, "Faithfulness": 0.9, "MRR": 0.7, "p50_latency": 3000, "cost_per_query": 0, "correct_refusal": 0.0})
    assert fast["production_score"] > slow["production_score"]
