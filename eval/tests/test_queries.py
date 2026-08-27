from __future__ import annotations

from hakim_bench.queries import expand_queries


def test_original_strategy_keeps_query() -> None:
    assert expand_queries("kast nedir", "original") == ["kast nedir"]


def test_multi_query_adds_variants_and_group_members() -> None:
    variants = expand_queries("öldürme suçları hangileridir?", "multi_query")
    assert variants[0] == "öldürme suçları hangileridir?"
    assert any("kasten öldürme" in item for item in variants)
    assert len(variants) > 1


def test_expand_adds_synonyms() -> None:
    variants = expand_queries("dolandırıcılık cezası", "expand")
    assert any("nitelikli" in item for item in variants)


def test_empty_query_does_not_crash() -> None:
    assert expand_queries("", "multi_query") == [""]
