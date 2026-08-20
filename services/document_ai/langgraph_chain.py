from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from document_ai.observability import (
    flush_langfuse,
    init_langfuse,
    langfuse_configured,
    trace_url,
)
from document_ai.pipeline import (
    GRAPH_EDGES,
    GRAPH_NODES,
    Analysis,
    step_havale,
    step_mevzuat,
    step_okuyucu,
    step_sinif,
    step_sure,
    step_taslak,
)


class HakimState(TypedDict, total=False):
    text: str
    retrieve: Any
    quoted: str
    agents: list
    classification: Any
    dates: Any
    fields: Any
    missing: Any
    findings: Any
    related: Any
    deadlines: Any
    analysis: Any


def _traced(name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]):
    def node(state: HakimState) -> HakimState:
        work = dict(state)
        if not langfuse_configured():
            return fn(work)  # type: ignore[return-value]
        try:
            from langfuse import get_client

            with get_client().start_as_current_observation(name=name, as_type="agent"):
                return fn(work)  # type: ignore[return-value]
        except Exception:
            return fn(work)  # type: ignore[return-value]

    node.__name__ = name
    return node


def compile_hakim_graph():
    graph: StateGraph = StateGraph(HakimState)
    graph.add_node("okuyucu", _traced("okuyucu", step_okuyucu))
    graph.add_node("sinif", _traced("sinif", step_sinif))
    graph.add_node("mevzuat", _traced("mevzuat", step_mevzuat))
    graph.add_node("sure", _traced("sure", step_sure))
    graph.add_node("taslak", _traced("taslak", step_taslak))
    graph.add_node("havale", _traced("havale", step_havale))
    graph.add_edge(START, "okuyucu")
    for src, dst in GRAPH_EDGES:
        graph.add_edge(src, dst)
    graph.add_edge("havale", END)
    return graph.compile()


_GRAPH = None


def hakim_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = compile_hakim_graph()
    return _GRAPH


def run_hakim_graph(text: str, *, retrieve: Any = None) -> Analysis:
    init_langfuse()
    invoke = hakim_graph().invoke
    payload: HakimState = {"text": text, "retrieve": retrieve, "agents": []}
    tid: str | None = None
    url: str | None = None
    if langfuse_configured():
        try:
            from langfuse import get_client

            lf = get_client()
            with lf.start_as_current_observation(name="hakim-langgraph", as_type="chain"):
                result = invoke(payload)
                tid = lf.get_current_trace_id()
                url = lf.get_trace_url(trace_id=tid) if tid else None
        except Exception:
            result = invoke(payload)
    else:
        result = invoke(payload)
    analysis: Analysis = result["analysis"]
    analysis.observability = {
        "engine": "langgraph",
        "graph_nodes": list(GRAPH_NODES),
        "graph_edges": [{"source": a, "target": b} for a, b in GRAPH_EDGES],
        "langfuse_enabled": langfuse_configured(),
        "langfuse_trace_id": tid,
        "langfuse_url": url or trace_url(tid),
    }
    flush_langfuse()
    return analysis
