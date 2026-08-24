from __future__ import annotations

import json
import re
from typing import Any, Callable

from llm.api_client import api_chat, api_configured
from llm.client import OllamaError, chat, ollama_enabled, parse_json_content, ping
from llm.formats import (
    belge_system_prompt,
    load_belge,
    load_format,
    system_prompt,
    validate_belge,
    validate_parsed,
)
from llm.render import petition_view, render_arastirma, render_belge, render_evrak, render_islem_module, render_surec

ACTION_TO_BELGE = {
    "istinaf": "istinaf",
    "itiraz": "itiraz",
    "cevap": "cevap",
    "sikayet": "sikayet",
    "suc_duyurusu": "suc_duyurusu",
    "temyiz": "temyiz",
    "katilma": "katilma",
    "bireysel_basvuru": "bireysel_basvuru",
    "idari_dava": "idari_dava",
    "tahliye": "tahliye",
    "adli_kontrol_itiraz": "adli_kontrol_itiraz",
    "ust_yazi": "ust_yazi",
    "bilgi_yazisi": "bilgi_yazisi",
    "olur": "olur",
    "cevap_yazisi": "cevap_yazisi",
}

ChatFn = Callable[..., str]

SPAN_CHARS = 160
EVIDENCE_SPAN_CHARS = 360
USER_TEXT_CHARS = 800
RELATED_HITS = 3
EVIDENCE_HITS = 4


def _span(text: Any, limit: int = SPAN_CHARS) -> str:
    return " ".join(str(text or "").split())[:limit]


def compact_engine(engine: dict[str, Any]) -> dict[str, Any]:
    """Groq/Ollama'ya tam madde dump'ı gitmesin: künye + kısa span."""
    classification = engine.get("classification") or {}
    related = []
    for hit in (engine.get("related") or [])[:RELATED_HITS]:
        related.append(
            {
                "n": hit.get("n"),
                "title": hit.get("title"),
                "article_no": hit.get("article_no"),
                "law_no": hit.get("law_no"),
                "span": _span(hit.get("content") or hit.get("span")),
            }
        )
    evidence = []
    for item in (engine.get("evidence") or [])[:EVIDENCE_HITS]:
        evidence.append(
            {
                "n": item.get("n"),
                "title": item.get("title"),
                "article_no": item.get("article_no"),
                "law_no": item.get("law_no"),
                "span": _span(item.get("content") or item.get("span"), EVIDENCE_SPAN_CHARS),
            }
        )
    deadlines = []
    for item in engine.get("deadlines") or []:
        deadlines.append(
            {
                "name": item.get("name"),
                "last_day": item.get("last_day"),
                "legal_basis": item.get("legal_basis"),
                "missing": item.get("missing"),
            }
        )
    return {
        "action": engine.get("action"),
        "user_text": _span(engine.get("user_text"), USER_TEXT_CHARS),
        "query": _span(engine.get("query"), 240) or None,
        "verdict": engine.get("verdict"),
        "classification": {
            "label": classification.get("label"),
            "document_type": classification.get("document_type"),
            "legal_nature": classification.get("legal_nature"),
            "stage": classification.get("stage"),
            "unit": classification.get("unit"),
        },
        "fields": engine.get("fields") or {},
        "missing": engine.get("missing") or [],
        "dates": engine.get("dates") or {},
        "deadlines": deadlines,
        "related": related,
        "evidence": evidence,
        "gaps": engine.get("gaps") or [],
    }


def _user_payload(engine: dict[str, Any]) -> str:
    extra = ""
    if engine.get("gaps"):
        extra = (
            "\nEksik alanları doldurmak için kimlik, T.C. no, esas no veya tarih uydurma. "
            "Eksik kimlik/tarih için «[…]» yer tutucu kullan. Kullanıcının cümlelerini olay bölümünde koru.\n"
        )
    if not (engine.get("related") or engine.get("evidence")):
        extra += (
            "\nrelated/evidence boş: hukuki_nitelendirme'ye ceza maddesi numarası yazma.\n"
        )
    return (
        "Aşağıdaki motor çıktısını kaynak kabul et. Yeni madde, tarih veya süre uydurma."
        + extra
        + "\n"
        + json.dumps(compact_engine(engine), ensure_ascii=False, default=str)
    )


BELGE_FIELD_ALIASES = (
    ("sure", "sure_cumlesi"),
    ("karar", "itiraz_olunan"),
    ("taraflar", "cevap_veren"),
    ("hukuki_sebepler", "sebepler"),
)


def _merge_example(example: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    merged = dict(example)
    for key, value in parsed.items():
        if value not in (None, "", []):
            merged[key] = value
    return merged


def _alias_belge_fields(parsed: dict[str, Any]) -> dict[str, Any]:
    out = dict(parsed)
    for left, right in BELGE_FIELD_ALIASES:
        if out.get(left) in (None, "", []) and out.get(right) not in (None, "", []):
            out[left] = out[right]
        if out.get(right) in (None, "", []) and out.get(left) not in (None, "", []):
            out[right] = out[left]
    return out


def resolve_writer(*, allow_ollama: bool = True) -> ChatFn | None:
    if api_configured():
        return api_chat
    if allow_ollama and ollama_enabled() and ping():
        return chat
    return None


def writer_name(*, allow_ollama: bool = True) -> str:
    if api_configured():
        return "api"
    if allow_ollama and ollama_enabled() and ping():
        return "ollama"
    return "extractive"


def _tr_day(value: Any) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return f"{raw[8:10]}.{raw[5:7]}.{raw[:4]}"
    return raw


def extractive_surec(engine: dict[str, Any]) -> dict[str, Any]:
    """Son günü motor doldurur; örnek JSON veya model tarihi ezmez."""
    from document_ai.answers import STAGE_TR

    cls = engine.get("classification") or {}
    stage = str(cls.get("stage") or "belirsiz")
    stage_tr = STAGE_TR.get(stage, stage)
    asama = f"Evrak {stage_tr} aşamasındadır."
    if stage == "kovusturma":
        asama += " İstinaf yolu açıktır; dosya henüz istinaf mahkemesinde değildir."
    labels = {
        "itiraz": "İtiraz",
        "istinaf": "İstinaf",
        "temyiz": "Temyiz",
        "bireysel_basvuru": "Bireysel başvuru",
        "sikayet": "Şikayet",
        "idari_dava": "İdari dava",
        "istinaf_idari": "İdari istinaf",
        "temyiz_idari": "İdari temyiz",
    }
    kanun = [
        {"id": rem, "cumle": f"{labels.get(rem, rem)} bu hüküm için işletilebilir."}
        for rem in cls.get("remedies") or []
    ]
    sureler = []
    for item in engine.get("deadlines") or []:
        name = str(item.get("name") or "Süre")
        rid = str(item.get("rule_id") or name)
        last = item.get("last_day")
        trigger = item.get("trigger")
        missing = item.get("missing")
        basis = item.get("legal_basis") or []
        label = str(basis[0]) if basis else ""
        extra = f" ({label})" if label else ""
        if last:
            trig = f"tebliğ {_tr_day(trigger)}" if trigger else "tetikleyici"
            anlatim = f"{name}, {trig} ise son gün {_tr_day(last)}’dir{extra}."
        else:
            anlatim = f"{name}: hesaplanamadı ({missing or 'tetikleyici yok'})."
        sureler.append({"rule_id": rid, "anlatim": anlatim})
    return {
        "asama_cumlesi": asama,
        "kanun_yollari": kanun,
        "sureler": sureler,
        "uyari": "Süreler kural motoruyla hesaplanmıştır; model tahmin etmez.",
    }


def write_module(
    module_id: str,
    engine: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
    allow_ollama: bool = True,
) -> str | None:
    fn = chat_fn or resolve_writer(allow_ollama=allow_ollama)
    if module_id == "surec":
        parsed = extractive_surec(engine)
        if fn is not None:
            try:
                raw = fn(
                    [
                        {"role": "system", "content": system_prompt(module_id)},
                        {"role": "user", "content": _user_payload(engine)},
                    ]
                )
                asama = str(parse_json_content(raw).get("asama_cumlesi") or "").strip()
                if asama:
                    parsed["asama_cumlesi"] = asama
            except Exception:
                pass
        return render_surec(parsed)
    if fn is None:
        return None
    raw = fn(
        [
            {"role": "system", "content": system_prompt(module_id)},
            {"role": "user", "content": _user_payload(engine)},
        ]
    )
    spec = load_format(module_id)
    parsed = parse_json_content(raw)
    parsed = _merge_example(spec.get("example") or {}, parsed)
    errors = validate_parsed(module_id, parsed)
    if errors:
        raise OllamaError("; ".join(errors))
    if module_id == "arastirma":
        return render_arastirma(parsed)
    if module_id == "evrak":
        return render_evrak(parsed)
    return render_islem_module(parsed)


NARRATIVE_FIELD = {
    "sikayet": "olay",
    "suc_duyurusu": "olay",
    "cevap": "esasa_cevap",
    "itiraz": "karar",
    "istinaf": "hukum",
    "temyiz": "karar",
    "katilma": "dava",
    "bireysel_basvuru": "olay",
    "idari_dava": "islem",
    "tahliye": "tutuklama",
    "adli_kontrol_itiraz": "karar",
    "ust_yazi": "metin",
    "bilgi_yazisi": "metin",
    "olur": "metin",
    "cevap_yazisi": "metin",
}


def _overlay_filled(parsed: dict[str, Any], data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key == "variant":
            continue
        if value in (None, "", [], "—"):
            continue
        parsed[key] = value


def _extractive_kamu(spec: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    """Gelen kamu evrakının sayı/konu/muhatap/ilgi alanlarından 2646 taslağı."""
    from llm.resmi_yazisma import draft_data_from_analysis

    parsed = dict(spec.get("example") or {})
    data = draft_data_from_analysis(engine)
    _overlay_filled(parsed, data)
    fields = engine.get("fields") or {}
    if fields.get("kurum"):
        parsed["makam"] = fields["kurum"]
        parsed["kurum"] = fields["kurum"]
    elif data.get("kurum"):
        parsed["makam"] = data["kurum"]
        parsed["kurum"] = data["kurum"]
    else:
        parsed["makam"] = spec.get("makam") or parsed.get("makam")
    parsed["onay_notu"] = "Taslaktır. EBYS/UYAP’a otomatik gönderim yoktur."
    return parsed


def _islem_gaps(engine: dict[str, Any]) -> list[dict[str, str]]:
    if "gaps" in engine:
        return [item for item in (engine.get("gaps") or []) if isinstance(item, dict)]
    from document_ai.gaps import diagnose_islem_gaps

    return diagnose_islem_gaps(
        str(engine.get("action") or ""),
        str(engine.get("user_text") or ""),
        engine.get("fields") or {},
        engine.get("dates") or {},
    )


def _apply_islem_gaps(parsed: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    from document_ai.gaps import apply_gap_placeholders

    return apply_gap_placeholders(parsed, _islem_gaps(engine), str(engine.get("user_text") or ""))


NO_MADDE_CUMLE = "Mevzuat aramasında eşleşen madde yok; taslağa TCK maddesi yazılmadı."
_ARTICLE_RE = re.compile(r"m\.\s*(\d+[a-zA-Z]?(?:/\d+)?)", re.IGNORECASE)
DEFAULT_SIKAYET_TALEP = (
    "Şikayet edilen hakkında soruşturma açılması, delillerin toplanması ve kamu davası açılması talep olunur."
)


def _sourced_articles(engine: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for hit in list(engine.get("related") or []) + list(engine.get("evidence") or []):
        no = str(hit.get("article_no") or "").strip()
        if not no:
            continue
        out.add(no)
        out.add(no.split("/")[0])
    return out


def _madde_ok(token: str, allowed: set[str]) -> bool:
    raw = token.strip()
    if not raw:
        return True
    return raw in allowed or raw.split("/")[0] in allowed


def _nitelendirme_unsourced(row: Any, allowed: set[str]) -> bool:
    if isinstance(row, dict):
        madde = str(row.get("madde") or "").strip()
        blob = f"{madde} {row.get('cumle') or ''}"
    else:
        madde = ""
        blob = str(row)
    cited = [m.group(1) for m in _ARTICLE_RE.finditer(blob)]
    if madde:
        cited.append(madde)
    if not cited:
        return False
    if not allowed:
        return True
    return any(not _madde_ok(token, allowed) for token in cited)


def _fold_tr(text: str) -> str:
    return (
        str(text or "")
        .lower()
        .replace("ı", "i")
        .replace("î", "i")
        .replace("û", "u")
        .replace("ü", "u")
    )


def _strip_mahkumiyet(talep: str) -> str:
    chunks = [part.strip() for part in re.split(r"(?<=\.)\s+", str(talep or "").strip()) if part.strip()]
    kept = [part for part in chunks if "mahkumiyet" not in _fold_tr(part)]
    return " ".join(kept).strip() or DEFAULT_SIKAYET_TALEP


def _finalize_belge_facts(
    parsed: dict[str, Any],
    engine: dict[str, Any],
    belge_id: str = "",
) -> dict[str, Any]:
    """Kaynakta olmayan TCK maddesini ve şikayette mahkûmiyet talebini düşür."""
    allowed = _sourced_articles(engine)
    rows = parsed.get("hukuki_nitelendirme")
    if isinstance(rows, list):
        kept = [row for row in rows if not _nitelendirme_unsourced(row, allowed)]
        parsed["hukuki_nitelendirme"] = kept or [{"cumle": NO_MADDE_CUMLE}]
    elif rows and _nitelendirme_unsourced(rows, allowed):
        parsed["hukuki_nitelendirme"] = [{"cumle": NO_MADDE_CUMLE}]
    kind = (belge_id or str(engine.get("action") or "")).strip().lower()
    if kind in {"sikayet", "suc_duyurusu"} and parsed.get("talep"):
        parsed["talep"] = _strip_mahkumiyet(str(parsed.get("talep") or ""))
    return parsed


def extractive_parsed(spec: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    """LLM yokken kalıp örneği + kullanıcı metni; evrak birimini makam diye yazma."""
    if spec.get("family") == "kamu":
        return _extractive_kamu(spec, engine)
    parsed = dict(spec.get("example") or {})
    parsed["makam"] = spec.get("makam") or parsed.get("makam")
    user = str(engine.get("user_text") or "").strip()
    fields = engine.get("fields") or {}
    belge_id = str(spec.get("id") or "")
    narrative_key = NARRATIVE_FIELD.get(belge_id)
    if user and narrative_key:
        parsed[narrative_key] = user[:1200]
    if fields.get("konu"):
        parsed["konu"] = fields["konu"]
    elif not parsed.get("konu"):
        parsed["konu"] = spec.get("title")
    related = engine.get("related") or []
    if "hukuki_nitelendirme" in parsed:
        rows = []
        for hit in related[:3]:
            madde = hit.get("article_no")
            cumle = hit.get("span") or hit.get("title") or ""
            if not cumle:
                continue
            rows.append({"n": hit.get("n"), "madde": madde, "cumle": cumle})
        parsed["hukuki_nitelendirme"] = rows or [{"cumle": NO_MADDE_CUMLE}]
    deadlines = engine.get("deadlines") or []
    for item in deadlines:
        if item.get("last_day") and not parsed.get("sure_cumlesi"):
            parsed["sure_cumlesi"] = f"{item.get('name')}: son gün {item.get('last_day')}."
            break
    parsed["onay_notu"] = "Taslaktır. UYAP’a otomatik gönderim yoktur. vatandas.uyap.gov.tr"
    return _finalize_belge_facts(_apply_islem_gaps(parsed, engine), engine, belge_id)


def compose_belge(
    belge_id: str,
    engine: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
    allow_ollama: bool = True,
) -> tuple[str, dict[str, Any]]:
    spec = load_belge(belge_id)
    parsed = extractive_parsed(spec, engine)
    fn = chat_fn or resolve_writer(allow_ollama=allow_ollama)
    if fn is not None:
        raw = fn(
            [
                {"role": "system", "content": belge_system_prompt(belge_id)},
                {"role": "user", "content": _user_payload(engine)},
            ]
        )
        parsed = _alias_belge_fields(_merge_example(parsed, parse_json_content(raw)))
        parsed = _finalize_belge_facts(_apply_islem_gaps(parsed, engine), engine, belge_id)
        errors = validate_belge(belge_id, parsed)
        if errors:
            raise OllamaError("; ".join(errors))
    return render_belge(spec, parsed), petition_view(spec, parsed)


def write_belge(
    belge_id: str,
    engine: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
    allow_ollama: bool = True,
) -> str | None:
    text, _ = compose_belge(belge_id, engine, chat_fn=chat_fn, allow_ollama=allow_ollama)
    return text


def compose_islem(action: str | None, engine: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    belge_id = ACTION_TO_BELGE.get((action or "").strip().lower())
    if not belge_id:
        text = write_module("islem", engine) or ""
        return text, {"id": "islem", "title": "İşlem", "family": "ceza", "layout": "dilekce", "sections": []}
    try:
        return compose_belge(belge_id, engine)
    except Exception:
        spec = load_belge(belge_id)
        parsed = extractive_parsed(spec, engine)
        return render_belge(spec, parsed), petition_view(spec, parsed)


def write_islem(
    action: str | None,
    engine: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
) -> str | None:
    belge_id = ACTION_TO_BELGE.get((action or "").strip().lower())
    if belge_id:
        return write_belge(belge_id, engine, chat_fn=chat_fn)
    return write_module("islem", engine, chat_fn=chat_fn)
