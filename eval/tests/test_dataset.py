from __future__ import annotations

from collections import Counter

from hakim_bench.dataset import DATASET_PATH, TARGET_MIX, load_dataset, mix_share, stratified_sample


def test_gold_dataset_meets_phase0_size_and_schema() -> None:
    rows = load_dataset()
    assert DATASET_PATH.exists()
    assert 300 <= len(rows) <= 600
    ids = [row.id for row in rows]
    assert len(ids) == len(set(ids))
    for row in rows:
        assert row.question.strip()
        assert row.expected_answer.strip()
        if row.answerable:
            assert row.article_keys or row.relevant_chunks or row.relevant_documents
        else:
            assert row.question_type == "unanswerable"
            assert not row.article_keys


def test_gold_dataset_category_mix_matches_plan() -> None:
    rows = load_dataset()
    counts = Counter(row.question_type for row in rows)
    share = mix_share(counts, len(rows))
    for qtype, target in TARGET_MIX.items():
        assert qtype in share, qtype
        assert abs(share[qtype] - target) <= 0.04, (qtype, share[qtype], target)


def test_stratified_sample_keeps_plan_mix() -> None:
    rows = stratified_sample(load_dataset(), 100)
    assert len(rows) == 100
    counts = Counter(row.question_type for row in rows)
    share = mix_share(counts, len(rows))
    for qtype, target in TARGET_MIX.items():
        assert abs(share[qtype] - target) <= 0.04, (qtype, share[qtype], target)
