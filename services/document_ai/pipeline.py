from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from deadline.catalog import DEFAULT_RULES
from deadline.engine import DeadlineComputation, compute_last_day_detail
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


STAGES_CEZA = (
    ("sorusturma", "Soruşturma"),
    ("kovusturma", "Kovuşturma (ilk derece)"),
    ("istinaf", "İstinaf"),
    ("temyiz", "Temyiz"),
    ("bireysel_basvuru", "Bireysel başvuru"),
)
# "Kovuşturma"/"soruşturma" ceza muhakemesine özgü — hukuk/idare/anayasa
# davalarında bu aşamalar yok, o yüzden ayrı ve daha kısa bir raylı gösterim:
# ilk derece → istinaf → temyiz (+ anayasa'da bireysel başvuru).
STAGES_DIGER = (
    ("ilk_derece", "İlk derece"),
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
    trace_nodes: list[dict[str, Any]] = field(default_factory=list)
    trace_edges: list[dict[str, Any]] = field(default_factory=list)
    legal_caveat: str | None = None


def _deadlines_for(classification: Classification, dates: dict[str, date]) -> list[DeadlineComputation]:
    out: list[DeadlineComputation] = []
    for rule in DEFAULT_RULES:
        remedy = str(rule["remedy"])
        include = remedy in classification.remedies
        if classification.document_type in {"mahkeme_karari", "tebligat"} and classification.legal_nature == "ceza":
            if remedy in {"itiraz", "istinaf_ceza", "temyiz_ceza"}:
                include = True
        if classification.document_type in {"mahkeme_karari", "tebligat"} and classification.legal_nature == "hukuk":
            if remedy in {"istinaf_hukuk", "temyiz_hukuk"}:
                include = True
        if classification.legal_nature == "anayasa" and remedy == "bireysel_basvuru":
            include = True
        if not include:
            continue
        trigger = dates.get(str(rule["trigger"])) or dates.get("teblig") or dates.get("karar")
        missing = None
        last = None
        note = None
        if trigger is None:
            missing = "Tebliğ veya karar tarihi metinde yok"
        else:
            last, note = compute_last_day_detail(
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
                adjustment_note=note,
            )
        )
    return out


def _stage_map(current: str, legal_nature: str) -> list[dict[str, Any]]:
    stages = STAGES_CEZA if legal_nature == "ceza" else STAGES_DIGER
    keys = [k for k, _ in stages]
    idx = keys.index(current) if current in keys else 0
    rows = []
    for i, (key, title) in enumerate(stages):
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
    if classification.legal_nature in {"ceza", "hukuk"}:
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
    "hukuk": "hukuk",
    "kamu": "kamu yazışması",
    "belirsiz": "nitelik belirsiz",
}


def _legal_interpretation_caveat(classification: Classification) -> str | None:
    """Ceren Özkurt'un bulgusu: sistem, arşivdeki GÜNCEL kanun metnini
    doğrudan uyguluyor. Ama gerçek hukuki sonuç lehe kanun uygulaması (TCK
    m.7) TEK başına değil — içtihadı birleştirme kararları, zamanaşımı,
    hâkimin takdir yetkisi gibi başka ilkelerle de bu metinden farklılaşabilir
    (özellikle ceza hukukunda). Arşivde tarihsel versiyon olmadığı için
    (yalnızca güncel metin var, bkz. mapping.py'deki mülga notu) bu ilkeler
    hesaba katılamıyor — kesin bir hukuki tespit sunmuyoruz, sessizce göz ardı
    de etmiyoruz: açıkça uyarıyoruz."""
    if classification.document_type not in {"mahkeme_karari", "tebligat", "iddianame", "dilekce"}:
        return None
    if classification.legal_nature == "ceza":
        return (
            "Bu analiz arşivdeki güncel kanun metnine dayanır. Lehe kanun uygulaması "
            "(TCK m.7), içtihadı birleştirme kararları, zamanaşımı, hâkimin takdir "
            "yetkisi gibi ilkeler nedeniyle somut olaydaki gerçek hukuki sonuç bu "
            "metinden farklılaşabilir — bu ilkeler burada ayrıca değerlendirilmemiştir. "
            "Kesin dayanak olarak kullanmadan önce bir hukuk uzmanına danışın."
        )
    if classification.legal_nature in {"hukuk", "idare"}:
        return (
            "Bu analiz arşivdeki güncel kanun metnine dayanır. İçtihat, zamanaşımı/hak "
            "düşürücü süre istisnaları gibi ilkeler nedeniyle somut olaydaki gerçek "
            "hukuki sonuç bu metinden farklılaşabilir. Kesin dayanak olarak kullanmadan "
            "önce bir hukuk uzmanına danışın."
        )
    return None


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


Retriever = Callable[[str, "datetime | None"], list[dict[str, Any]]]

GRAPH_NODES = ("okuyucu", "sinif", "mevzuat", "sure", "taslak", "havale")
GRAPH_EDGES = (
    ("okuyucu", "sinif"),
    ("sinif", "mevzuat"),
    ("mevzuat", "mevzuat"),  # ilk sorgu boş dönerse geniş sorguyla bir kez tekrar dener
    ("mevzuat", "sure"),
    ("sure", "taslak"),
    ("taslak", "havale"),
)
MEVZUAT_RETRY_ELIGIBLE = frozenset({"ceza", "idare", "anayasa"})

_TRACE_KIND = {
    "okuyucu": "query",
    "sinif": "retriever",
    "mevzuat": "retriever",
    "sure": "fusion",
    "taslak": "answer",
    "havale": "route",
}
_TRACE_EDGE_LABELS = {("mevzuat", "mevzuat"): "retry"}


def _chunk_label(item: dict[str, Any]) -> str:
    from llm.prompt import LAW_SHORT

    document_id = str(item.get("document_id") or "")
    if document_id.startswith("decision:"):
        return str(item.get("title") or document_id or "Karar")
    law_no = str(item.get("law_no") or "")
    article_no = item.get("article_no")
    short = LAW_SHORT.get(law_no, f"K.{law_no}" if law_no else "Kanun")
    if article_no:
        return f"{short} {article_no}"
    return str(item.get("title") or item.get("chunk_id") or "Kaynak")


def build_document_trace(
    agents: list[dict[str, Any]],
    related: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Ajan zincirini (okuyucu→…→havale) + kullanılan mevzuat maddelerini tek
    bir izlenebilirlik grafına çevirir: hangi karar/yönlendirme hangi madde/
    karara dayanıyor, TraceGraphView'daki gibi node/edge listesi olarak."""
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in agents:
        node_id = str(item.get("id") or "")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": str(item.get("title") or node_id).upper(),
                "kind": _TRACE_KIND.get(node_id, "retriever"),
                "meta": {
                    "state": item.get("state"),
                    "ms": item.get("ms"),
                    "summary": item.get("summary"),
                    "note": item.get("note"),
                },
            }
        )
    mevzuat_note = next((str(item.get("note") or "") for item in agents if item.get("id") == "mevzuat"), "")
    mevzuat_retried = "geniş sorgu" in mevzuat_note.lower()
    edges: list[dict[str, Any]] = [
        {"source": a, "target": b, "label": _TRACE_EDGE_LABELS.get((a, b), "")}
        for a, b in GRAPH_EDGES
        if (a, b) != ("mevzuat", "mevzuat") or mevzuat_retried
    ]
    if "mevzuat" in seen:
        for item in related:
            chunk_id = str(item.get("chunk_id") or "")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            rank = item.get("n") or item.get("rrf_rank") or len(nodes)
            nodes.append(
                {
                    "id": chunk_id,
                    "label": _chunk_label(item),
                    "kind": "chunk",
                    "meta": {
                        "law_no": item.get("law_no"),
                        "article_no": item.get("article_no"),
                        "title": item.get("title"),
                        "rrf_rank": item.get("rrf_rank"),
                        "retrievers": item.get("retrievers") or [],
                        "graph_neighbors": item.get("graph_neighbors") or [],
                        "used_in_answer": bool(item.get("used_in_answer", True)),
                        "mulga_warning": item.get("mulga_warning"),
                    },
                }
            )
            edges.append({"source": "mevzuat", "target": chunk_id, "label": f"#{rank}"})
            if "taslak" in seen:
                edges.append({"source": chunk_id, "target": "taslak", "label": "cite"})
    return nodes, edges


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


def _broadened_mevzuat_query(quoted: str, classification: Classification) -> str:
    """İlk (konu + 500 kr) sorgu boş dönerse dener: kırpma sınırını kaldırıp
    evrak gövdesinden daha geniş bir bağlam kullan."""
    body = " ".join((quoted or "").split())
    if body:
        return body[:1500]
    return (classification.evidence_span or "").strip()


def _mevzuat_at(dates: dict[str, date]) -> datetime | None:
    """Madde 2 (zamansal geçerlilik): mevzuat araması, evrakın kendi tarihine
    göre yürürlükte olan metni getirmeli — bugünün tarihine göre değil.
    Tebliğ tarihi yoksa karar tarihi kullanılır (süre motorunun tetikleyici
    önceliğiyle aynı sıra, bkz. `_deadlines_for`)."""
    picked = dates.get("teblig") or dates.get("karar")
    if picked is None:
        return None
    return datetime(picked.year, picked.month, picked.day)


def step_mevzuat(work: dict[str, Any]) -> dict[str, Any]:
    started = now()
    classification: Classification = work["classification"]
    quoted = str(work.get("quoted") or "")
    retrieve: Retriever | None = work.get("retrieve")
    findings: list[Finding] = work["findings"]
    related: list[dict[str, Any]] = []
    attempt = int(work.get("mevzuat_attempt") or 0)
    is_retry = attempt >= 1
    query = (
        _broadened_mevzuat_query(quoted, classification)
        if is_retry
        else mevzuat_search_query(quoted, classification, work.get("fields") or {})
    )
    use_retrieve = (
        retrieve
        and query.strip()
        and classification.document_type not in KAMU_TYPES
        and classification.legal_nature in MEVZUAT_RETRY_ELIGIBLE
    )
    work["mevzuat_retry"] = False
    if use_retrieve:
        at = _mevzuat_at(work.get("dates") or {})
        try:
            related = retrieve(query, at)[:3]  # type: ignore[misc]
        except Exception:
            related = []
        if not related and not is_retry:
            # Bilgi tabanı ilk (dar) sorguda boş döndü; graf bu node'a bir kez
            # daha (geniş sorguyla) döner — bu turda agents'a henüz yazma.
            work["related"] = related
            work["mevzuat_attempt"] = 1
            work["mevzuat_retry"] = True
            return work
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
        if is_retry:
            note = (
                "İlk sorguda bulunamadı; geniş sorguyla tekrar denendi ve kaynak bulundu."
                if related
                else "İlk ve geniş sorguda da eşleşen mevzuat bulunamadı; üretim gerçek madde yerine geçmez."
            )
        else:
            note = None if related else "Bilgi tabanı eksik; üretim gerçek madde yerine geçmez."
        work["agents"].append(
            step(
                "mevzuat",
                "Mevzuat",
                state="done" if related else "warn",
                ms=elapsed_ms(started),
                summary=summary,
                answer=answer,
                note=note,
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
    if retrieve and classification.legal_nature in MEVZUAT_RETRY_ELIGIBLE:
        from llm.emsal import attach_emsal_hits

        emsal_action = "idari_dava" if classification.legal_nature == "idare" else ""
        related = attach_emsal_hits(
            related,
            retrieve,
            quoted,
            at=_mevzuat_at(work.get("dates") or {}),
            action=emsal_action,
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


def _apply_citation_usage(analysis: Analysis) -> None:
    """`related`'teki `used_in_answer`'ı gerçek taslağa göre düzeltir. Sanitizer
    (writer.py:_finalize_belge_facts) kaynaksız/alakasız bir maddeyi
    `hukuki_nitelendirme`'den düşürüp yerine `n` taşımayan bir yer tutucu
    koyabilir — o durumda o kaynak yalnızca aday havuzunda kalmıştır, taslakta
    gerçekten kullanılmamıştır ve Kaynak grafiğinde öyle görünmemelidir."""
    petition = analysis.petition
    if not isinstance(petition, dict) or "cited_ns" not in petition:
        return
    cited = set(petition.get("cited_ns") or [])
    for item in analysis.related:
        if isinstance(item, dict) and "n" in item:
            item["used_in_answer"] = item["n"] in cited


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
        stages=_stage_map(classification.stage, classification.legal_nature),
        related=work.get("related") or [],
        fields=work["fields"],
        missing=work["missing"],
        official_targets=_targets(classification),
        suggested_action=action,
        route_reason=reason,
    )
    analysis.verdict = build_verdict(analysis)
    analysis.draft = build_draft(analysis, quoted)
    analysis.legal_caveat = _legal_interpretation_caveat(classification)
    _apply_citation_usage(analysis)
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
    analysis.trace_nodes, analysis.trace_edges = build_document_trace(analysis.agents, analysis.related)
    work["analysis"] = analysis
    return work


def analyze_document_core(text: str, *, retrieve: Retriever | None = None) -> Analysis:
    work: dict[str, Any] = {"text": text, "retrieve": retrieve, "agents": []}
    work = step_okuyucu(work)
    work = step_sinif(work)
    work = step_mevzuat(work)
    if work.get("mevzuat_retry"):
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
                "adjustment_note": item.adjustment_note,
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
        "trace_nodes": analysis.trace_nodes,
        "trace_edges": analysis.trace_edges,
        "legal_caveat": analysis.legal_caveat,
        "action": analysis.suggested_action,
        "belge": analysis.suggested_action,
        "observability": analysis.observability or {
            "engine": "python",
            "graph_nodes": list(GRAPH_NODES),
            "graph_edges": [{"source": a, "target": b} for a, b in GRAPH_EDGES],
        },
    }
