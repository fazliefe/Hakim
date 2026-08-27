from __future__ import annotations

import time
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from document_ai.observability import (
    flush_langfuse,
    init_langfuse,
    langfuse_configured,
    trace_url,
)
from retrieval.adaptive import bm25_is_enough, query_is_off_topic
from retrieval.bm25 import parse_law_hint
from retrieval.hybrid import _is_exact_citation_query
from retrieval.query_expand import expand_queries, query_needs_multi
from retrieval.rerank import rerank_fused
from retrieval.research import _build_trace, _focus_query, assemble_research_result, collect_neighbors

GRAPH_NODES = ("sorgu", "kontrol", "bm25", "vektor", "rrf", "rerank", "graf", "cevap", "reddet")
GRAPH_EDGES = (
    ("sorgu", "kontrol"),
    ("kontrol", "bm25"),
    ("kontrol", "reddet"),
    ("bm25", "vektor"),
    ("vektor", "rrf"),
    ("rrf", "rerank"),
    ("rerank", "graf"),
    ("graf", "cevap"),
    ("cevap", "vektor"),
)


class ResearchState(TypedDict, total=False):
    engine: Any
    query: str
    law_no: str | None
    search_law: str | None
    hops: list
    bm25_hits: list
    semantic_hits: list
    decision_bm25_hits: list
    decision_semantic_hits: list
    fused: list
    route: str
    neighbors: dict
    result: Any
    off_topic: bool
    bm25_ok: bool
    force_semantic: bool
    need_retry: bool
    attempt: int
    multi_query: bool


def _hop(
    hops: list[dict[str, Any]],
    hop_id: str,
    title: str,
    started: float,
    *,
    state: str = "done",
    summary: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    hops.append(
        {
            "id": hop_id,
            "title": title,
            "ms": max(0, int((time.perf_counter() - started) * 1000)),
            "state": state,
            "summary": summary,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "cost_usd": round(float(cost_usd), 8),
        }
    )


def _traced(name: str, fn: Callable[[ResearchState], ResearchState]):
    def node(state: ResearchState) -> ResearchState:
        work = dict(state)
        if not langfuse_configured():
            return fn(work)  # type: ignore[return-value]
        try:
            from langfuse import get_client

            with get_client().start_as_current_observation(name=name, as_type="span"):
                return fn(work)  # type: ignore[return-value]
        except Exception:
            return fn(work)  # type: ignore[return-value]

    node.__name__ = name
    return node


def _route_after_kontrol(state: ResearchState) -> str:
    return "reddet" if state.get("off_topic") else "bm25"


def _route_after_cevap(state: ResearchState) -> str:
    return "vektor" if state.get("need_retry") else END


def _node_sorgu(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    query = (state.get("query") or "").strip()
    hinted = parse_law_hint(query)
    search_law = hinted if hinted else state.get("law_no")
    multi = False
    try:
        from hakim_config import get_models

        multi = bool(get_models().multi_query_aggregation and query_needs_multi(query))
    except Exception:
        multi = query_needs_multi(query)
    hops = list(state.get("hops") or [])
    _hop(hops, "sorgu", "Sorgu", started, summary=query[:220] or "boş sorgu")
    return {
        "search_law": search_law,
        "hops": hops,
        "multi_query": multi,
        "force_semantic": True if multi else bool(state.get("force_semantic")),
    }


def _node_kontrol(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    off_topic = query_is_off_topic(state.get("query") or "")
    hops = list(state.get("hops") or [])
    _hop(
        hops,
        "kontrol",
        "Kontrol",
        started,
        state="warn" if off_topic else "done",
        summary="hukuk dışı" if off_topic else "hukuki sorgu",
    )
    return {"off_topic": off_topic, "hops": hops}


def _node_bm25(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    hits = state["engine"].hybrid.search_bm25(state["query"], law_no=state.get("search_law"))
    enough = bm25_is_enough(state["query"], hits)
    hops = list(state.get("hops") or [])
    # Emsal karar index'i (Yargıtay/Danıştay) yalnızca law_no'suz (serbest
    # metin) sorgularda dahil edilir — madde arayan biri sadece madde
    # metnini görsün (kullanıcı kararı, bkz. HybridSearcher.search).
    decision_hits = (
        state["engine"].hybrid.search_decision_bm25(state["query"])
        if state.get("search_law") is None
        else []
    )
    summary = f"{len(hits)} sonuç"
    if decision_hits:
        summary += f" · {len(decision_hits)} emsal karar"
    summary += " · yeter" if enough else " · semantic gerekir"
    _hop(hops, "bm25", "BM25", started, summary=summary, state="done" if hits else "warn")
    return {"bm25_hits": hits, "decision_bm25_hits": decision_hits, "bm25_ok": enough, "hops": hops}


def _node_vektor(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    hops = list(state.get("hops") or [])
    skip = not state.get("force_semantic") and bool(state.get("bm25_ok"))
    if skip:
        _hop(
            hops,
            "vektor",
            "Vektör",
            started,
            state="skip",
            summary="BM25 yeterli; vektör atlandı",
        )
        return {"semantic_hits": [], "decision_semantic_hits": [], "hops": hops}
    hits = state["engine"].hybrid.search_semantic(state["query"], law_no=state.get("search_law"))
    decision_hits = (
        state["engine"].hybrid.search_decision_semantic(state["query"])
        if state.get("search_law") is None
        else []
    )
    summary = f"{len(hits)} sonuç"
    if decision_hits:
        summary += f" · {len(decision_hits)} emsal karar"
    _hop(hops, "vektor", "Vektör", started, summary=summary, state="done" if hits else "warn")
    return {"semantic_hits": hits, "decision_semantic_hits": decision_hits, "hops": hops}


def _node_rrf(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    query = state["query"]
    engine = state["engine"]
    if state.get("multi_query") and hasattr(engine.hybrid, "search_multi"):
        fused = engine.hybrid.search_multi(
            expand_queries(query, "multi_query"),
            law_no=state.get("search_law"),
            limit=12,
        )
        route = "multi_query"
    else:
        fused = engine.hybrid.fuse(
            query,
            state.get("bm25_hits") or [],
            state.get("semantic_hits") or [],
            limit=12,
            decision_bm25_hits=state.get("decision_bm25_hits") or [],
            decision_semantic_hits=state.get("decision_semantic_hits") or [],
        )
        if _is_exact_citation_query(query):
            route = "exact_citation"
        elif state.get("semantic_hits"):
            route = "hybrid"
        else:
            route = "bm25"
    gate_note = ""
    try:
        from hakim_config import get_models

        threshold = float(get_models().dense_gate or 0.0)
    except Exception:
        threshold = 0.0
    if threshold > 0 and fused and not _is_exact_citation_query(query):
        semantic = list(state.get("semantic_hits") or [])
        if not semantic and hasattr(engine.hybrid, "search_semantic"):
            semantic = engine.hybrid.search_semantic(query, law_no=state.get("search_law"))[:1]
        top = float(semantic[0].score) if semantic else 0.0
        if semantic and top < threshold:
            fused = []
            gate_note = f" · dense kapı {top:.2f}<{threshold:.2f}"
            route = "refuse"
    hops = list(state.get("hops") or [])
    _hop(hops, "rrf", "Birleşim", started, summary=f"{len(fused)} kaynak · {route}{gate_note}")
    return {"fused": fused, "route": route, "hops": hops}


def _node_rerank(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    fused = list(state.get("fused") or [])
    hops = list(state.get("hops") or [])
    enabled = True
    try:
        from hakim_config import get_models

        enabled = bool(get_models().rerank_enabled)
    except Exception:
        enabled = True
    if not enabled:
        _hop(hops, "rerank", "Rerank", started, state="skip", summary="RRF sırası korundu")
        return {"fused": fused, "hops": hops}
    scorer = getattr(state.get("engine"), "reranker", None)
    ranked = rerank_fused(state["query"], fused, limit=12, scorer=scorer)
    method = "cross-encoder" if scorer is not None else "lexical"
    _hop(hops, "rerank", "Rerank", started, summary=f"{len(ranked)} kaynak yeniden sıralandı ({method})")
    return {"fused": ranked, "hops": hops}


def _node_graf(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    fused = list(state.get("fused") or [])
    engine = state["engine"]
    neighbors = collect_neighbors(engine, fused[: engine.evidence_limit])
    linked = sum(len(rows) for rows in neighbors.values())
    hops = list(state.get("hops") or [])
    _hop(
        hops,
        "graf",
        "Graf",
        started,
        summary=f"{linked} komşu" if linked else "Komşu yok",
        state="done" if linked else "skip",
    )
    return {"neighbors": neighbors, "hops": hops}


def _node_cevap(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    from llm.usage import estimate_cost, reset_usage, take_usage

    reset_usage()
    result = assemble_research_result(
        state["engine"],
        state["query"],
        list(state.get("fused") or []),
        str(state.get("route") or "hybrid"),
        state.get("neighbors") or {},
    )
    usage = take_usage()
    cost = estimate_cost(usage.prompt_tokens, usage.completion_tokens) if usage.total_tokens else 0.0
    attempt = int(state.get("attempt") or 0)
    need_retry = False
    if (
        attempt < 1
        and not state.get("off_topic")
        and not _is_exact_citation_query(state["query"])
        and ((state.get("bm25_ok") and result.writer == "refuse") or bool(result.writer_error))
    ):
        need_retry = True
    hops = list(state.get("hops") or [])
    _hop(
        hops,
        "cevap",
        "Cevap",
        started,
        summary=("yeniden dene" if need_retry else result.writer),
        state="warn" if need_retry or result.writer == "refuse" else "done",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        cost_usd=cost,
    )
    return {
        "result": result,
        "hops": hops,
        "need_retry": need_retry,
        "attempt": attempt + 1 if need_retry else attempt,
        "force_semantic": True if need_retry else bool(state.get("force_semantic")),
        "bm25_ok": False if need_retry else bool(state.get("bm25_ok")),
    }


def _node_reddet(state: ResearchState) -> ResearchState:
    started = time.perf_counter()
    from retrieval.research import ResearchResult, _build_trace, _refuse_answer, build_research_reasoning

    query = (state.get("query") or "").strip()
    answer = _refuse_answer()
    nodes, edges = _build_trace(query, [], "refuse")
    result = ResearchResult(
        query=query,
        answer=answer,
        evidence=[],
        trace_nodes=nodes,
        trace_edges=edges,
        route="refuse",
        writer="refuse",
        writer_error=None,
        reasoning=build_research_reasoning(query, [], route="refuse", answer=answer, refused=True),
    )
    hops = list(state.get("hops") or [])
    _hop(hops, "reddet", "Reddet", started, state="warn", summary="hukuk araştırması kapsamı dışında")
    return {"result": result, "hops": hops}


def compile_research_graph():
    graph: StateGraph = StateGraph(ResearchState)
    graph.add_node("sorgu", _traced("sorgu", _node_sorgu))
    graph.add_node("kontrol", _traced("kontrol", _node_kontrol))
    graph.add_node("bm25", _traced("bm25", _node_bm25))
    graph.add_node("vektor", _traced("vektor", _node_vektor))
    graph.add_node("rrf", _traced("rrf", _node_rrf))
    graph.add_node("rerank", _traced("rerank", _node_rerank))
    graph.add_node("graf", _traced("graf", _node_graf))
    graph.add_node("cevap", _traced("cevap", _node_cevap))
    graph.add_node("reddet", _traced("reddet", _node_reddet))
    graph.add_edge(START, "sorgu")
    graph.add_edge("sorgu", "kontrol")
    graph.add_conditional_edges("kontrol", _route_after_kontrol, {"bm25": "bm25", "reddet": "reddet"})
    graph.add_edge("bm25", "vektor")
    graph.add_edge("vektor", "rrf")
    graph.add_edge("rrf", "rerank")
    graph.add_edge("rerank", "graf")
    graph.add_edge("graf", "cevap")
    graph.add_conditional_edges("cevap", _route_after_cevap, {"vektor": "vektor", END: END})
    graph.add_edge("reddet", END)
    return graph.compile()


_GRAPH = None


def research_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = compile_research_graph()
    return _GRAPH


def build_observability(
    hops: list[dict[str, Any]],
    tid: str | None = None,
    url: str | None = None,
    *,
    langfuse_enabled: bool | None = None,
) -> dict[str, Any]:
    enabled = langfuse_configured() if langfuse_enabled is None else langfuse_enabled
    model = ""
    provider = ""
    label = ""
    try:
        from hakim_config import get_models, model_label

        cfg = get_models()
        model = cfg.llm_model
        provider = cfg.profile
        label = model_label(cfg)
    except Exception:
        model = ""
    prompt_tokens = sum(int(item.get("prompt_tokens") or 0) for item in hops)
    completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in hops)
    from llm.usage import _cost_is_estimated

    return {
        "engine": "langgraph",
        "graph_nodes": list(GRAPH_NODES),
        "graph_edges": [{"source": a, "target": b} for a, b in GRAPH_EDGES],
        "langfuse_enabled": enabled,
        "langfuse_trace_id": tid,
        "langfuse_url": url or trace_url(tid),
        "hops": hops,
        "totals": {
            "ms": sum(int(item.get("ms") or 0) for item in hops),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": round(sum(float(item.get("cost_usd") or 0) for item in hops), 8),
            "cost_estimated": _cost_is_estimated(prompt_tokens, completion_tokens),
            "provider": provider,
            "model": model,
            "model_label": label,
        },
    }


def run_research_graph(engine: Any, query: str, *, law_no: str | None = None):
    init_langfuse()
    from llm.usage import reset_usage

    reset_usage()
    payload: ResearchState = {
        "engine": engine,
        "query": _focus_query(query.strip()),
        "law_no": law_no,
        "hops": [],
        "attempt": 0,
        "force_semantic": False,
        "need_retry": False,
        "multi_query": False,
    }
    invoke = research_graph().invoke
    tid: str | None = None
    url: str | None = None
    if langfuse_configured():
        try:
            from langfuse import get_client

            lf = get_client()
            with lf.start_as_current_observation(name="hakim-research", as_type="chain"):
                finished = invoke(payload)
                tid = lf.get_current_trace_id()
                url = lf.get_trace_url(trace_id=tid) if tid else None
        except Exception:
            finished = invoke(payload)
    else:
        finished = invoke(payload)
    result = finished["result"]
    hops = list(finished.get("hops") or [])
    result.observability = build_observability(hops, tid=tid, url=url)
    result.trace_nodes, result.trace_edges = _build_trace(
        result.query,
        [],
        result.route,
        hops=hops,
        evidence=result.evidence,
    )
    flush_langfuse()
    return result
