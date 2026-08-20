from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable

from deadline.catalog import DEFAULT_RULES
from deadline.engine import DeadlineComputation, compute_last_day
from document_ai.agents import build_reasoning, chain_status as score_chain, diagnose_chain, elapsed_ms, now, pick_yazisma_action, step
from document_ai.answers import (
    format_havale,
    format_mevzuat_2646,
    format_mevzuat_empty,
    format_mevzuat_hits,
    format_okuyucu,
    format_sinif,
    format_sure,
    format_taslak,
)
from document_ai.classify import Classification, KAMU_TYPES, classify_document
from document_ai.extract import extract_dates, extract_fields, missing_fields
from document_ai.gaps import diagnose_islem_gaps
from document_ai.schemas import FIELD_LABELS


STAGES = (
    ("sorusturma", "Soruşturma"),
    ("kovusturma", "Kovuşturma (ilk derece)"),
    ("istinaf", "İstinaf"),
    ("temyiz", "Temyiz"),
    ("bireysel_basvuru", "Bireysel başvuru"),
)


@dataclass
class Finding:
    label: str
    value: str
    confidence: float
    evidence: str
    source: str | None = None


@dataclass
class Analysis:
    classification: Classification
    dates: dict[str, date]
    findings: list[Finding]
    deadlines: list[DeadlineComputation]
    stages: list[dict[str, Any]]
    related: list[dict[str, Any]] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    verdict: str = ""
    draft: str = ""
    official_targets: list[dict[str, str]] = field(default_factory=list)
    agents: list[dict[str, Any]] = field(default_factory=list)
    suggested_action: str = ""
    route_reason: str = ""
    chain_status: str = "solid"
    reasoning: dict[str, Any] = field(default_factory=dict)
    petition: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)


def _deadlines_for(classification: Classification, dates: dict[str, date]) -> list[DeadlineComputation]:
    out: list[DeadlineComputation] = []
    for rule in DEFAULT_RULES:
        remedy = str(rule["remedy"])
        include = remedy in classification.remedies
        if classification.document_type in {"mahkeme_karari", "tebligat"} and classification.legal_nature == "ceza":
            if remedy in {"itiraz", "istinaf", "temyiz"}:
                include = True
        if classification.legal_nature == "anayasa" and remedy == "bireysel_basvuru":
            include = True
        if not include:
            continue
        trigger = dates.get(str(rule["trigger"])) or dates.get("teblig") or dates.get("karar")
        missing = None
        last = None
        if trigger is None:
            missing = "Tebliğ veya karar tarihi metinde yok"
        else:
            last = compute_last_day(
                trigger=trigger,
                duration=int(rule["duration"]),
                unit=rule["unit"],  # type: ignore[arg-type]
                calendar=rule["calendar"],  # type: ignore[arg-type]
            )
        basis = (str(rule["legal_basis_label"]), *[str(x) for x in rule["legal_basis"]])  # type: ignore[misc]
        out.append(
            DeadlineComputation(
                rule_id=str(rule["id"]),
                name=str(rule["name"]),
                trigger=trigger,
                duration=int(rule["duration"]),
                unit=rule["unit"],  # type: ignore[arg-type]
                calendar=rule["calendar"],  # type: ignore[arg-type]
                last_day=last,
                legal_basis=basis,
                missing=missing,
            )
        )
    return out


def _stage_map(current: str) -> list[dict[str, Any]]:
    keys = [k for k, _ in STAGES]
    idx = keys.index(current) if current in keys else 1
    rows = []
    for i, (key, title) in enumerate(STAGES):
        if current not in keys:
            state = "idle"
        elif i < idx:
            state = "past"
        elif i == idx:
            state = "current"
        else:
            state = "next"
        rows.append({"id": key, "title": title, "state": state})
    return rows


def _targets(classification: Classification) -> list[dict[str, str]]:
    rows = [
        {"name": "UYAP Vatandaş", "url": "https://vatandas.uyap.gov.tr"},
        {"name": "mevzuat.gov.tr", "url": "https://www.mevzuat.gov.tr"},
    ]
    if classification.legal_nature == "ceza":
        rows.append({"name": "Yargıtay Karar Arama", "url": "https://karararama.yargitay.gov.tr"})
    if classification.legal_nature == "idare":
        rows.append({"name": "Danıştay Karar Arama", "url": "https://karararama.danistay.gov.tr"})
    if classification.legal_nature == "anayasa" or "bireysel_basvuru" in classification.remedies:
        rows.append({"name": "AYM Kararlar Bilgi Bankası", "url": "https://kararlarbilgibankasi.anayasa.gov.tr/kbb/"})
    return rows


_NATURE_TR = {
    "ceza": "ceza",
    "idare": "idare",
    "anayasa": "anayasa",
    "kamu": "kamu yazışması",
    "belirsiz": "nitelik belirsiz",
}


def build_verdict(analysis: Analysis) -> str:
    c = analysis.classification
    nature = _NATURE_TR.get(c.legal_nature, c.legal_nature)
    parts = [f"Bu belge {c.label} olarak sınıflandırıldı ({nature})."]
    kurum = analysis.fields.get("kurum")
    konu = analysis.fields.get("konu")
    if kurum:
        parts.append(f"Kurum: {kurum}.")
    if konu:
        parts.append(f"Konu: {konu}.")
    parts.append(f"Havale: {c.unit}.")
    if analysis.missing:
        parts.append("Eksik: " + ", ".join(analysis.missing) + ".")
    return " ".join(parts)


def _engine_from_analysis(analysis: Analysis, user_text: str) -> dict[str, Any]:
    return {
        "classification": asdict(analysis.classification),
        "fields": analysis.fields,
        "missing": analysis.missing,
        "dates": {key: value.isoformat() for key, value in analysis.dates.items()},
        "related": analysis.related,
        "deadlines": [
            {
                "name": item.name,
                "last_day": item.last_day.isoformat() if item.last_day else None,
                "legal_basis": list(item.legal_basis),
                "missing": item.missing,
            }
            for item in analysis.deadlines
        ],
        "user_text": user_text,
        "action": analysis.suggested_action,
        "gaps": diagnose_islem_gaps(
            analysis.suggested_action,
            user_text,
            analysis.fields,
            {key: value.isoformat() for key, value in analysis.dates.items()},
        ),
    }


def build_draft(analysis: Analysis, user_text: str = "") -> str:
    from llm.writer import compose_islem

    action = analysis.suggested_action or "ust_yazi"
    text, petition = compose_islem(action, _engine_from_analysis(analysis, user_text))
    analysis.petition = petition
    return text


Retriever = Callable[[str], list[dict[str, Any]]]

GRAPH_NODES = ("okuyucu", "sinif", "mevzuat", "sure", "taslak", "havale")
GRAPH_EDGES = tuple(zip(GRAPH_NODES, GRAPH_NODES[1:]))


def step_okuyucu(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    quoted = str(work.get("text") or "").strip()
    work["quoted"] = quoted
    work["agents"] = list(work.get("agents") or [])
    okuyucu_warn = len(quoted) < 40
    summary, answer = format_okuyucu(quoted)
    work["agents"].append(
        step(
            "okuyucu",
            "Okuyucu",
            state="warn" if okuyucu_warn else "done",
            ms=elapsed_ms(started),
            summary=summary,
            answer=answer,
            note="Metin çok kısa; sonraki adımlar buna bağlı." if okuyucu_warn else None,
        )
    )
    return work


def step_sinif(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    quoted = str(work.get("quoted") or "")
    classification = classify_document(quoted)
    dates = extract_dates(quoted)
    fields = extract_fields(quoted)
    missing = missing_fields(classification.document_type, fields)
    findings = [
        Finding("Evrak türü", classification.label, classification.confidence, classification.evidence_span),
        Finding("Hukuki nitelik", classification.legal_nature, classification.confidence, classification.evidence_span),
        Finding("Yönlendirme", classification.unit, classification.confidence, classification.evidence_span),
        Finding("Aşama", classification.stage, 0.7, classification.evidence_span),
    ]
    for key, value in fields.items():
        findings.append(Finding(FIELD_LABELS.get(key, key), value, 0.9, value, "evrak alanı"))
    for item in missing:
        findings.append(Finding("Eksik alan", item, 0.95, "tür şablonunda zorunlu, metinde yok", "şablon"))
    for key, value in dates.items():
        if key in fields:
            continue
        findings.append(Finding(f"{key} tarihi", value.isoformat(), 0.9, value.isoformat(), "evrak metni"))
    sinif_warn = classification.confidence < 0.55 or classification.document_type == "belirsiz"
    summary, answer = format_sinif(classification, fields, missing)
    work["classification"] = classification
    work["dates"] = dates
    work["fields"] = fields
    work["missing"] = missing
    work["findings"] = findings
    work["agents"].append(
        step(
            "sinif",
            "Sınıflandırıcı",
            state="warn" if sinif_warn else "done",
            ms=elapsed_ms(started),
            summary=summary,
            answer=answer,
            confidence=classification.confidence,
            note="Tür belirsiz veya düşük güven." if sinif_warn else None,
        )
    )
    return work


def mevzuat_search_query(
    quoted: str,
    classification: Classification,
    fields: dict[str, str] | None = None,
) -> str:
    """Search the index with the evrak body, not the chopped type-match span."""
    konu = " ".join(str((fields or {}).get("konu") or "").split())
    body = " ".join((quoted or "").split())
    if konu and konu.lower() not in body.lower():
        body = f"{konu} {body}".strip()
    if body:
        return body[:500]
    return (classification.evidence_span or "").strip()


def step_mevzuat(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    classification: Classification = work["classification"]
    quoted = str(work.get("quoted") or "")
    retrieve: Retriever | None = work.get("retrieve")
    findings: list[Finding] = work["findings"]
    related: list[dict[str, Any]] = []
    query = mevzuat_search_query(quoted, classification, work.get("fields") or {})
    use_retrieve = (
        retrieve
        and query.strip()
        and classification.document_type not in KAMU_TYPES
        and classification.legal_nature in {"ceza", "idare", "anayasa"}
    )
    if use_retrieve:
        try:
            related = retrieve(query)[:3]  # type: ignore[misc]
        except Exception:
            related = []
        for hit in related[:3]:
            findings.append(
                Finding(
                    "İlgili kaynak",
                    str(hit.get("title") or hit.get("article_no") or hit.get("document_id")),
                    0.8,
                    str(hit.get("content") or "")[:160],
                    source=str(hit.get("document_id") or ""),
                )
            )
        summary, answer = format_mevzuat_hits(related)
        work["agents"].append(
            step(
                "mevzuat",
                "Mevzuat",
                state="done" if related else "warn",
                ms=elapsed_ms(started),
                summary=summary,
                answer=answer,
                note=None if related else "Bilgi tabanı eksik; üretim gerçek madde yerine geçmez.",
            )
        )
    elif classification.document_type in KAMU_TYPES:
        findings.append(
            Finding(
                "İlgili kaynak",
                "Resmî Yazışma Yönetmeliği (Karar 2646) m.10–20",
                0.95,
                "Başlık, sayı, konu, muhatap, ilgi, metin, imza, ek, dağıtım, olur.",
                "2646-ek",
            )
        )
        summary, answer = format_mevzuat_2646()
        work["agents"].append(
            step(
                "mevzuat",
                "Mevzuat",
                state="done",
                ms=elapsed_ms(started),
                summary=summary,
                answer=answer,
            )
        )
    else:
        summary, answer = format_mevzuat_empty()
        work["agents"].append(
            step(
                "mevzuat",
                "Mevzuat",
                state="warn",
                ms=elapsed_ms(started),
                summary=summary,
                answer=answer,
                note="Bilgi tabanı eksik; üretim gerçek madde yerine geçmez.",
            )
        )
    work["related"] = related
    work["findings"] = findings
    return work


def step_sure(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    classification: Classification = work["classification"]
    dates: dict[str, date] = work["dates"]
    deadlines = _deadlines_for(classification, dates)
    work["deadlines"] = deadlines
    summary, answer = format_sure(deadlines)
    if not deadlines:
        work["agents"].append(
            step("sure", "Süre", state="skip", ms=elapsed_ms(started), summary=summary, answer=answer)
        )
    elif any(item.missing for item in deadlines):
        work["agents"].append(
            step(
                "sure",
                "Süre",
                state="warn",
                ms=elapsed_ms(started),
                summary=summary,
                answer=answer,
                note="Tebliğ/karar tarihi yok; süre hesabı tamamlanamadı.",
            )
        )
    else:
        work["agents"].append(
            step("sure", "Süre", state="done", ms=elapsed_ms(started), summary=summary, answer=answer)
        )
    return work


def step_taslak(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    classification: Classification = work["classification"]
    quoted = str(work.get("quoted") or "")
    action, reason = pick_yazisma_action(classification, quoted)
    analysis = Analysis(
        classification=classification,
        dates=work["dates"],
        findings=work["findings"],
        deadlines=work["deadlines"],
        stages=_stage_map(classification.stage),
        related=work.get("related") or [],
        fields=work["fields"],
        missing=work["missing"],
        official_targets=_targets(classification),
        suggested_action=action,
        route_reason=reason,
    )
    analysis.verdict = build_verdict(analysis)
    analysis.draft = build_draft(analysis, quoted)
    taslak_summary, taslak_answer = format_taslak(action or "ust_yazi", reason)
    work["analysis"] = analysis
    work["agents"].append(
        step(
            "taslak",
            "Taslak",
            state="done",
            ms=elapsed_ms(started),
            summary=taslak_summary,
            answer=taslak_answer,
        )
    )
    return work


def step_havale(work: dict[str, Any]) -> dict[str, Any]:
    analysis: Analysis = work["analysis"]
    classification: Classification = work["classification"]
    summary, answer = format_havale(classification.unit, analysis.route_reason)
    work["agents"].append(
        step("havale", "Havale", state="done", ms=0, summary=summary, answer=answer)
    )
    analysis.agents = diagnose_chain(work["agents"])
    analysis.chain_status = score_chain(analysis.agents)
    analysis.reasoning = build_reasoning(
        analysis.agents,
        verdict=analysis.verdict,
        route_reason=analysis.route_reason,
    )
    work["analysis"] = analysis
    return work


def analyze_document_core(text: str, *, retrieve: Retriever | None = None) -> Analysis:
    work: dict[str, Any] = {"text": text, "retrieve": retrieve, "agents": []}
    work = step_okuyucu(work)
    work = step_sinif(work)
    work = step_mevzuat(work)
    work = step_sure(work)
    work = step_taslak(work)
    work = step_havale(work)
    return work["analysis"]


def analyze_document(text: str, *, retrieve: Retriever | None = None) -> Analysis:
    try:
        from document_ai.langgraph_chain import run_hakim_graph

        return run_hakim_graph(text, retrieve=retrieve)
    except ImportError:
        analysis = analyze_document_core(text, retrieve=retrieve)
        analysis.observability = {
            "engine": "python",
            "graph_nodes": list(GRAPH_NODES),
            "graph_edges": [{"source": a, "target": b} for a, b in GRAPH_EDGES],
            "langfuse_enabled": False,
        }
        return analysis


def analysis_to_dict(analysis: Analysis) -> dict[str, Any]:
    return {
        "classification": asdict(analysis.classification),
        "dates": {k: v.isoformat() for k, v in analysis.dates.items()},
        "findings": [asdict(item) for item in analysis.findings],
        "deadlines": [
            {
                "rule_id": item.rule_id,
                "name": item.name,
                "trigger": item.trigger.isoformat() if item.trigger else None,
                "duration": item.duration,
                "unit": item.unit.value,
                "calendar": item.calendar.value,
                "last_day": item.last_day.isoformat() if item.last_day else None,
                "legal_basis": list(item.legal_basis),
                "missing": item.missing,
            }
            for item in analysis.deadlines
        ],
        "stages": analysis.stages,
        "related": analysis.related,
        "fields": analysis.fields,
        "missing": analysis.missing,
        "verdict": analysis.verdict,
        "draft": analysis.draft,
        "official_targets": analysis.official_targets,
        "agents": analysis.agents,
        "suggested_action": analysis.suggested_action,
        "route_reason": analysis.route_reason,
        "chain_status": analysis.chain_status,
        "reasoning": analysis.reasoning,
        "petition": analysis.petition,
        "action": analysis.suggested_action,
        "belge": analysis.suggested_action,
        "observability": analysis.observability or {
            "engine": "python",
            "graph_nodes": list(GRAPH_NODES),
            "graph_edges": [{"source": a, "target": b} for a, b in GRAPH_EDGES],
        },
    }
