from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from retrieval.bm25 import extract_article_no, parse_law_hint
from hakim_legal_schema.ids import article_id

from graph.projector import neighborhood, neighborhood_decision
from retrieval.embeddings import Embedder, create_embedder
from retrieval.hybrid import HybridSearcher
from retrieval.rrf import FusedHit


@dataclass
class EvidenceItem:
    n: int
    chunk_id: str
    document_id: str | None
    law_no: str | None
    article_no: str | None
    title: str | None
    content: str
    authority: str | None
    bm25_rank: int | None
    semantic_rank: int | None
    rrf_rank: int
    rrf_score: float
    retrievers: list[str]
    graph_neighbors: list[dict[str, Any]] = field(default_factory=list)
    used_in_answer: bool = False


@dataclass
class TraceNode:
    id: str
    label: str
    kind: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEdge:
    source: str
    target: str
    label: str


@dataclass
class ResearchResult:
    query: str
    answer: str
    evidence: list[EvidenceItem]
    trace_nodes: list[TraceNode]
    trace_edges: list[TraceEdge]
    route: str
    writer: str = "extractive"
    writer_error: str | None = None
    reasoning: dict[str, Any] = field(default_factory=dict)


_LAW_SHORT = {
    "5237": "TCK",
    "5271": "CMK",
    "2577": "İYUK",
    "4721": "TMK",
    "6098": "TBK",
    "2004": "İİK",
    "7201": "Tebligat K.",
    "2709": "Anayasa",
    "6216": "6216 sayılı Kanun",
}


def _snippet(text: str, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _is_decision(item: EvidenceItem) -> bool:
    return (item.document_id or "").startswith("decision:")


def _cite(item: EvidenceItem) -> str:
    if _is_decision(item):
        return item.title or item.document_id or "Mahkeme kararı"
    prefix = _LAW_SHORT.get(item.law_no or "", f"Kanun {item.law_no}" if item.law_no else "Kanun")
    return f"{prefix} m.{item.article_no}"


def _source_label(item: EvidenceItem) -> str:
    if _is_decision(item):
        return item.title or item.document_id or "Mahkeme kararı"
    title = f" ({item.title})" if item.title else ""
    return f"{_cite(item)}{title}"


def _official_span(item: EvidenceItem, query: str = "", limit: int = 320) -> str:
    compact = " ".join((item.content or "").split())
    if not compact:
        return ""
    if _is_decision(item):
        return _first_sentence(compact, limit)
    match = re.search(r"Madde\s+[0-9]+[A-Za-z/]*\s*[-–—]?\s*", compact)
    if match:
        compact = compact[match.start() :]
    return _snippet(compact, limit)


def _first_sentence(text: str, limit: int = 220) -> str:
    compact = " ".join((text or "").split())
    match = re.search(r".+?[.!?…](?:\s|$)", compact)
    if match:
        return _snippet(match.group(0).strip(), limit)
    return _snippet(compact, limit)


_CLAUSE_STOP = frozenset(
    {
        "kullanılması",
        "kullanmak",
        "suretiyle",
        "olarak",
        "nitelikli",
        "suçunun",
        "maddesi",
        "hakkında",
        "şekilde",
        "aracılığıyla",
    }
)


def _query_tokens(query: str, *, min_len: int = 5) -> list[str]:
    return [
        tok
        for tok in re.findall(r"\w+", query.lower(), flags=re.UNICODE)
        if len(tok) >= min_len and tok not in _CLAUSE_STOP
    ]


def _clause_for_query(query: str, content: str) -> str | None:
    compact = " ".join((content or "").split())
    if not compact:
        return None
    tokens = _query_tokens(query, min_len=5)
    if not tokens:
        return None
    scored: list[tuple[int, str]] = []
    for part in re.split(r"(?=\b[a-h]\)\s)", compact):
        blob = " ".join(part.split())
        if not re.match(r"[a-h]\)\s", blob):
            continue
        body = _snippet(re.sub(r"^[a-h]\)\s*", "", blob).rstrip(" ;,"), 140)
        hits = [tok for tok in tokens if tok in body.lower()]
        if hits:
            scored.append((sum(len(tok) for tok in hits), body))
    if not scored:
        return None
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored[0][1]


def _is_procedure_query(query: str) -> bool:
    blob = (query or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return any(token in blob for token in ("nasil", "nedir", "ne zaman", "hangi usul", "nasıl"))


def _article_int(no: str | None) -> int | None:
    if not no:
        return None
    try:
        return int(str(no).split("/")[0])
    except ValueError:
        return None


def _is_close_provision(primary: EvidenceItem, item: EvidenceItem, query: str) -> bool:
    if _is_decision(item) or _is_decision(primary):
        return False
    if not (primary.law_no and item.law_no == primary.law_no):
        return False
    a, b = _article_int(primary.article_no), _article_int(item.article_no)
    return a is not None and b is not None and 0 < abs(a - b) <= 2


def _is_base_offence(primary: EvidenceItem, item: EvidenceItem) -> bool:
    if not _is_close_provision(primary, item, ""):
        return False
    a, b = _article_int(primary.article_no), _article_int(item.article_no)
    if a is not None and b is not None and b == a - 1:
        return True
    pt, it = (primary.title or "").lower(), (item.title or "").lower()
    return bool(it and pt and it != pt and it in pt)


def _draft_research_answer(engine: dict[str, Any]) -> tuple[str | None, str, str | None]:
    """Groq first. If it fails or dumps the madde, try local Ollama. Else extractive."""
    from llm.api_client import api_configured
    from llm.client import chat, ping
    from llm.writer import write_module, writer_name

    last_err: str | None = None
    if api_configured():
        try:
            drafted = write_module("arastirma", engine, allow_ollama=False)
            if _usable_draft(drafted, engine):
                return drafted, writer_name(allow_ollama=False), None
            if drafted:
                last_err = "API kısa veya hatalı metin yazdı"
        except Exception as exc:
            last_err = str(exc)[:280]
    if ping(timeout=1.5):
        try:
            drafted = write_module(
                "arastirma",
                engine,
                chat_fn=lambda messages, **_k: chat(messages, timeout=120, json_mode=True),
                allow_ollama=True,
            )
            if _usable_draft(drafted, engine):
                return drafted, "ollama", None
            if drafted:
                last_err = "Ollama kısa veya hatalı metin yazdı"
        except Exception as exc:
            last_err = str(exc)[:280]
    return None, "extractive", last_err


def _join_labels(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} ve {labels[-1]}"


def _looks_like_article_dump(text: str) -> bool:
    blob = text or ""
    if "en yakın resmi hüküm" in blob:
        return True
    return len(re.findall(r"\b[a-h]\)\s", blob)) >= 3


def _looks_like_garbage(text: str) -> bool:
    blob = text or ""
    if re.search(r"\[(?!\d+\])[^\]]+\]", blob):
        return True
    lowered = blob.lower()
    return "outcome" in lowered or "yaygın ad" in lowered


def _refuse_answer() -> str:
    return (
        "Bu sorgu hukuk araştırmasına uygun değil.\n\n"
        "HÂKİM yalnızca kanun maddesi, içtihat ve resmi belgelere dayanır. "
        "Spor sonucu, tahmin veya arşivde dayanağı olmayan sorulara cevap verilmez.\n\n"
        "Madde numarası veya hukuki kavramla yeniden deneyin."
    )


def _missing_citation_answer(law_no: str, article: str) -> str:
    name = _LAW_SHORT.get(law_no, f"Kanun {law_no}")
    return (
        f"Arşivde {name} m.{article} metni yok.\n\n"
        "Sorulan kanunun maddesi bulunmuyorken başka kanunun aynı numaralı maddesi "
        "cevap olarak yazılmaz.\n\n"
        "Bu madde arşive işlenince soru yeniden sorulabilir."
    )


def _query_supported(query: str, evidence: list[EvidenceItem]) -> bool:
    from retrieval.hybrid import _is_exact_citation_query

    hinted = parse_law_hint(query)
    article = extract_article_no(query)
    if hinted and article:
        return any(item.law_no == hinted and str(item.article_no) == str(article) for item in evidence)
    if _is_exact_citation_query(query):
        if article:
            return any(str(item.article_no) == str(article) for item in evidence)
        return True
    used = _answer_items(query, evidence) or evidence[:1]
    if not used:
        return False
    primary = used[0]
    tokens = _query_tokens(query, min_len=5)
    blob = f"{primary.title or ''} {primary.content or ''}".lower()
    if tokens and any(tok in blob for tok in tokens):
        return True
    if primary.bm25_rank:
        return True
    return False


def _answer_items(query: str, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    used = [item for item in evidence if item.used_in_answer][:5] or evidence[:5]
    if not used:
        return []
    primary = used[0]
    close = [item for item in used[1:] if _is_close_provision(primary, item, query)][:2]
    return [primary, *close]


def _allowed_articles(engine: dict[str, Any]) -> set[str]:
    return {
        str(item.get("article_no"))
        for item in engine.get("evidence") or []
        if item.get("article_no")
    }


def _mentions_foreign_article(text: str, allowed: set[str]) -> bool:
    if not allowed:
        return False
    found: set[str] = set()
    for pattern in (r"(?:TCK|CMK|TMK)\s+(?:m\.)?(\d+)", r"\bm\.(\d+)"):
        found.update(match.group(1) for match in re.finditer(pattern, text or "", re.I))
    return bool(found - allowed)


def _wrong_code_for_query(text: str, query: str) -> bool:
    hinted = parse_law_hint(query)
    article = extract_article_no(query)
    if not hinted or not article:
        return False
    short = _LAW_SHORT.get(hinted)
    if not short:
        return False
    blob = text or ""
    if re.search(rf"{re.escape(short)}\s*m\.\s*{re.escape(article)}", blob, re.I):
        return False
    return bool(re.search(rf"(?:TCK|CMK|TMK|İYUK|IYUK)\s*m\.\s*{re.escape(article)}", blob, re.I))


def _usable_draft(text: str | None, engine: dict[str, Any]) -> bool:
    if not text:
        return False
    if _looks_like_article_dump(text):
        return False
    if _looks_like_garbage(text):
        return False
    if _draft_too_short(text):
        return False
    if _wrong_code_for_query(text, str(engine.get("query") or "")):
        return False
    return not _mentions_foreign_article(text, _allowed_articles(engine))


def _draft_too_short(text: str) -> bool:
    body = re.sub(r"_Bu metin.*", "", text or "", flags=re.S).strip()
    if len(body) < 420:
        return True
    sentences = [part for part in re.split(r"(?<=[.!?…])\s+", body) if len(part.strip()) > 12]
    return len(sentences) < 4


def build_research_reasoning(
    query: str,
    evidence: list[EvidenceItem],
    *,
    route: str,
    answer: str,
    refused: bool = False,
) -> dict[str, Any]:
    used = [item for item in evidence if item.used_in_answer]
    primary = used[0] if used and not refused else None
    bm25_n = sum(1 for item in evidence if item.bm25_rank)
    sem_n = sum(1 for item in evidence if item.semantic_rank)
    lead = (answer or "").split("\n\n")[0].strip()
    hops = [
        {
            "n": 1,
            "id": "sorgu",
            "title": "Sorgu",
            "question": "Ne soruluyor?",
            "answer": query,
            "why": None,
            "state": "done",
        },
        {
            "n": 2,
            "id": "bm25",
            "title": "BM25",
            "question": "Kelime araması ne getirdi?",
            "answer": f"{bm25_n} kaynak sözcük eşleşmesiyle öne çıktı." if bm25_n else "Sözcük listesinde güçlü eşleşme yok.",
            "why": None,
            "state": "done" if bm25_n else "warn",
        },
        {
            "n": 3,
            "id": "vektor",
            "title": "Vektör",
            "question": "Anlamsal yakınlık ne dedi?",
            "answer": f"{sem_n} kaynak vektör aramasında öne çıktı." if sem_n else "Anlamsal eşleşme zayıf.",
            "why": None,
            "state": "done" if sem_n else "warn",
        },
        {
            "n": 4,
            "id": "rrf",
            "title": "Birleşim",
            "question": "Hangi resmi hüküm seçildi?",
            "answer": (
                "Arşivde bu sorguya uyan resmi hüküm yok."
                if refused
                else (
                    f"{_cite(primary)} — {primary.title or 'kaynak'}."
                    if primary
                    else "Eşleşen resmi hüküm yok."
                )
            ),
            "why": f"Rota: {'kesin madde atıfı' if route == 'exact_citation' else 'hibrit arama'}.",
            "state": "done" if primary and not refused else "warn",
        },
        {
            "n": 5,
            "id": "cevap",
            "title": "Cevap",
            "question": "Ne dendi?",
            "answer": (
                "Cevap yazılmadı; sorgu hukuk arşivine ilişkin değil."
                if refused
                else (
                    f"Gerekçe aşağıda: {_cite(primary)}."
                    if primary
                    else "Cevap metni üretilemedi."
                )
            ),
            "why": None,
            "state": "warn" if refused else ("done" if lead else "error"),
        },
    ]
    status = "solid" if primary and lead and not refused else "fragile"
    return {"status": status, "hops": hops, "conclusion": None}


def _build_extractive_answer(query: str, evidence: list[EvidenceItem]) -> str:
    used = _answer_items(query, evidence)
    if not used:
        return (
            "Bu sorgu için arşivde yeterli resmi kaynak bulunamadı. "
            "Madde numarası veya hukuki kavramla yeniden deneyin."
        )
    primary = used[0]
    n = primary.n
    paragraphs: list[str] = []
    if _is_decision(primary):
        label = _cite(primary)
        paragraphs.append(f"{label}, sorudaki olguya ilişkin emsal karardır [{n}].")
        lead = _first_sentence(primary.content or "")
        if lead:
            if not re.search(r"\[\d+\]\s*$", lead):
                lead = f"{lead.rstrip('.')} [{n}]."
            paragraphs.append(lead)
        paragraphs.append(
            f"Kararın gerekçesi, aynı nitelikteki somut olaylarda nasıl hüküm kurulduğunu gösterir [{n}]."
        )
    else:
        cite = _cite(primary)
        title = (primary.title or "").strip()
        name = title.lower() if title else "ilgili hüküm"
        lead = _first_sentence(primary.content or "")
        if _is_procedure_query(query):
            who = f"{title} " if title else ""
            paragraphs.append(f"{who}{cite} hükmünde düzenlenir [{n}].")
            if lead:
                paragraphs.append(f"Madde metninin ilgili kısmı şöyle başlar: {lead.rstrip('.')} [{n}].")
            paragraphs.append(
                f"Bu usul maddenin lafzına göre işletilir; başvurunun nereye ve nasıl yapılacağı "
                f"bu hüküm çerçevesinde okunur [{n}]."
            )
        else:
            clause = _clause_for_query(query, primary.content or "")
            if clause:
                paragraphs.append(
                    f"Evet: sorulan olgu {cite} kapsamında {name} olarak değerlendirilir [{n}]."
                )
                paragraphs.append(f"{cite} bu hâli «{clause}» diye sayar [{n}].")
                paragraphs.append(
                    f"Bu seçimlik hareket gerçekleştiğinde fiil, maddenin nitelikli hâli içinde kalır; "
                    f"kanun koyucu bu yolu {name} sayarak temel şekilden ayırır [{n}]."
                )
            elif title:
                paragraphs.append(f"{title} {cite}’de düzenlenir [{n}].")
                if lead:
                    paragraphs.append(f"Madde metninin ilgili kısmı şöyle başlar: {lead.rstrip('.')} [{n}].")
                paragraphs.append(
                    f"Sorudaki kavram bu hükmün konusuna girer; somut olay unsurları dosyadan ayrıca bakılır [{n}]."
                )
            else:
                paragraphs.append(f"Bu konu {cite} hükmünde düzenlenir [{n}].")
        for item in used[1:]:
            label = _cite(item)
            extra = f" ({item.title})" if item.title else ""
            if _is_base_offence(primary, item) and not _is_procedure_query(query):
                paragraphs.append(
                    f"Bu suçun temel şekli {label}{extra} hükmünde düzenlenir [{item.n}]."
                )
            else:
                paragraphs.append(
                    f"İlgili hüküm {label}{extra}, aynı konunun komşu düzenlemesidir [{item.n}]."
                )
        if _is_procedure_query(query):
            paragraphs.append(
                f"Somut başvurunun şekli ve yetkili merci, yalnız bu arşiv metnine göre kesinleştirilemez; "
                f"dosya olguları ayrıca değerlendirilir [{n}]."
            )
        else:
            paragraphs.append(
                f"Somut olayda maddede aranan unsurların gerçekleşip gerçekleşmediği yalnız bu arşiv metnine göre "
                f"kesinleştirilemez; dosya olguları ayrıca değerlendirilir [{n}]."
            )
    paragraphs.append("_Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır._")
    return "\n\n".join(paragraphs)


def _build_trace(query: str, fused: list[FusedHit], route: str) -> tuple[list[TraceNode], list[TraceEdge]]:
    nodes = [
        TraceNode(id="query", label="SORGU", kind="query", meta={"text": query, "route": route}),
        TraceNode(id="bm25", label="BM25", kind="retriever"),
        TraceNode(id="vector", label="VEKTÖR", kind="retriever"),
        TraceNode(id="graph", label="GRAPH", kind="retriever"),
        TraceNode(id="rrf", label="RRF", kind="fusion"),
        TraceNode(id="answer", label="CEVAP", kind="answer"),
    ]
    edges = [
        TraceEdge("query", "bm25", "lexical"),
        TraceEdge("query", "vector", "semantic"),
        TraceEdge("query", "graph", "citation"),
        TraceEdge("bm25", "rrf", "top50"),
        TraceEdge("vector", "rrf", "top50"),
        TraceEdge("graph", "rrf", "neighbors"),
        TraceEdge("rrf", "answer", "evidence"),
    ]
    for hit in fused[:8]:
        node_id = hit.chunk_id
        is_decision = (hit.hit.document_id or "").startswith("decision:")
        nodes.append(
            TraceNode(
                id=node_id,
                label=(hit.hit.title or hit.hit.document_id or "karar")
                if is_decision
                else f"{_LAW_SHORT.get(hit.hit.law_no or '', 'Kanun')} {hit.hit.article_no}",
                kind="chunk",
                meta={
                    "bm25_rank": hit.bm25_rank,
                    "semantic_rank": hit.semantic_rank,
                    "rrf_rank": hit.rank,
                    "retrievers": list(hit.sources),
                    "authority": hit.hit.authority,
                    "used_in_answer": hit.rank <= 5,
                },
            )
        )
        edges.append(TraceEdge("rrf", node_id, f"#{hit.rank}"))
        edges.append(TraceEdge(node_id, "answer", "cite" if hit.rank <= 5 else "candidate"))
    return nodes, edges


class ResearchEngine:
    def __init__(
        self,
        es_client: Any,
        embedder: Embedder | None = None,
        neo4j_driver: Any | None = None,
        *,
        evidence_limit: int = 8,
    ) -> None:
        self.embedder = embedder or create_embedder(prefer_neural=True)
        self.hybrid = HybridSearcher(es_client, self.embedder, limit=30)
        self.neo4j = neo4j_driver
        self.evidence_limit = evidence_limit

    def research(self, query: str, *, law_no: str | None = "5237") -> ResearchResult:
        hinted = parse_law_hint(query)
        search_law = hinted if hinted else law_no
        fused = self.hybrid.search(query, law_no=search_law, limit=12)
        route = "exact_citation" if any(
            h.sources == ("bm25",) for h in fused[:1]
        ) and fused and fused[0].bm25_rank == 1 and fused[0].semantic_rank is None else "hybrid"

        # Refine route detection via hybrid internals
        from retrieval.hybrid import _is_exact_citation_query

        if _is_exact_citation_query(query):
            route = "exact_citation"

        top = fused[: self.evidence_limit]
        evidence: list[EvidenceItem] = []
        for hit in top:
            neighbors: list[dict[str, Any]] = []
            if self.neo4j is not None and hit.rank <= 4:
                try:
                    doc_id = hit.hit.document_id or ""
                    if doc_id.startswith("decision:"):
                        neighbors = neighborhood_decision(self.neo4j, doc_id).get("neighbors") or []
                    elif hit.hit.law_no and hit.hit.article_no:
                        node = article_id(hit.hit.law_no, hit.hit.article_no)
                        neighbors = neighborhood(self.neo4j, node).get("neighbors") or []
                except Exception:
                    neighbors = []
            evidence.append(
                EvidenceItem(
                    n=hit.rank,
                    chunk_id=hit.chunk_id,
                    document_id=hit.hit.document_id,
                    law_no=hit.hit.law_no,
                    article_no=hit.hit.article_no,
                    title=hit.hit.title,
                    content=hit.hit.content,
                    authority=hit.hit.authority,
                    bm25_rank=hit.bm25_rank,
                    semantic_rank=hit.semantic_rank,
                    rrf_rank=hit.rank,
                    rrf_score=hit.rrf_score,
                    retrievers=list(hit.sources),
                    graph_neighbors=neighbors,
                    used_in_answer=hit.rank <= 5,
                )
            )

        # Mark used
        for item in evidence:
            item.used_in_answer = item.n <= min(5, len(evidence))

        supported = _query_supported(query, evidence)
        if not supported:
            for item in evidence:
                item.used_in_answer = False
            hinted = parse_law_hint(query)
            article = extract_article_no(query)
            refuse = (
                _missing_citation_answer(hinted, article)
                if hinted and article
                else _refuse_answer()
            )
            nodes, edges = _build_trace(query, top, route)
            return ResearchResult(
                query=query,
                answer=refuse,
                evidence=evidence,
                trace_nodes=nodes,
                trace_edges=edges,
                route=route,
                writer="refuse",
                writer_error=None,
                reasoning=build_research_reasoning(
                    query, evidence, route=route, answer=refuse, refused=True
                ),
            )

        answer_items = _answer_items(query, evidence)
        engine = {
            "query": query,
            "route": route,
            "evidence": [
                {
                    "n": item.n,
                    "document_id": item.document_id,
                    "law_no": item.law_no,
                    "article_no": item.article_no,
                    "title": item.title,
                    "content": _official_span(item, query, limit=360),
                    "authority": item.authority,
                }
                for item in answer_items
            ],
        }
        answer = _build_extractive_answer(query, evidence)
        writer = "extractive"
        drafted, drafted_writer, writer_error = _draft_research_answer(engine)
        if drafted:
            answer = drafted
            writer = drafted_writer
            writer_error = None
        nodes, edges = _build_trace(query, top, route)
        return ResearchResult(
            query=query,
            answer=answer,
            evidence=evidence,
            trace_nodes=nodes,
            trace_edges=edges,
            route=route,
            writer=writer,
            writer_error=writer_error,
            reasoning=build_research_reasoning(query, evidence, route=route, answer=answer),
        )
