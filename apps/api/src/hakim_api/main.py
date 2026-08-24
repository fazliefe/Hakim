from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from hakim_legal_schema import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "services"), str(ROOT / "packages" / "legal-schema" / "src")]


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    if os.environ.get("LANGFUSE_BASE_URL") and not os.environ.get("LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"].rstrip("/")


_load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if "pytest" not in sys.modules:
        import threading

        threading.Thread(target=_engine, name="hakim-warmup", daemon=True).start()
        try:
            from document_ai.observability import init_langfuse

            init_langfuse()
        except Exception:
            pass
    yield


DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def _cors_origins() -> list[str]:
    """Demo günü farklı bir host/IP gerekirse kod değişmeden HAKIM_CORS_ORIGINS ile açılsın."""
    raw = os.environ.get("HAKIM_CORS_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_CORS_ORIGINS
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or DEFAULT_CORS_ORIGINS


app = FastAPI(title="HAKİM API", version=SCHEMA_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,  # frontend credentials/çerez göndermiyor; wildcard/çoklu origin ile de uyumlu kalsın
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str = Field(min_length=2)
    law_no: str = "5237"


class EvidenceOut(BaseModel):
    n: int
    chunk_id: str
    document_id: str | None = None
    law_no: str | None = None
    article_no: str | None = None
    title: str | None = None
    content: str
    authority: str | None = None
    bm25_rank: int | None = None
    semantic_rank: int | None = None
    rrf_rank: int
    rrf_score: float
    retrievers: list[str]
    graph_neighbors: list[dict[str, Any]] = []
    used_in_answer: bool = False


class TraceNodeOut(BaseModel):
    id: str
    label: str
    kind: str
    meta: dict[str, Any] = {}


class TraceEdgeOut(BaseModel):
    source: str
    target: str
    label: str


class ResearchResponse(BaseModel):
    query: str
    answer: str
    route: str
    evidence: list[EvidenceOut]
    trace_nodes: list[TraceNodeOut]
    trace_edges: list[TraceEdgeOut]
    writer: str = "extractive"
    writer_error: str | None = None
    reasoning: dict[str, Any] | None = None


class DocumentRequest(BaseModel):
    text: str = Field(min_length=8)
    action: str | None = None


@lru_cache(maxsize=1)
def _engine():
    from graph.neo4j_client import create_neo4j_driver
    from retrieval.embeddings import create_embedder
    from retrieval.es_client import create_es_client
    from retrieval.research import ResearchEngine

    es = create_es_client(os.environ.get("HAKIM_ELASTICSEARCH_URL", "http://127.0.0.1:9200"))
    embedder = create_embedder(prefer_neural=True)
    try:
        neo4j = create_neo4j_driver()
        neo4j.verify_connectivity()
    except Exception:
        neo4j = None
    return ResearchEngine(es, embedder=embedder, neo4j_driver=neo4j)


def _retrieve_related(query: str) -> list[dict[str, Any]]:
    try:
        fused = _engine().hybrid.search(query, law_no=None, limit=4)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for hit in fused:
        rows.append(
            {
                "n": hit.rank,
                "chunk_id": hit.chunk_id,
                "document_id": hit.hit.document_id,
                "law_no": hit.hit.law_no,
                "article_no": hit.hit.article_no,
                "title": hit.hit.title,
                "content": (hit.hit.content or "")[:220],
                "authority": hit.hit.authority,
            }
        )
    return rows


def _analyze(text: str, *, surface: str = "evrak", action: str | None = None) -> dict[str, Any]:
    from document_ai.agents import elapsed_ms, mark_writer, now
    from document_ai.pipeline import analysis_to_dict, analyze_document
    from llm.writer import ACTION_TO_BELGE, compose_islem, write_module, writer_name

    retrieve = _retrieve_related if _check_elasticsearch() == "ok" else None
    payload = analysis_to_dict(analyze_document(text, retrieve=retrieve))
    payload["writer"] = "extractive"
    action_id = (action or payload.get("suggested_action") or "").strip().lower()
    if surface == "islem":
        payload["belge"] = ACTION_TO_BELGE.get(action_id)
        payload["action"] = action_id
    if surface != "surec":
        from document_ai.gaps import diagnose_islem_gaps

        payload["gaps"] = diagnose_islem_gaps(
            action_id,
            text,
            payload.get("fields") or {},
            payload.get("dates") or {},
        )
    started = now()
    try:
        draft = None
        if surface == "surec":
            draft = write_module(surface, {**payload, "user_text": text[:900]})
        else:
            draft, petition = compose_islem(
                action_id, {**payload, "action": action_id, "user_text": text[:900]}
            )
            payload["petition"] = petition
            payload["action"] = action_id
            payload["belge"] = ACTION_TO_BELGE.get(action_id) or action_id
        if draft:
            payload["draft"] = draft
            payload["writer"] = writer_name()
            mark_writer(payload.get("agents") or [], writer=payload["writer"], ms=elapsed_ms(started))
    except Exception as exc:
        payload["writer"] = "extractive"
        payload["writer_error"] = str(exc)[:280]
        mark_writer(payload.get("agents") or [], writer="extractive", ms=elapsed_ms(started), error=str(exc))
    return payload


def _check_elasticsearch() -> str:
    try:
        from elasticsearch import Elasticsearch
        from retrieval.es_client import DEFAULT_ES_URL

        es = Elasticsearch(DEFAULT_ES_URL, request_timeout=1.5)
        return "ok" if es.ping() else "kapalı"
    except Exception:
        return "kapalı"


def _check_neo4j() -> str:
    try:
        from graph.neo4j_client import create_neo4j_driver

        driver = create_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        return "ok"
    except Exception:
        return "kapalı"


def _check_postgres() -> str:
    try:
        import psycopg

        url = os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim")
        with psycopg.connect(url, connect_timeout=1) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except Exception:
        return "kapalı"


_OLLAMA_CHECK: dict[str, Any] = {"at": 0.0, "value": "kapalı"}


def _check_yazim() -> str:
    try:
        from llm.api_client import api_configured

        if api_configured():
            return "ok"
    except Exception:
        pass
    return _check_ollama()


def _check_ollama() -> str:
    now = time.monotonic()
    if now - float(_OLLAMA_CHECK["at"]) < 12:
        return str(_OLLAMA_CHECK["value"])
    try:
        from llm.client import ping

        value = "ok" if ping() else "kapalı"
    except Exception:
        value = "kapalı"
    _OLLAMA_CHECK["at"] = now
    _OLLAMA_CHECK["value"] = value
    return value


def _check_langfuse() -> str:
    try:
        from document_ai.observability import langfuse_configured

        return "ok" if langfuse_configured() else "kapalı"
    except Exception:
        return "kapalı"


def _check_langgraph() -> str:
    try:
        import langgraph  # noqa: F401

        return "ok"
    except Exception:
        return "kapalı"


@app.get("/health")
def health() -> dict[str, Any]:
    checks = {
        "api": "ok",
        "elasticsearch": _check_elasticsearch(),
        "neo4j": _check_neo4j(),
        "postgres": _check_postgres(),
        "yazim": _check_yazim(),
        "ollama": _check_ollama(),
        "langfuse": _check_langfuse(),
        "langgraph": _check_langgraph(),
    }
    required = ("api", "elasticsearch", "neo4j", "postgres")
    return {
        "status": "ok",
        "service": "hakim-api",
        "ready": all(checks[key] == "ok" for key in required),
        "checks": checks,
    }


@app.get("/v1/durum")
def durum() -> dict[str, Any]:
    payload = health()
    payload["etiketler"] = {
        "api": "API",
        "elasticsearch": "Arama",
        "neo4j": "Bilgi grafı",
        "postgres": "Arşiv",
        "yazim": "Yazım",
        "ollama": "Ollama",
        "langfuse": "Langfuse",
        "langgraph": "LangGraph",
    }
    return payload


def _catalog_path() -> Path:
    return ROOT / "data" / "catalogs" / "open_legal_sources.json"


def _source_counts() -> dict[str, int]:
    try:
        import psycopg

        url = os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim")
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("SET search_path TO hakim, public")
            rows = conn.execute(
                """
                SELECT source_id, count(*)::int
                FROM (
                    SELECT source_id FROM court_decisions
                    UNION ALL
                    SELECT source_id FROM legal_documents
                ) t
                GROUP BY source_id
                """
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}
    except Exception:
        return {}


@app.get("/v1/kaynaklar")
def kaynaklar() -> dict[str, Any]:
    import json

    path = _catalog_path()
    catalog = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    counts = _source_counts()
    official = []
    for item in catalog.get("official") or []:
        row = dict(item)
        row["documents"] = counts.get(str(item.get("id") or ""), 0)
        official.append(row)
    huggingface = []
    for item in catalog.get("huggingface") or []:
        row = dict(item)
        row["documents"] = counts.get(str(item.get("id") or ""), 0)
        huggingface.append(row)
    return {
        "official": official,
        "mcp": catalog.get("mcp") or [],
        "huggingface": huggingface,
        "counts": counts,
    }


@app.get("/v1/schema")
def schema() -> dict[str, str]:
    return {"legal_data_model": SCHEMA_VERSION, "name": "HAKİM Legal Data Model"}


@app.get("/v1/graf")
def graf() -> dict[str, Any]:
    try:
        from graph.projector import dump_graph

        driver = _engine().neo4j
        if driver is None:
            return {"nodes": [], "edges": [], "counts": {}, "detail": "Neo4j kapalı"}
        return dump_graph(driver)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Graf okunamadı: {exc}") from exc


@app.get("/v1/kamu/sablon")
def kamu_sablon() -> dict[str, Any]:
    from llm.formats import belgeler_index, load_belge
    from llm.render import render_belge
    from llm.resmi_yazisma import load_sablon

    raw = load_sablon()
    bloklar = {}
    for key, block in (raw.get("bloklar") or {}).items():
        bloklar[key] = {
            "sira": block.get("sira"),
            "ornek": block.get("ornek"),
            "kurallar": block.get("kurallar"),
        }
    varyantlar = {}
    for key, variant in (raw.get("varyantlar") or {}).items():
        varyantlar[key] = {
            "belge_id": variant.get("belge_id"),
            "ornek": variant.get("ornek"),
            "blok_sirasi": variant.get("blok_sirasi") or [],
            "kapanis": variant.get("kapanis"),
        }
    ornekler: dict[str, str] = {}
    for item in belgeler_index().get("documents") or []:
        spec = load_belge(str(item["id"]))
        if spec.get("family") != "kamu":
            continue
        ornekler[str(spec["id"])] = render_belge(spec, spec.get("example") or {})
    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "source": raw.get("source"),
        "ornek_pdf": raw.get("ornek_pdf"),
        "kaynaklar": raw.get("kaynaklar") or [],
        "bloklar": bloklar,
        "varyantlar": varyantlar,
        "ornekler": ornekler,
    }


@app.get("/v1/belgeler")
def belgeler() -> dict[str, Any]:
    from llm.formats import belgeler_index, load_belge

    documents = []
    for item in belgeler_index().get("documents") or []:
        spec = load_belge(str(item["id"]))
        documents.append(
            {
                "id": spec["id"],
                "title": spec.get("title") or item.get("title"),
                "when": spec.get("when") or item.get("when"),
                "makam": spec.get("makam") or item.get("makam"),
                "family": spec.get("family"),
                "legal_basis": spec.get("legal_basis") or [],
                "sections": [row.get("label") for row in spec.get("sections") or []],
            }
        )
    return {"documents": documents}


@app.post("/v1/arastirma", response_model=ResearchResponse)
def arastirma(body: ResearchRequest) -> ResearchResponse:
    try:
        result = _engine().research(body.query.strip(), law_no=body.law_no)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail=f"Araştırma motoru hazır değil: {exc}") from exc

    return ResearchResponse(
        query=result.query,
        answer=result.answer,
        route=result.route,
        evidence=[EvidenceOut(**item.__dict__) for item in result.evidence],
        trace_nodes=[TraceNodeOut(**n.__dict__) for n in result.trace_nodes],
        trace_edges=[TraceEdgeOut(**e.__dict__) for e in result.trace_edges],
        writer=result.writer,
        writer_error=result.writer_error,
        reasoning=result.reasoning or None,
    )


@app.post("/v1/evrak")
def evrak(body: DocumentRequest) -> dict[str, Any]:
    return _analyze(body.text, surface="evrak")


@app.post("/v1/evrak/dosya")
async def evrak_dosya(file: UploadFile = File(...)) -> dict[str, Any]:
    from document_ai.ingest import UploadError, extract_upload

    data = await file.read()
    try:
        extracted = extract_upload(file.filename or "evrak", data)
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = _analyze(extracted.text, surface="evrak")
    payload["source_filename"] = extracted.filename
    payload["source_kind"] = extracted.kind
    payload["extract_note"] = extracted.note
    payload["text"] = extracted.text
    return payload


@app.post("/v1/surec")
def surec(body: DocumentRequest) -> dict[str, Any]:
    return _analyze(body.text, surface="surec")


@app.post("/v1/islem")
def islem(body: DocumentRequest) -> dict[str, Any]:
    from document_ai.route_islem import ACTION_TITLES, route_islem
    from llm.writer import ACTION_TO_BELGE

    explicit = (body.action or "").strip().lower()
    routed = None
    if explicit in ACTION_TO_BELGE:
        action = explicit
        reason = f"Kalıp kullanıcı tarafından seçildi: {ACTION_TITLES.get(action, action)}."
    else:
        routed = route_islem(body.text)
        action = routed.action
        reason = routed.reason
    payload = _analyze(body.text, surface="islem", action=action)
    payload["action"] = action
    payload["belge"] = ACTION_TO_BELGE.get(action, action)
    payload["route_reason"] = reason
    if routed:
        payload["route_evidence"] = routed.evidence
        payload["route_confidence"] = routed.confidence
    payload["export_blocked"] = not payload.get("draft")
    payload["uyap_note"] = (
        "UYAP entegrasyonu yok. Taslağı indirip vatandas.uyap.gov.tr üzerinden yetkili kullanıcı gönderir."
    )
    return payload


@app.post("/v1/senaryo")
def senaryo(body: DocumentRequest) -> dict[str, Any]:
    """Görev 1+2 tek paket: oku → sınıf → mevzuat → süre → resmi yazı → havale."""
    from document_ai.agents import build_reasoning, elapsed_ms, mark_writer, now
    from document_ai.answers import format_havale
    from document_ai.pipeline import analysis_to_dict, analyze_document
    from llm.writer import ACTION_TO_BELGE, compose_islem, writer_name

    retrieve = _retrieve_related if _check_elasticsearch() == "ok" else None
    analysis = analyze_document(body.text, retrieve=retrieve)
    explicit = (body.action or "").strip().lower()
    if explicit in ACTION_TO_BELGE:
        action = explicit
        reason = f"Kalıp kullanıcı tarafından seçildi: {action}."
    else:
        action = analysis.suggested_action
        reason = analysis.route_reason
    payload = analysis_to_dict(analysis)
    payload["action"] = action
    payload["belge"] = ACTION_TO_BELGE.get(action, action)
    payload["route_reason"] = reason
    payload["senaryo"] = True
    _, havale_note = format_havale(analysis.classification.unit, reason)
    payload["havale"] = {
        "unit": analysis.classification.unit,
        "note": havale_note,
    }
    payload["writer"] = "extractive"
    started = now()
    try:
        from document_ai.gaps import diagnose_islem_gaps

        payload["gaps"] = diagnose_islem_gaps(action, body.text, payload.get("fields") or {}, payload.get("dates") or {})
        draft, petition = compose_islem(action, {**payload, "action": action, "user_text": body.text[:900]})
        if draft:
            payload["draft"] = draft
            payload["petition"] = petition
            payload["writer"] = writer_name()
            mark_writer(payload.get("agents") or [], writer=payload["writer"], ms=elapsed_ms(started))
    except Exception as exc:
        payload["writer_error"] = str(exc)[:280]
        mark_writer(payload.get("agents") or [], writer="extractive", ms=elapsed_ms(started), error=str(exc))
    payload["reasoning"] = build_reasoning(
        payload.get("agents") or [],
        verdict=str(payload.get("verdict") or ""),
        route_reason=reason,
    )
    payload["chain_status"] = payload["reasoning"]["status"]
    payload["uyap_note"] = (
        "UYAP entegrasyonu yok. Taslağı indirip vatandas.uyap.gov.tr üzerinden yetkili kullanıcı gönderir."
    )
    return payload
