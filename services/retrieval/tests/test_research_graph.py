from retrieval.research_graph import GRAPH_EDGES, GRAPH_NODES, build_observability, compile_research_graph


def test_research_graph_has_routing_nodes() -> None:
    compiled = compile_research_graph()
    names = set(compiled.get_graph().nodes)
    for node in GRAPH_NODES:
        assert node in names
    assert ("sorgu", "kontrol") in GRAPH_EDGES or any(e[0] == "sorgu" and e[1] == "kontrol" for e in GRAPH_EDGES)
    assert any(e[0] == "bm25" and e[1] == "vektor" for e in GRAPH_EDGES)
    assert any(e[0] == "rrf" and e[1] == "rerank" for e in GRAPH_EDGES)
    assert any(e[0] == "cevap" and e[1] == "vektor" for e in GRAPH_EDGES)
    assert any(e[0] == "kontrol" and e[1] == "reddet" for e in GRAPH_EDGES)


def test_build_observability_sums_hops() -> None:
    hops = [
        {
            "id": "sorgu",
            "title": "Sorgu",
            "ms": 10,
            "state": "done",
            "summary": "soru",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
        },
        {
            "id": "cevap",
            "title": "Cevap",
            "ms": 90,
            "state": "done",
            "summary": "api",
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "cost_usd": 0.000135,
        },
    ]
    obs = build_observability(hops, tid="abc", url="https://us.cloud.langfuse.com/trace/abc")
    assert obs["engine"] == "langgraph"
    assert "kontrol" in obs["graph_nodes"]
    assert "rerank" in obs["graph_nodes"]
    assert obs["totals"]["ms"] == 100
    assert obs["totals"]["prompt_tokens"] == 1000
    assert obs["totals"]["completion_tokens"] == 200
    assert abs(obs["totals"]["cost_usd"] - 0.000135) < 1e-9
    assert obs["langfuse_trace_id"] == "abc"
    assert "langfuse.com" in (obs["langfuse_url"] or "")
    assert obs["totals"]["provider"] == "evren"
    assert obs["totals"]["model_label"] == "Evren · llm-fast"
    assert not str(obs["totals"]["model_label"]).lower().startswith("openai")


class _FakeHybrid:
    def __init__(self) -> None:
        self.semantic_calls = 0

    def search_bm25(self, query: str, **_kwargs):
        return []

    def search_semantic(self, query: str, **_kwargs):
        self.semantic_calls += 1
        return []

    def search_decision_bm25(self, query: str, **_kwargs):
        return []

    def search_decision_semantic(self, query: str, **_kwargs):
        return []

    def fuse(self, query: str, bm25_hits, semantic_hits, **_kwargs):
        return []


class _FakeEngine:
    def __init__(self) -> None:
        self.hybrid = _FakeHybrid()
        self.neo4j = None
        self.evidence_limit = 8


def test_detailed_query_runs_semantic() -> None:
    from retrieval.research_graph import run_research_graph

    engine = _FakeEngine()
    result = run_research_graph(engine, "nitelikli dolandırıcılıkta banka hesabı")
    hops = [hop["id"] for hop in result.observability["hops"]]
    assert hops[:3] == ["sorgu", "kontrol", "bm25"]
    assert "vektor" in hops
    assert "rerank" in hops
    assert "cevap" in hops
    assert engine.hybrid.semantic_calls >= 1
    vektor = next(hop for hop in result.observability["hops"] if hop["id"] == "vektor")
    assert vektor["state"] != "skip"


def test_exact_citation_skips_vector_hop() -> None:
    from retrieval.research_graph import run_research_graph

    engine = _FakeEngine()
    result = run_research_graph(engine, "madde 158")
    hops = {hop["id"]: hop for hop in result.observability["hops"]}
    assert hops["vektor"]["state"] == "skip"
    assert engine.hybrid.semantic_calls == 0


def test_off_topic_goes_to_reddet_without_search() -> None:
    from retrieval.research_graph import run_research_graph

    engine = _FakeEngine()
    result = run_research_graph(engine, "fenerbahçe maçı ne olur")
    hops = [hop["id"] for hop in result.observability["hops"]]
    assert hops == ["sorgu", "kontrol", "reddet"]
    assert result.writer == "refuse"
    assert engine.hybrid.semantic_calls == 0


def test_trace_follows_executed_hops_not_static_map() -> None:
    from retrieval.research_graph import run_research_graph

    engine = _FakeEngine()
    easy = run_research_graph(engine, "madde 158")
    easy_ids = {node.id for node in easy.trace_nodes}
    assert "bm25" in easy_ids
    assert "rrf" in easy_ids
    assert "vector" not in easy_ids
    easy_edges = {(edge.source, edge.target) for edge in easy.trace_edges}
    assert ("bm25", "rrf") in easy_edges
    assert ("bm25", "vector") not in easy_edges
    assert ("query", "vector") not in easy_edges

    detailed = run_research_graph(_FakeEngine(), "nitelikli dolandırıcılıkta banka hesabı")
    detailed_ids = {node.id for node in detailed.trace_nodes}
    assert "vector" in detailed_ids
    assert ("vector", "rrf") in {(edge.source, edge.target) for edge in detailed.trace_edges}

    refuse = run_research_graph(_FakeEngine(), "fenerbahçe maçı ne olur")
    refuse_ids = {node.id for node in refuse.trace_nodes if node.kind != "chunk"}
    assert refuse_ids == {"query", "answer"}
    assert any(edge.source == "query" and edge.target == "answer" for edge in refuse.trace_edges)
    assert "bm25" not in {node.id for node in refuse.trace_nodes}


def test_trace_retry_keeps_second_pass_and_drops_cite_graph() -> None:
    from retrieval.research import _build_trace

    hops = [
        {"id": "sorgu", "state": "done"},
        {"id": "kontrol", "state": "done"},
        {"id": "bm25", "state": "done"},
        {"id": "vektor", "state": "done"},
        {"id": "rrf", "state": "done"},
        {"id": "rerank", "state": "done"},
        {"id": "graf", "state": "done"},
        {"id": "cevap", "state": "warn"},
        {"id": "vektor", "state": "done"},
        {"id": "rrf", "state": "done"},
        {"id": "rerank", "state": "done"},
        {"id": "graf", "state": "done"},
        {"id": "cevap", "state": "done"},
    ]
    nodes, edges = _build_trace("nitelikli dolandırıcılık", [], "hybrid", hops=hops)
    ids = [node.id for node in nodes if node.kind != "chunk"]
    assert ids == [
        "query",
        "bm25",
        "vector",
        "rrf",
        "rerank",
        "graph",
        "answer",
        "vector#2",
        "rrf#2",
        "rerank#2",
        "graph#2",
        "answer#2",
    ]
    pairs = {(edge.source, edge.target) for edge in edges}
    assert ("answer", "vector#2") in pairs
    assert ("vector#2", "rrf#2") in pairs
    assert ("graph#2", "answer#2") in pairs
    assert all(edge.label != "cite-graph" for edge in edges)
