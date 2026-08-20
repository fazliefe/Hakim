from __future__ import annotations

from document_ai.langgraph_chain import GRAPH_EDGES, GRAPH_NODES, compile_hakim_graph
from document_ai.pipeline import analyze_document, analysis_to_dict


def test_graph_has_six_nodes() -> None:
    compiled = compile_hakim_graph()
    names = set(compiled.get_graph().nodes)
    for node in GRAPH_NODES:
        assert node in names
    assert GRAPH_EDGES[0] == ("okuyucu", "sinif")
    assert GRAPH_EDGES[-1] == ("taslak", "havale")


def test_langgraph_analyze_sets_observability() -> None:
    analysis = analyze_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın mahkûmiyetine karar verildi. Tebliğ tarihi: 14.08.2026"
    )
    assert analysis.observability.get("engine") == "langgraph"
    assert analysis.observability.get("graph_nodes") == list(GRAPH_NODES)
    payload = analysis_to_dict(analysis)
    assert payload["observability"]["engine"] == "langgraph"
    assert [item["id"] for item in analysis.agents] == list(GRAPH_NODES)
