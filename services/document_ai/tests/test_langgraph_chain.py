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


def test_langgraph_mevzuat_conditional_retry() -> None:
    """`mevzuat` düğümü gerçek bir add_conditional_edges ile kendine dönüyor:
    dar sorgu boş dönerse graf aynı node'u geniş sorguyla bir kez daha çalıştırır."""
    seen: list[str] = []

    def retrieve(query: str, at=None):
        seen.append(query)
        if len(seen) == 1:
            return []
        return [{"n": 1, "title": "TCK 158", "article_no": "158", "law_no": "5237", "content": "Madde 158"}]

    analysis = analyze_document(
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026",
        retrieve=retrieve,
    )
    assert analysis.observability.get("engine") == "langgraph"
    assert len(seen) == 2
    assert analysis.related and analysis.related[0]["article_no"] == "158"
    # graf tekrar denese de yalnız tek bir "mevzuat" ajan kartı üretir
    assert [item["id"] for item in analysis.agents].count("mevzuat") == 1
