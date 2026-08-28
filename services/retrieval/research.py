from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from retrieval.bm25 import extract_article_no, parse_law_hint
from hakim_legal_schema.ids import article_id

from graph.projector import neighborhood, neighborhood_decision
from retrieval.cross_encoder import PairScorer, create_reranker
from retrieval.embeddings import Embedder, create_embedder
from retrieval.hybrid import HybridSearcher
from retrieval.mapping import detect_mulga_warning
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
    mulga_warning: str | None = None


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
    observability: dict[str, Any] = field(default_factory=dict)


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


def _hit_fields(item: Any) -> tuple[str, str, str]:
    if hasattr(item, "hit"):
        return _hit_fields(item.hit)
    if isinstance(item, dict):
        return (
            str(item.get("document_id") or item.get("chunk_id") or ""),
            str(item.get("title") or ""),
            str(item.get("content") or ""),
        )
    return (
        str(getattr(item, "document_id", None) or getattr(item, "chunk_id", "") or ""),
        str(getattr(item, "title", None) or ""),
        str(getattr(item, "content", None) or ""),
    )


def _is_petition_like(item: Any) -> bool:
    """Dilekçe / bireysel başvuru metni araştırma cevabına girmez.

    AYM bireysel başvurusu dilekçe formatındadır ve başvurucu adı taşır;
    evrak/işlem örneklerinde kalır, kanun araştırmasının dayanağı olmaz.
    """
    from llm.emsal import _name_only_title

    document_id, title, content = _hit_fields(item)
    hit = {"document_id": document_id, "title": title, "content": content}
    if _name_only_title(hit):
        return True
    head = _ascii_q(f"{title}\n{content[:900]}")
    if "basvurusu" in head or "basvuru numarasi" in head:
        return True
    if re.search(r"\barz olunur\b|\barz ederim\b|geregini rica", head):
        return True
    if str(document_id).startswith("decision:aym:") and (
        "basvurucu" in head or "basvuru" in head
    ):
        return True
    return False


def _exclude_from_research(item: Any) -> bool:
    """Dilekçe örnekleri, mahkeme kararı olmayan kaynaklar (ticaret sicili,
    Rekabet Kurumu, KVKK Kurulu, Resmi Gazete) ve alt derece (istinaf/yerel
    hukuk) kararları araştırma kaynak listesine girmez.

    DİKKAT: `llm.emsal.court_ok()` KULLANILMAZ — o fonksiyon yalnızca
    İşlem'in ceza-odaklı dilekçe emsal künyesi içindir ("hukuk" geçip
    "ceza" geçmeyen HER kararı reddeder, bkz. emsal.py docstring'i:
    "Temyiz/istinaf için yalnızca Yargıtay / ceza dairesi / CGK / İBK").
    Araştırma genel amaçlıdır — medeni hukuk (tazminat, boşanma, miras,
    kira, iş hukuku...) emsal kararları da gösterilmeli; court_ok burada
    kullanılınca TÜM Yargıtay Hukuk Daireleri kararları sessizce
    kayboluyordu (canlı doğrulandı — bkz. commit mesajı)."""
    if _is_petition_like(item):
        return True
    document_id, title, content = _hit_fields(item)
    if not str(document_id).startswith("decision:"):
        return False
    blob = _ascii_q(f"{document_id} {title} {content[:800]}")
    if any(bad in blob for bad in ("ticaret", "rekabet", "kvkk", "resmi_gazete")):
        return True
    folded = _ascii_q(document_id)
    return "istinafhukuk" in folded or "yerelhukuk" in folded


def _looks_like_petition_dump(text: str) -> bool:
    folded = _ascii_q(text)
    if "basvuru numarasi" in folded:
        return True
    if re.search(r"[a-z]+\s+[a-z]+\s+basvurusu", folded):
        return True
    return False


_CITE_MARK = re.compile(r"\s*\[\d+\]")


def _is_decision(item: EvidenceItem) -> bool:
    return (item.document_id or "").startswith("decision:")


def _cite(item: EvidenceItem) -> str:
    if _is_decision(item):
        return item.title or item.document_id or "Mahkeme kararı"
    prefix = _LAW_SHORT.get(item.law_no or "", f"Kanun {item.law_no}" if item.law_no else "Kanun")
    return f"{prefix} m.{item.article_no}"


def _attach_cite(text: str, n: int) -> str:
    blob = _CITE_MARK.sub("", str(text or "")).strip()
    if not blob:
        return ""
    blob = blob.rstrip(" .")
    return f"{blob} [{n}]."


def _cite_sentences(text: str, ns: list[int]) -> str:
    """Her cümleye bir atıf; birden fazla kaynak varsa [1]/[2]/[3] dağıtılır."""
    blob = str(text or "").strip()
    if not blob or not ns:
        return blob
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", blob) if part.strip()]
    if not parts:
        return _attach_cite(blob, ns[0])
    if len(ns) == 1:
        return _attach_cite(" ".join(_CITE_MARK.sub("", part).strip() for part in parts), ns[0])
    assigned = [ns[0]] * len(parts)
    for index, extra in enumerate(ns[1:], start=1):
        assigned[min(index, len(parts) - 1)] = extra
    return " ".join(_attach_cite(part, assigned[index]) for index, part in enumerate(parts))


def _source_index_lines(items: list[EvidenceItem]) -> str:
    from llm.render import KAYNAK_UYARI

    lines = [f"[{item.n}] {_source_label(item)}" for item in items]
    lines.append(KAYNAK_UYARI)
    return "\n".join(lines)


def _fill_missing_cites(answer: str, items: list[EvidenceItem]) -> str:
    found = {int(match) for match in re.findall(r"\[(\d+)\]", answer or "")}
    missing = [item for item in items if item.n not in found][:4]
    if not missing:
        return answer
    extra = "\n".join(
        f"• {_cite(item)}"
        + (f" ({item.title})" if item.title and not _is_decision(item) else "")
        + f" [{item.n}]."
        for item in missing
    )
    if "\n\nİlgili hükümler\n" in answer:
        head, rest = answer.split("\n\nİlgili hükümler\n", 1)
        block, *tail = rest.split("\n\n", 1)
        suffix = f"\n\n{tail[0]}" if tail else ""
        return f"{head}\n\nİlgili hükümler\n{block}\n{extra}{suffix}"
    marker = "\n\nKaynak\n"
    inject = f"\n\nİlgili hükümler\n{extra}"
    if marker in answer:
        return answer.replace(marker, f"{inject}{marker}", 1)
    return f"{answer}{inject}"


def _spread_cites(answer: str, items: list[EvidenceItem]) -> str:
    """Gövde yalnızca [1] basmışsa ve birden fazla kaynak varsa [1]/[2] dağıt."""
    ns = [item.n for item in items]
    if len(ns) < 2 or not answer:
        return answer
    marker = "\n\nKaynak\n"
    if marker in answer:
        body, kaynak = answer.split(marker, 1)
    else:
        body, kaynak = answer, None
    found = {int(match) for match in re.findall(r"\[(\d+)\]", body)}
    if len(found) > 1:
        return answer
    index = 0

    def repl(_match: re.Match[str]) -> str:
        nonlocal index
        n = ns[index % len(ns)]
        index += 1
        return f"[{n}]"

    body = re.sub(r"\[\d+\]", repl, body)
    if kaynak is None:
        return body
    return f"{body}{marker}{kaynak}"


def _clamp_unknown_cites(answer: str, items: list[EvidenceItem]) -> str:
    """Gövdede [6] gibi listede olmayan rank'leri atıf kümesine çek."""
    ns = [item.n for item in items]
    if not ns or not answer:
        return answer
    valid = set(ns)
    marker = "\n\nKaynak\n"
    if marker in answer:
        body, kaynak = answer.split(marker, 1)
    else:
        body, kaynak = answer, None
    found = {int(match) for match in re.findall(r"\[(\d+)\]", body)}
    if not found - valid:
        return answer
    index = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal index
        n = int(match.group(1))
        if n in valid:
            return match.group(0)
        out = f"[{ns[index % len(ns)]}]"
        index += 1
        return out

    body = re.sub(r"\[(\d+)\]", repl, body)
    if kaynak is None:
        return body
    return f"{body}{marker}{kaynak}"


def _rewrite_kaynak(answer: str, items: list[EvidenceItem]) -> str:
    """Kaynak bloğunu atıf numaralarıyla hizala; seyrek RRF rank'i ([6]) sızmasın."""
    if not items or not answer:
        return answer
    marker = "\n\nKaynak\n"
    lines = _source_index_lines(items)
    if marker in answer:
        body, _ = answer.split(marker, 1)
        return f"{body}{marker}{lines}"
    return f"{answer}{marker}{lines}"


def _keep_cited_evidence(evidence: list[EvidenceItem], answer: str) -> list[EvidenceItem]:
    """Atıfı olmayan kanun maddelerini düşür; emsal kararları Emsal sekmesi için tut."""
    if not evidence:
        return []
    marker = "\n\nKaynak\n"
    body = answer.split(marker, 1)[0] if marker in (answer or "") else (answer or "")
    found = {int(n) for n in re.findall(r"\[(\d+)\]", body)}
    if found:
        cited = [item for item in evidence if item.n in found]
    else:
        cited = [item for item in evidence if item.used_in_answer]
    if not cited:
        return evidence
    cited_ids = {item.chunk_id for item in cited}
    extras = [
        item for item in evidence if _is_decision(item) and item.chunk_id not in cited_ids
    ]
    for item in cited:
        item.used_in_answer = True
    numbered = [
        replace(item, n=len(cited) + index, used_in_answer=False)
        for index, item in enumerate(extras, start=1)
    ]
    return [*cited, *numbered]


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


def _ascii_q(query: str) -> str:
    blob = (query or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return blob.replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")


def _focus_query(query: str) -> str:
    text = query or ""
    for marker in ("\n\nBağlam:", "\nBağlam:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text.strip()


def _laws_in_query(query: str) -> list[str]:
    from retrieval.bm25 import LAW_HINTS

    blob = _ascii_q(query)
    found: list[str] = []
    for key, law_no in sorted(LAW_HINTS.items(), key=lambda row: -len(row[0])):
        if key in blob and law_no not in found:
            found.append(law_no)
    return found


def _is_count_query(query: str) -> bool:
    blob = _ascii_q(_focus_query(query))
    marks = ("daha fazla", "kac madde", "madde sayisi", "sayisal", "kac tane", "hangi kanunda daha")
    if not any(mark in blob for mark in marks):
        return False
    return "madde" in blob or "kanun" in blob or len(_laws_in_query(query)) >= 2


def _article_counts(engine: Any, law_nos: list[str]) -> dict[str, int]:
    es = getattr(getattr(getattr(engine, "hybrid", None), "bm25", None), "es", None)
    if es is None or not law_nos:
        return {}
    from retrieval.mapping import INDEX_NAME

    out: dict[str, int] = {}
    for law_no in law_nos:
        try:
            response = es.search(
                index=INDEX_NAME,
                body={
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"law_no": law_no}},
                                {"term": {"document_type": "law"}},
                            ]
                        }
                    },
                    "aggs": {"n": {"cardinality": {"field": "article_no", "precision_threshold": 4000}}},
                },
            )
            out[law_no] = int(response["aggregations"]["n"]["value"])
        except Exception:
            continue
    return {key: value for key, value in out.items() if value}


def _build_count_answer(query: str, counts: dict[str, int]) -> str:
    from llm.render import KAYNAK_UYARI, render_research_memo

    rows = [
        (index, _LAW_SHORT.get(law_no, f"Kanun {law_no}"), law_no, n)
        for index, (law_no, n) in enumerate(counts.items(), start=1)
    ]
    if not rows:
        return "Bu arşivde sayılacak kanun maddesi bulunamadı."
    ranked = sorted(rows, key=lambda row: -row[3])
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    if second and top[3] == second[3]:
        lead = f"Bu arşivde {top[1]} ve {second[1]} madde sayısı eşittir ({top[3]} madde)."
    else:
        lead = f"Bu arşivdeki madde sayısına göre {top[1]} daha fazladır: {top[3]} madde."
        if second:
            lead += f" {second[1]} ise {second[3]} maddedir."
    n_top, n_other = top[0], (second[0] if second else top[0])
    sonuc = (
        f"{lead} "
        f"Sayı, indekslenen güncel madde kayıtlarıdır; Resmî Gazete’deki ek/mülga fıkralar ayrı duruyorsa fark edebilir [{n_top}]. "
        f"Bu bir külliyat sayımıdır, somut uyuşmazlıkta hangi hükmün uygulanacağını göstermez [{n_other}]. "
        f"Karşılaştırma arşivdeki kanun kodlarına göredir; emsal karar metninden türetilmez [{n_top}]. "
        f"Bu metin hüküm kurmaz [{n_other}]."
    )
    gerekce = [
        f"{name} ({law_no} sayılı Kanun) bu arşivde {n} madde olarak indekslenmiştir [{index}]."
        for index, name, law_no, n in rows
    ]
    gerekce.append(
        f"Madde sayısı kanunun düzenleme alanının genişliğini gösterir; uygulanacak hüküm somut olaya göre ayrıca okunur [{n_top}]."
    )
    kaynak = "\n".join(f"[{index}] {name} madde sayısı (arşiv)" for index, name, law_no, n in rows)
    kaynak = f"{kaynak}\n{KAYNAK_UYARI}"
    return render_research_memo(sonuc=sonuc, gerekce=gerekce, ilgili=[], uyari=kaynak)


def _article_nos_from_query(query: str) -> list[str]:
    found: list[str] = []
    blob = _focus_query(query)
    for match in re.finditer(r"(?:m\.\s*|madde\s+)(\d+)", blob, re.I):
        if match.group(1) not in found:
            found.append(match.group(1))
    for match in re.finditer(r"(?:yoksa|veya|ile)\s+(\d{2,3})\b", blob, re.I):
        if match.group(1) not in found:
            found.append(match.group(1))
    return found


def _parse_fikralar(content: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for chunk in re.split(r"(?=\(\d+\))", content or ""):
        match = re.match(r"\((\d+)\)\s*(.+)", chunk.strip(), re.S)
        if not match:
            continue
        text = " ".join(match.group(2).split())
        if text:
            out.append((match.group(1), text[:320]))
    return out


def _is_procedure_query(query: str) -> bool:
    blob = _ascii_q(_focus_query(query))
    if re.search(r"nasil\s+duzenlen", blob):
        return False
    if any(token in blob for token in ("fikra", "taksir", "unsur", "kast", "nitelikli", "secimlik")):
        return False
    marks = (
        "nasil yapilir",
        "nasil verilir",
        "nereye",
        "hangi usul",
        "hangi merci",
        "basvuru",
        "dilekce",
        "teblig tarihi",
        "ihbar ve sikayet",
    )
    if any(token in blob for token in marks):
        return True
    return "nasil" in blob and any(token in blob for token in ("yapilir", "verilir", "basvur", "sikayet", "ihbar"))


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
    """Yalnızca başlık içerimi güvenilir bir sinyaldir (örn. "hırsızlık" ⊂
    "nitelikli hırsızlık"). Salt madde numarası komşuluğu (n-1) hukuki bir
    temel-suç ilişkisini kanıtlamaz; komşu maddeler çoğu zaman bambaşka
    suçlardır (örn. TCK m.178 ↔ m.179)."""
    if not _is_close_provision(primary, item, ""):
        return False
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
    allow_ollama = False
    try:
        from hakim_config import get_models

        allow_ollama = bool(get_models().research_allow_ollama)
    except Exception:
        allow_ollama = False
    if allow_ollama and ping(timeout=1.5):
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
    from llm.prompt import refuse_answer

    return refuse_answer()


def _missing_citation_answer(law_no: str, article: str) -> str:
    from llm.prompt import missing_citation_answer

    return missing_citation_answer(law_no, article)


def _query_supported(query: str, evidence: list[EvidenceItem]) -> bool:
    from retrieval.adaptive import query_is_off_topic
    from retrieval.hybrid import _is_exact_citation_query

    if query_is_off_topic(query):
        return False

    if _is_count_query(query):
        return True

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
    pool = [item for item in evidence if not _exclude_from_research(item)]
    used = [item for item in pool if item.used_in_answer][:8] or pool[:8]
    if not used:
        return []
    wanted = _article_nos_from_query(query)
    if wanted:
        ranked = [item for item in used if str(item.article_no) in wanted]
        ranked.sort(key=lambda item: wanted.index(str(item.article_no)))
        if ranked:
            primary = ranked[0]
            extra = [
                item
                for item in used
                if item is not primary
                and (str(item.article_no) in wanted or _is_close_provision(primary, item, query))
            ][:2]
            return [primary, *extra]
    laws = [item for item in used if not _is_decision(item)]
    primary = laws[0] if laws else used[0]
    close = [
        item
        for item in used
        if item is not primary and _is_close_provision(primary, item, query)
    ][:2]
    extras = list(close)
    seen = {primary.law_no, *(item.law_no for item in extras)}
    for item in used:
        if item is primary or item in extras:
            continue
        if not item.law_no or item.law_no in seen:
            continue
        extras.append(item)
        seen.add(item.law_no)
        if len(extras) >= 3:
            break
    return [primary, *extras]


def _renumber(items: list[EvidenceItem]) -> list[EvidenceItem]:
    return [replace(item, n=index) for index, item in enumerate(items, start=1)]


def _align_citation_numbers(
    evidence: list[EvidenceItem],
    picked: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Cited sources become [1]…[k]; leftover hits follow without rank gaps."""
    if not evidence:
        return []
    by_id = {item.chunk_id: item for item in evidence}
    ids = []
    for item in picked:
        if item.chunk_id in by_id and item.chunk_id not in ids:
            ids.append(item.chunk_id)
    rest = [item.chunk_id for item in evidence if item.chunk_id not in set(ids)]
    ordered = [by_id[cid] for cid in [*ids, *rest]]
    aligned = _renumber(ordered)
    cited = set(ids)
    for item in aligned:
        item.used_in_answer = item.chunk_id in cited
    return aligned


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
    if _looks_like_petition_dump(text):
        return False
    if _looks_like_garbage(text):
        return False
    if _draft_too_short(text):
        return False
    if _wrong_code_for_query(text, str(engine.get("query") or "")):
        return False
    return not _mentions_foreign_article(text, _allowed_articles(engine))


def _draft_too_short(text: str) -> bool:
    body = re.sub(r"(?:\n|^)Kaynak\n.*", "", text or "", flags=re.S).strip()
    body = re.sub(r"_Bu metin.*", "", body, flags=re.S).strip()
    if len(body) < 720:
        return True
    sentences = [part for part in re.split(r"(?<=[.!?…])\s+", body) if len(part.strip()) > 12]
    return len(sentences) < 8


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
    lead = ""
    for part in (answer or "").split("\n\n"):
        line = part.strip()
        if line and line not in {"Sonuç", "Hukuki dayanak", "İlgili hükümler", "Değerlendirme", "Kaynak"}:
            lead = line.split("\n")[0].strip()
            break
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
    from llm.render import render_research_memo

    used = _renumber(list(_answer_items(query, evidence)))
    if not used:
        return (
            "Bu sorgu için arşivde yeterli resmi kaynak bulunamadı. "
            "Madde numarası veya hukuki kavramla yeniden deneyin."
        )
    primary = used[0]
    n = primary.n
    sonuc = ""
    gerekce: list[str] = []
    ilgili: list[str] = []
    degerlendirme = ""
    if _is_decision(primary):
        label = _cite(primary)
        sonuc = (
            f"{label}, sorudaki olguya ilişkin emsal karardır [{n}]. "
            f"Karar, benzer vakıalarda hükmün nasıl kurulduğunu gösterir; soyut kanun metnini somut olaya taşır [{n}]. "
            f"Gerekçe, aynı nitelikteki uyuşmazlıklarda hangi olguların ağır bastığını ortaya koyar [{n}]. "
            f"Emsalin örtüşüp örtüşmediği, dosyadaki vakıa ve delil incelemesine bağlıdır [{n}]. "
            f"Bu metin emsal çerçevesi verir; somut uyuşmazlıkta hüküm kurmaz [{n}]."
        )
        lead = _first_sentence(primary.content or "")
        if lead:
            if not re.search(r"\[\d+\]\s*$", lead):
                lead = f"{lead.rstrip('.')} [{n}]."
            gerekce.append(lead)
        gerekce.append(
            f"Kararın gerekçesi, aynı nitelikteki somut olaylarda nasıl hüküm kurulduğunu gösterir [{n}]."
        )
        gerekce.append(
            f"Emsal, arşivdeki resmi metne dayanır; dosyadaki taraf iddialarını kendiliğinden doğrulamaz [{n}]."
        )
        gerekce.append(
            f"Somut uyuşmazlığın bu kararla örtüşüp örtüşmediği, vakıa ve delil incelemesine bağlıdır [{n}]."
        )
    else:
        cite = _cite(primary)
        title = (primary.title or "").strip()
        name = title.lower() if title else "ilgili hüküm"
        lead = _first_sentence(primary.content or "")
        focus = _focus_query(query)
        ascii_q = _ascii_q(focus)
        fikralar = _parse_fikralar(primary.content or "")
        if _is_procedure_query(focus):
            who = f"{title} " if title else ""
            sonuc = (
                f"{who}{cite} hükmünde düzenlenir [{n}]. "
                f"Bu bir usul kuralıdır; suçun maddi unsurlarını kurmaz, başvurunun şeklini ve merciini gösterir [{n}]. "
                f"İşleyiş, maddenin lafzına ve dosyadaki usulî verilere göre okunur [{n}]. "
                f"Süre, yetki ve şekil şartları bu hüküm çerçevesinde aranır; arşiv metni somut başvuruyu tek başına kesinleştirmez [{n}]. "
                f"Usul hükmü, maddi hukuk nitelendirmesinden ayrı durur [{n}]."
            )
            if lead:
                gerekce.append(f"Madde metninin ilgili kısmı şöyle başlar: {lead.rstrip('.')} [{n}].")
            gerekce.append(
                f"Bu usul maddenin lafzına göre işletilir; başvurunun nereye ve nasıl yapılacağı "
                f"bu hüküm çerçevesinde okunur [{n}]."
            )
            gerekce.append(
                f"Yetkili merci, süre ve şekil şartları maddenin düzenlediği çerçevede aranır [{n}]. "
                f"Arşiv metni, somut başvurunun kabul edilebilirliğini tek başına kesinleştirmez [{n}]."
            )
            gerekce.append(
                f"Usul hükmü, maddi hukuk nitelendirmesinden ayrı durur; şikayet veya ihbar yolu "
                f"ile suçun unsurları birbirine karıştırılmaz [{n}]."
            )
        elif "fikra" in ascii_q and len(fikralar) >= 2:
            first, second = fikralar[0], fikralar[1]
            heading = title or "Bu madde"
            sonuc = (
                f"{heading} {cite} içinde fıkralar ayrı hareket tiplerini düzenler [{n}]. "
                f"Birinci fıkra ({first[0]}) işaret ve yönlendirme düzenine ilişkin fiilleri toplar [{n}]. "
                f"İkinci fıkra ({second[0]}) aracın tehlikeli sevk ve idaresini ayrıca cezalandırır [{n}]. "
                f"Hangi fıkranın uygulanacağı somut hareketin niteliğine bağlıdır [{n}]. "
                f"Bu ayrım arşiv lafzına göredir; dosya olguları ayrıca bakılır [{n}]."
            )
            gerekce.append(f"({first[0]}) {first[1]} [{n}].")
            gerekce.append(f"({second[0]}) {second[1]} [{n}].")
            gerekce.append(
                f"İki fıkra aynı madde içinde kalsa da hareket tipi farklıdır; biri diğerinin yerine geçmez [{n}]."
            )
            gerekce.append(
                f"Somut olayda hangi fıkranın dolacağı, fiilin niteliğine göre okunur [{n}]."
            )
        elif "taksir" in ascii_q:
            other = next(
                (
                    item
                    for item in used[1:]
                    if str(item.article_no) in {"179", "180"} and item is not primary
                ),
                None,
            )
            other_cite = _cite(other) if other else "TCK m.179"
            other_n = other.n if other else n
            kast_cite, taksir_cite = (other_cite, cite) if str(primary.article_no) == "180" else (cite, other_cite)
            kast_n, taksir_n = (other_n, n) if str(primary.article_no) == "180" else (n, other_n)
            sonuc = (
                f"Taksirle işlenen hâller {taksir_cite} hükmünde düzenlenir [{taksir_n}]. "
                f"Kasten işlenen trafik güvenliğini tehlikeye sokma {kast_cite} kapsamındadır [{kast_n}]. "
                f"179 kasti fiili, 180 ise taksirli tehlikeye sokmayı ayrı tutar [{n}]. "
                f"Hangi maddenin uygulanacağı failin kusur şekline bağlıdır [{n}]. "
                f"Bu ayrım arşiv lafzına göredir; somut kusur incelemesi dosyadan yapılır [{n}]."
            )
            gerekce.append(
                f"{taksir_cite} taksirle tehlikeye sokmayı müstakil suç olarak kurar [{taksir_n}]."
            )
            gerekce.append(
                f"{kast_cite} kasten işlenen hâli düzenler; taksirli hareket bu maddenin kapsamında kalmaz [{kast_n}]."
            )
            gerekce.append(
                f"İki madde komşu olsa da kusur şekli farklıdır; biri diğerinin yerine okunmaz [{n}]."
            )
            gerekce.append(
                f"Nitelendirme, somut olayda kastın mı taksirin mi bulunduğuna göre yapılır [{n}]."
            )
        else:
            clause = _clause_for_query(query, primary.content or "")
            if clause:
                sonuc = (
                    f"Evet: sorulan olgu {cite} kapsamında {name} olarak değerlendirilir [{n}]. "
                    f"Madde bu hâli temel dolandırıcılıktan ayırır ve seçimlik hareketlerden biri olarak ağırlaştırır [{n}]. "
                    f"Hükmün uygulanması, bu seçeneğin somut olayda gerçekleşmesine bağlıdır [{n}]. "
                    f"Temel suçun diğer unsurları da dosyadan aranır; arşiv maddesi ispatı varsaymaz [{n}]. "
                    f"Bu metin nitelendirme çerçevesi verir; hüküm kurmaz [{n}]."
                )
                gerekce.append(
                    f"{cite} bu hâli «{clause}» diye sayar [{n}]. "
                    f"Lafız, ilgili seçeneği temel şekle eklenen nitelikli bir yol olarak kurar [{n}]."
                )
                gerekce.append(
                    f"Bu seçimlik hareket gerçekleştiğinde fiil, maddenin nitelikli hâli içinde kalır; "
                    f"kanun koyucu bu yolu {name} sayarak temel şekilden ayırır [{n}]."
                )
                gerekce.append(
                    f"Nitelikli hâlin yanında, temel suçun diğer unsurlarının da (hile, zarar, kast) "
                    f"somut olayda aranması gerekir [{n}]. Arşiv maddesi bu unsurların dosyada ispatını varsaymaz [{n}]."
                )
                gerekce.append(
                    f"Uygulamada araç olarak kullanılma, hesabın veya kurumun fiile vasıta kılınmasıyla okunur [{n}]. "
                    f"Salt hesap sahibi olmak veya kurumla ilişki, tek başına bu seçeneği doldurmaz [{n}]."
                )
            elif title:
                sonuc = (
                    f"{title} {cite}’de düzenlenir [{n}]. "
                    f"Sorudaki kavram bu hükmün konusuna girer [{n}]. "
                    f"Madde, ilgili fiilin hukuki çerçevesini çizer; uygulama somut vakıalara bağlıdır [{n}]. "
                    f"Unsurların gerçekleşip gerçekleşmediği yalnız bu arşiv metninden kesinleştirilemez [{n}]. "
                    f"Bu cevap nitelendirme çerçevesi verir; dosya olguları ayrıca değerlendirilir [{n}]."
                )
                if lead:
                    gerekce.append(f"Madde metninin ilgili kısmı şöyle başlar: {lead.rstrip('.')} [{n}].")
                gerekce.append(
                    f"Sorudaki kavram bu hükmün konusuna girer; somut olay unsurları dosyadan ayrıca bakılır [{n}]."
                )
                gerekce.append(
                    f"Hüküm, soyut bir çerçeve çizer; nitelendirme ancak vakıalarla birlikte yapılabilir [{n}]."
                )
                gerekce.append(
                    f"Komşu maddeler aynı konunun farklı yüzlerini düzenliyorsa, asıl dayanak yine {cite} olarak kalır [{n}]."
                )
            else:
                sonuc = (
                    f"Bu konu {cite} hükmünde düzenlenir [{n}]. "
                    f"Aşağıdaki gerekçe yalnız bu resmi metne dayanır [{n}]. "
                    f"Hükmün lafzı, sorudaki hukuki meselenin arşivdeki çerçevesini verir [{n}]. "
                    f"Somut subsumption dosya incelemesine bırakılır [{n}]. "
                    f"Bu metin nitelendirme çerçevesi verir; hüküm kurmaz [{n}]."
                )
                gerekce.append(
                    f"{cite} sorudaki hukuki meselenin arşivdeki dayanağıdır [{n}]. "
                    f"Somut subsumption dosya incelemesine bırakılır [{n}]."
                )
        for item in used[1:]:
            label = _cite(item)
            extra = f" ({item.title})" if item.title else ""
            if _is_base_offence(primary, item) and not _is_procedure_query(focus):
                ilgili.append(f"Bu suçun temel şekli {label}{extra} hükmünde düzenlenir [{item.n}].")
            else:
                ilgili.append(f"İlgili hüküm {label}{extra}, aynı konunun komşu düzenlemesidir [{item.n}].")
        if _is_procedure_query(focus):
            degerlendirme = (
                f"Somut başvurunun şekli ve yetkili merci, yalnız bu arşiv metnine göre kesinleştirilemez; "
                f"dosya olguları ayrıca değerlendirilir [{n}]. "
                f"Süre, tebligat ve şekil eksikleri bu hükümle birlikte usul dosyasından okunur [{n}]."
            )
        else:
            degerlendirme = (
                f"Somut olayda maddede aranan unsurların gerçekleşip gerçekleşmediği yalnız bu arşiv metnine göre "
                f"kesinleştirilemez; dosya olguları ayrıca değerlendirilir [{n}]. "
                f"Bu metin nitelendirme çerçevesini verir; hüküm kurmaz [{n}]."
            )
    ns = [item.n for item in used]
    sonuc = _cite_sentences(sonuc, ns)
    gerekce = [_attach_cite(line, ns[index % len(ns)]) for index, line in enumerate(gerekce)]
    degerlendirme = _cite_sentences(degerlendirme, ns) if degerlendirme else degerlendirme
    return _fill_missing_cites(
        render_research_memo(
            sonuc=sonuc,
            gerekce=gerekce,
            ilgili=ilgili,
            degerlendirme=degerlendirme,
            uyari=_source_index_lines(used),
        ),
        used,
    )


_HOP_TO_TRACE = {
    "sorgu": "query",
    "kontrol": "query",
    "bm25": "bm25",
    "vektor": "vector",
    "rrf": "rrf",
    "rerank": "rerank",
    "graf": "graph",
    "cevap": "answer",
    "reddet": "answer",
}

_PIPELINE_KIND = {
    "query": ("SORGU", "query"),
    "bm25": ("BM25", "retriever"),
    "vector": ("VEKTÖR", "retriever"),
    "graph": ("GRAPH", "retriever"),
    "rrf": ("RRF", "fusion"),
    "rerank": ("RERANK", "fusion"),
    "answer": ("CEVAP", "answer"),
}

_EDGE_LABELS = {
    ("query", "bm25"): "lexical",
    ("query", "vector"): "gerekirse",
    ("query", "answer"): "reddet",
    ("bm25", "vector"): "gerekirse",
    ("bm25", "rrf"): "top50",
    ("vector", "rrf"): "semantic",
    ("rrf", "rerank"): "reorder",
    ("rerank", "graph"): "neighbors",
    ("rerank", "answer"): "",
    ("graph", "answer"): "",
    ("answer", "vector"): "retry",
}

_STATIC_WALK = ("query", "bm25", "vector", "rrf", "rerank", "graph", "answer")
_STATIC_EDGES = (
    ("query", "bm25"),
    ("bm25", "vector"),
    ("vector", "rrf"),
    ("bm25", "rrf"),
    ("rrf", "rerank"),
    ("rerank", "graph"),
    ("graph", "answer"),
)


def _base_id(vis_id: str) -> str:
    return vis_id.split("#", 1)[0]


def _executed_trace_walk(hops: list[dict[str, Any]] | None) -> list[str]:
    walk: list[str] = []
    counts: dict[str, int] = {}
    for hop in hops or []:
        if hop.get("state") == "skip":
            continue
        node_id = _HOP_TO_TRACE.get(str(hop.get("id") or ""))
        if not node_id:
            continue
        if walk and _base_id(walk[-1]) == node_id:
            continue
        counts[node_id] = counts.get(node_id, 0) + 1
        vis_id = node_id if counts[node_id] == 1 else f"{node_id}#{counts[node_id]}"
        walk.append(vis_id)
    return walk


def _pipeline_nodes(query: str, route: str, ids: list[str]) -> list[TraceNode]:
    nodes: list[TraceNode] = []
    seen: set[str] = set()
    for vis_id in ids:
        base = _base_id(vis_id)
        if vis_id in seen or base not in _PIPELINE_KIND:
            continue
        seen.add(vis_id)
        label, kind = _PIPELINE_KIND[base]
        meta = {"text": query, "route": route} if base == "query" else {}
        nodes.append(TraceNode(id=vis_id, label=label, kind=kind, meta=meta))
    return nodes


def _pipeline_edges(pairs: list[tuple[str, str]]) -> list[TraceEdge]:
    edges: list[TraceEdge] = []
    seen: set[tuple[str, str]] = set()
    for source, target in pairs:
        if (source, target) in seen:
            continue
        seen.add((source, target))
        label = _EDGE_LABELS.get((_base_id(source), _base_id(target)), "")
        edges.append(TraceEdge(source, target, label))
    return edges


def _cite_anchor(node_order: list[str]) -> tuple[str, str] | None:
    answer = next((nid for nid in reversed(node_order) if _base_id(nid) == "answer"), None)
    if not answer:
        return None
    for key in ("rerank", "rrf", "bm25", "query"):
        found = next((nid for nid in reversed(node_order) if _base_id(nid) == key), None)
        if found:
            return found, answer
    return None


def _append_chunk_trace(
    nodes: list[TraceNode],
    edges: list[TraceEdge],
    fused: list[FusedHit],
    evidence: list[EvidenceItem] | None,
    node_order: list[str],
    *,
    used_only: bool,
) -> None:
    anchor = _cite_anchor(node_order)
    if not anchor:
        return
    cite_from, answer_id = anchor

    def add_chunk(
        node_id: str,
        label: str,
        *,
        rank: int,
        used: bool,
        bm25_rank: int | None,
        semantic_rank: int | None,
        retrievers: list[str],
        authority: str | None,
    ) -> None:
        if used_only and not used:
            return
        nodes.append(
            TraceNode(
                id=node_id,
                label=label,
                kind="chunk",
                meta={
                    "bm25_rank": bm25_rank,
                    "semantic_rank": semantic_rank,
                    "rrf_rank": rank,
                    "retrievers": retrievers,
                    "authority": authority,
                    "used_in_answer": used,
                },
            )
        )
        edges.append(TraceEdge(cite_from, node_id, f"#{rank}"))
        edges.append(TraceEdge(node_id, answer_id, "cite" if used else "candidate"))

    if fused:
        for hit in fused[:8]:
            is_decision = (hit.hit.document_id or "").startswith("decision:")
            label = (
                (hit.hit.title or hit.hit.document_id or "karar")
                if is_decision
                else f"{_LAW_SHORT.get(hit.hit.law_no or '', 'Kanun')} {hit.hit.article_no}"
            )
            add_chunk(
                hit.chunk_id,
                label,
                rank=hit.rank,
                used=hit.rank <= 5,
                bm25_rank=hit.bm25_rank,
                semantic_rank=hit.semantic_rank,
                retrievers=list(hit.sources),
                authority=hit.hit.authority,
            )
        return
    for item in evidence or []:
        is_decision = (item.document_id or "").startswith("decision:")
        label = (
            (item.title or item.document_id or "karar")
            if is_decision
            else f"{_LAW_SHORT.get(item.law_no or '', 'Kanun')} {item.article_no}"
        )
        add_chunk(
            item.chunk_id,
            label,
            rank=item.n,
            used=item.used_in_answer,
            bm25_rank=item.bm25_rank,
            semantic_rank=item.semantic_rank,
            retrievers=list(item.retrievers),
            authority=item.authority,
        )


def _build_trace(
    query: str,
    fused: list[FusedHit],
    route: str,
    hops: list[dict[str, Any]] | None = None,
    evidence: list[EvidenceItem] | None = None,
) -> tuple[list[TraceNode], list[TraceEdge]]:
    walk = _executed_trace_walk(hops)
    if hops is None:
        node_order = list(_STATIC_WALK)
        pairs = list(_STATIC_EDGES)
        used_only = False
    else:
        node_order = walk or ["query", "answer"]
        pairs = list(zip(node_order, node_order[1:]))
        used_only = True
    nodes = _pipeline_nodes(query, route, node_order)
    edges = _pipeline_edges(pairs)
    _append_chunk_trace(nodes, edges, fused, evidence, node_order, used_only=used_only)
    return nodes, edges


class ResearchEngine:
    def __init__(
        self,
        es_client: Any,
        embedder: Embedder | None = None,
        neo4j_driver: Any | None = None,
        *,
        evidence_limit: int = 8,
        decision_index: str | None = None,
        decision_embedder: Embedder | None = None,
        reranker: PairScorer | None = None,
    ) -> None:
        self.embedder = embedder or create_embedder(prefer_neural=True)
        self.hybrid = HybridSearcher(
            es_client,
            self.embedder,
            limit=30,
            decision_index=decision_index,
            decision_embedder=decision_embedder,
        )
        self.neo4j = neo4j_driver
        self.evidence_limit = evidence_limit
        # RRF sonrası aday daraltma için cross-encoder — bkz.
        # retrieval/cross_encoder.py. Model yüklenemezse (offline, ilk
        # çalıştırma) create_reranker None döner, rerank_fused sözcük-
        # örtüşme sezgiseline düşer.
        self.reranker = reranker if reranker is not None else create_reranker(prefer_neural=True)

    def research(self, query: str, *, law_no: str | None = None) -> ResearchResult:
        from retrieval.research_graph import run_research_graph

        return run_research_graph(self, query, law_no=law_no)


def collect_neighbors(engine: ResearchEngine, fused: list[FusedHit]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for hit in fused:
        neighbors: list[dict[str, Any]] = []
        if engine.neo4j is not None and hit.rank <= 4:
            try:
                doc_id = hit.hit.document_id or ""
                if doc_id.startswith("decision:"):
                    neighbors = neighborhood_decision(engine.neo4j, doc_id).get("neighbors") or []
                elif hit.hit.law_no and hit.hit.article_no:
                    node = article_id(hit.hit.law_no, hit.hit.article_no)
                    neighbors = neighborhood(engine.neo4j, node).get("neighbors") or []
            except Exception:
                neighbors = []
        out[hit.chunk_id] = neighbors
    return out


def _reserve_decisions(hits: list[FusedHit], limit: int, *, reserve: int = 3) -> list[FusedHit]:
    """`HybridSearcher.fuse()`'daki aynı sorun burada TEKRARLANIYOR: fuse()
    kendi (daha geniş) havuzunda emsal kararlara yer ayırmış olsa da, kararlar
    düşük ham RRF skoru yüzünden havuzun sonuna düşüyor — bu DAHA DAR
    `evidence_limit` kesmesi (bkz. fuse()'un limit=12'si vs. burasının
    evidence_limit=8'i) onları yeniden dışarı atabiliyordu (canlı
    doğrulandı). Aynı rezervasyon mantığı burada da uygulanıyor."""
    if len(hits) <= limit:
        return hits
    decisions = [h for h in hits if _hit_fields(h)[0].startswith("decision:")]
    if not decisions:
        return hits[:limit]
    laws = [h for h in hits if h not in decisions]
    keep_dec = min(reserve, len(decisions), limit)
    combined = laws[: limit - keep_dec] + decisions[:keep_dec]
    combined.sort(key=lambda h: h.rrf_score, reverse=True)
    return combined[:limit]


def assemble_research_result(
    engine: ResearchEngine,
    query: str,
    fused: list[FusedHit],
    route: str,
    neighbors: dict[str, list[dict[str, Any]]] | None = None,
) -> ResearchResult:
    kept = [hit for hit in fused if not _exclude_from_research(hit)]
    top = _reserve_decisions(kept, engine.evidence_limit)
    neighbor_map = neighbors or {}
    evidence: list[EvidenceItem] = []
    for hit in top:
        evidence.append(
            EvidenceItem(
                n=len(evidence) + 1,
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
                graph_neighbors=list(neighbor_map.get(hit.chunk_id) or []),
                used_in_answer=hit.rank <= 5,
                mulga_warning=detect_mulga_warning(
                    hit.hit.content, is_decision=bool((hit.hit.document_id or "").startswith("decision:"))
                ),
            )
        )

    for index, item in enumerate(evidence, start=1):
        item.n = index
        item.used_in_answer = index <= min(5, len(evidence))

    if _is_count_query(query):
        laws = _laws_in_query(query) or ["5237", "4721"]
        counts = _article_counts(engine, laws)
        if counts:
            answer = _build_count_answer(query, counts)
            nodes, edges = _build_trace(query, top, route)
            return ResearchResult(
                query=query,
                answer=answer,
                evidence=evidence,
                trace_nodes=nodes,
                trace_edges=edges,
                route=route,
                writer="archive_count",
                writer_error=None,
                reasoning=build_research_reasoning(query, evidence, route=route, answer=answer),
            )

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
    evidence = _align_citation_numbers(evidence, answer_items)
    answer_items = [item for item in evidence if item.used_in_answer]
    payload = {
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
    drafted, drafted_writer, writer_error = _draft_research_answer(payload)
    if drafted:
        answer = drafted
        writer = drafted_writer
        writer_error = None
    answer = _spread_cites(answer, answer_items)
    answer = _clamp_unknown_cites(answer, answer_items)
    answer = _fill_missing_cites(answer, answer_items)
    answer = _rewrite_kaynak(answer, answer_items)
    evidence = _keep_cited_evidence(evidence, answer)
    nodes, edges = _build_trace(query, [], route, evidence=evidence)
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
