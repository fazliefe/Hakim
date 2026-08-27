from __future__ import annotations

import re
from typing import Any, Callable

from llm.api_client import api_chat, api_configured
from llm.client import OllamaError, chat, ollama_enabled, parse_json_content, ping
from llm.emsal import emsal_atif_or_drop, is_court_hit, pick_emsal
from llm.formats import load_belge, load_format, validate_belge, validate_parsed
from llm.prompt import LAW_SHORT, belge_messages, module_messages
from llm.render import petition_view, render_arastirma, render_belge, render_evrak, render_islem_module, render_surec

ACTION_TO_BELGE = {
    "istinaf": "istinaf",
    "istinaf_hukuk": "istinaf_hukuk",
    "itiraz": "itiraz",
    "cevap": "cevap",
    "sikayet": "sikayet",
    "suc_duyurusu": "suc_duyurusu",
    "temyiz": "temyiz",
    "temyiz_hukuk": "temyiz_hukuk",
    "katilma": "katilma",
    "bireysel_basvuru": "bireysel_basvuru",
    "idari_dava": "idari_dava",
    "tahliye": "tahliye",
    "adli_kontrol_itiraz": "adli_kontrol_itiraz",
    "temyiz_cevap": "temyiz_cevap",
    "sure_uzatim": "sure_uzatim",
    "icra_borca_itiraz": "icra_borca_itiraz",
    "ihtiyac_tahliye": "ihtiyac_tahliye",
    "ust_yazi": "ust_yazi",
    "bilgi_yazisi": "bilgi_yazisi",
    "olur": "olur",
    "cevap_yazisi": "cevap_yazisi",
}

ChatFn = Callable[..., str]

SPAN_CHARS = 280
EVIDENCE_SPAN_CHARS = 720
USER_TEXT_CHARS = 800
RELATED_HITS = 5
EVIDENCE_HITS = 6
MAX_VISUAL_EKS = 4
VISUAL_EK_CUMLE_ONE = "Olaydaki görsel ekte sunulmuştur."
VISUAL_EK_CUMLE_MANY = "Olaydaki görseller ekte sunulmuştur."


def _span(text: Any, limit: int = SPAN_CHARS) -> str:
    return " ".join(str(text or "").split())[:limit]


def normalize_visual_eks(raw: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        caption = _span(item.get("caption"), 160)
        scene = _span(item.get("scene"), 400)
        if not caption:
            continue
        rows.append({"caption": caption, "scene": scene})
        if len(rows) >= MAX_VISUAL_EKS:
            break
    return rows


def compact_engine(engine: dict[str, Any]) -> dict[str, Any]:
    """Groq/Ollama'ya tam madde dump'ı gitmesin: künye + kısa span.

    Serbest metin alanları (user_text, query) dış LLM'e gitmeden önce PII
    (TCKN/IBAN/e-posta/telefon) maskelenir. `fields` buna dahil değildir:
    oradaki ad/TCKN/adres, dilekçenin işlevsel içeriğidir, tesadüfi değil.
    """
    from document_ai.privacy.pii_detector import redact_text

    classification = engine.get("classification") or {}
    related = []
    for hit in (engine.get("related") or [])[:RELATED_HITS]:
        row = {
            "n": hit.get("n"),
            "title": hit.get("title"),
            "article_no": hit.get("article_no"),
            "law_no": hit.get("law_no"),
            "span": _span(hit.get("content") or hit.get("span")),
        }
        if hit.get("document_type"):
            row["document_type"] = hit.get("document_type")
        if hit.get("court"):
            row["court"] = hit.get("court")
        related.append(row)
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
    compact = {
        "action": engine.get("action"),
        "user_text": _span(redact_text(str(engine.get("user_text") or "")), USER_TEXT_CHARS),
        "query": _span(redact_text(str(engine.get("query") or "")), 240) or None,
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
        "emsal": pick_emsal(engine, action=str(engine.get("action") or "")),
        "gaps": engine.get("gaps") or [],
    }
    visual_eks = normalize_visual_eks(engine.get("visual_eks"))
    if visual_eks:
        compact["visual_eks"] = visual_eks
    return compact


def _messages(module_or_belge: str, engine: dict[str, Any], *, belge: bool = False) -> list[dict[str, str]]:
    compact = compact_engine(engine)
    if belge:
        return belge_messages(module_or_belge, compact)
    return module_messages(module_or_belge, compact)


def _correction_messages(
    base_messages: list[dict[str, str]], raw: str, errors: list[str]
) -> list[dict[str, str]]:
    """Şema doğrulama hatası sonrası TEK seferlik düzeltme turu için sohbeti
    uzatır — modelin kendi hatalı cevabını görüp aynı kaynaklara dayanarak
    düzeltmesini ister. Hâlâ geçmezse çağıran taraf extractive fallback'e
    düşer (bkz. main.py::_analyze except bloğu); burada ikinci bir retry
    yok, maliyet/gecikmeyi sınırlı tutmak için tek tur yeterli kabul edildi."""
    return base_messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                "Önceki cevap şemaya uymuyor: "
                + "; ".join(errors)
                + ". Yeni kaynak veya alan uydurma; yalnızca aynı kaynaklara dayanarak "
                "düzeltilmiş JSON'u döndür. Açıklama, markdown veya kod çiti ekleme."
            ),
        },
    ]


def _attempt_json(
    fn: ChatFn,
    messages: list[dict[str, str]],
    *,
    build: Callable[[dict[str, Any]], dict[str, Any]],
    validate: Callable[[dict[str, Any]], list[str]],
) -> tuple[dict[str, Any] | None, str, list[str]]:
    """Tek bir sohbet turu: modeli çağır, JSON ayrıştır, `build` ile son
    hâline getir, `validate` ile şema kontrolü yap. JSON hiç ayrıştırılamazsa
    (`parse_json_content` OllamaError fırlatırsa) da aynı "errors" sözleşmesine
    döner — çağıran taraf hem parse hem şema hatasını aynı tek-retry yoluyla
    (bkz. `_correction_messages`) ele alabilsin diye."""
    raw = fn(messages)
    try:
        payload = build(parse_json_content(raw))
    except OllamaError as exc:
        return None, raw, [str(exc)]
    return payload, raw, validate(payload)


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
    if stage in {"kovusturma", "ilk_derece"}:
        asama += " İstinaf yolu açıktır; dosya henüz istinaf mahkemesinde değildir."
    # remedies (classify.py::classify_document) artık nitelik-bazlı ayrı
    # etiketler taşıyor (istinaf_ceza/istinaf_hukuk, temyiz_ceza/temyiz_hukuk)
    # — bu harita eskisi gibi düz "istinaf"/"temyiz" bekleseydi, eşleşmeyen
    # anahtar ham kod olarak ("istinaf_ceza bu hüküm için işletilebilir.")
    # üretilen anlatıya sızardı.
    labels = {
        "itiraz": "İtiraz",
        "istinaf": "İstinaf",
        "istinaf_ceza": "İstinaf",
        "istinaf_hukuk": "İstinaf",
        "istinaf_idari": "İdari istinaf",
        "temyiz": "Temyiz",
        "temyiz_ceza": "Temyiz",
        "temyiz_hukuk": "Temyiz",
        "bireysel_basvuru": "Bireysel başvuru",
        "sikayet": "Şikayet",
        "idari_dava": "İdari dava açma",
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
                raw = fn(_messages(module_id, engine))
                asama = str(parse_json_content(raw).get("asama_cumlesi") or "").strip()
                if asama:
                    parsed["asama_cumlesi"] = asama
            except Exception:
                pass
        return render_surec(parsed)
    if fn is None:
        return None
    spec = load_format(module_id)
    example = spec.get("example") or {}
    base_messages = _messages(module_id, engine)

    def build(payload: dict[str, Any]) -> dict[str, Any]:
        return _merge_example(example, payload)

    def validate(payload: dict[str, Any]) -> list[str]:
        return validate_parsed(module_id, payload)

    parsed, raw, errors = _attempt_json(fn, base_messages, build=build, validate=validate)
    if errors:
        parsed, raw, errors = _attempt_json(
            fn, _correction_messages(base_messages, raw, errors), build=build, validate=validate
        )
        if errors:
            raise OllamaError("; ".join(errors))
    if module_id == "arastirma":
        return render_arastirma(parsed)
    if module_id == "evrak":
        return render_evrak(parsed)
    return render_islem_module(parsed)


# Olay/savunma gövdesi — künye satırına (hüküm, karar no) ham konuşma yapıştırılmaz.
STORY_FIELD = {
    "sikayet": "olay",
    "suc_duyurusu": "olay",
    "cevap": "esasa_cevap",
    "itiraz": "sebepler",
    "istinaf": "sebepler",
    "temyiz": "sebepler",
    "katilma": "zarar",
    "bireysel_basvuru": "olay",
    "idari_dava": "sebepler",
    "tahliye": "sebepler",
    "adli_kontrol_itiraz": "sebepler",
    "temyiz_cevap": "aciklamalar",
    "sure_uzatim": "aciklamalar",
    "icra_borca_itiraz": "sebepler",
    "ihtiyac_tahliye": "aciklamalar",
    "ust_yazi": "metin",
    "bilgi_yazisi": "metin",
    "olur": "metin",
    "cevap_yazisi": "metin",
}

META_FIELDS = {
    "istinaf": ("hukum",),
    "itiraz": ("itiraz_olunan", "karar"),
    "temyiz": ("karar",),
    "tahliye": ("tutuklama",),
    "idari_dava": ("islem",),
    "adli_kontrol_itiraz": ("karar",),
    "katilma": ("dava",),
}

OFFENCE_BELGE = {"sikayet", "suc_duyurusu"}
USUL_BELGE = {"temyiz", "istinaf", "itiraz", "adli_kontrol_itiraz"}
HUKUK_BELGE = {"temyiz_cevap", "sure_uzatim", "icra_borca_itiraz", "ihtiyac_tahliye"}
_INFORMAL_RE = re.compile(
    r"\b(beni|bana|benim|istiyorum|gitmek|mahkum etti|hapisteyim|"
    r"cezaevindeyim|parami|paramı|aldılar|aldirlar)\b",
    re.IGNORECASE,
)
_PROC_CITE_RE = re.compile(r"\b(CMK|İYUK|IYUK|2577|6216|Anayasa|İİK|IIK|Tebligat)\b", re.IGNORECASE)
_TCK_CITE_RE = re.compile(r"\bTCK\s*m\.\s*\d+", re.IGNORECASE)


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
STORY_LINE = {
    "istinaf": "İlk derece mahkemesince kurulan hükmün hukuka aykırılığı nedeniyle istinaf yoluna başvurulmaktadır.",
    "itiraz": "Kararın usul ve yasaya aykırılığı nedeniyle itiraz yoluna başvurulmaktadır.",
    "temyiz": "Kararın hukuka aykırılığı nedeniyle temyiz yoluna başvurulmaktadır.",
    "tahliye": "Tutuklama nedenlerinin ortadan kalktığı, tahliyenin ölçülü olacağı beyan olunur.",
    "adli_kontrol_itiraz": "Koruma tedbirinin ölçüsüz olduğu, kararın kaldırılması gerektiği beyan olunur.",
    "idari_dava": "Dava konusu işlemin hukuka aykırı olduğu ileri sürülmektedir.",
    "ihtiyac_tahliye": "Kiralananın malik ihtiyacı nedeniyle tahliyesinin gerektiği beyan olunur.",
    "sure_uzatim": "Dosyanın incelenmesi ve hakların korunması için sürenin uzatılması talep olunur.",
    "icra_borca_itiraz": "Takibe konu borcun mevcut olmadığı, borcun tamamına, faize ve fer’ilerine itiraz edildiği beyan olunur.",
    "temyiz_cevap": "Temyiz başvurusuna ilişkin olarak mahkeme kararının yerinde ve hukuka uygun olduğu beyan olunur.",
}
KARSIT_TEMYIZ_LINE = (
    "Temyiz dilekçesinde ileri sürülen iddiaların reddi ile birlikte, "
    "usule aykırı görülen kısımlar yönünden karşı temyiz yoluna başvurulduğu beyan olunur."
)
KARSIT_TEMYIZ_TALEP = (
    "Temyiz başvurusunun reddine; usule aykırı görülen kısımlar yönünden karşı temyiz "
    "talebinin kabulüne; yargılama giderleri ve vekâlet ücretinin karşı tarafa yüklenmesine "
    "karar verilmesi talep olunur."
)
PARTY_FROM_NAME = {
    "temyiz": "temyiz_eden",
    "temyiz_cevap": "cevap_veren",
    "icra_borca_itiraz": "borclu",
    "ihtiyac_tahliye": "davaci",
    "sure_uzatim": "davali",
}


def _sourced_articles(engine: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for hit in list(engine.get("related") or []) + list(engine.get("evidence") or []):
        if is_court_hit(hit):
            continue
        no = str(hit.get("article_no") or "").strip()
        if not no or re.fullmatch(r"\d{4}/\d+", no):
            continue
        out.add(no)
        out.add(no.split("/")[0])
    return out


def _madde_ok(token: str, allowed: set[str]) -> bool:
    raw = token.strip()
    if not raw:
        return True
    return raw in allowed or raw.split("/")[0] in allowed


def _nitelendirme_blob(row: Any) -> str:
    if isinstance(row, dict):
        return f"{row.get('madde') or ''} {row.get('cumle') or ''} {row.get('kanun') or ''}"
    return str(row or "")


def _is_system_note(text: str) -> bool:
    raw = str(text or "").lower()
    folded = _fold_tr(text)
    blob = f"{raw} {folded}"
    return any(
        marker in blob
        for marker in (
            "eşleşen madde yok",
            "eslesen madde yok",
            "yazılmadı",
            "yazilmadi",
            "taslaga tck",
            "sistem not",
        )
    )


def _nitelendirme_unsourced(row: Any, allowed: set[str]) -> bool:
    """Kaynaksız TCK suç maddesini düşür; CMK/İYUK usul cümlelerini bırak."""
    blob = _nitelendirme_blob(row)
    if _is_system_note(blob):
        return True
    if isinstance(row, dict):
        madde = str(row.get("madde") or "").strip()
    else:
        madde = ""
    cited = [m.group(1) for m in _ARTICLE_RE.finditer(blob)]
    if madde:
        cited.append(madde)
    if not cited:
        return False
    procedural = bool(_PROC_CITE_RE.search(blob))
    tck = bool(_TCK_CITE_RE.search(blob)) or (bool(madde) and not procedural)
    if not allowed:
        return tck or not procedural
    bad = [token for token in cited if not _madde_ok(token, allowed)]
    if not bad:
        return False
    if procedural and not tck:
        return False
    return True


def _fold_tr(text: str) -> str:
    return (
        str(text or "")
        .lower()
        .replace("ı", "i")
        .replace("î", "i")
        .replace("û", "u")
        .replace("ü", "u")
    )


def _norm_line(text: str) -> str:
    return re.sub(r"\s+", " ", _fold_tr(text)).strip(" .,:;")


def _looks_like_raw_user(value: str, user: str) -> bool:
    a, b = _norm_line(value), _norm_line(user)
    if not a or not b or len(b) < 8:
        return False
    if a == b or b in a or a in b:
        return True
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.7


def _informal_meta(value: str) -> bool:
    return bool(_INFORMAL_RE.search(value or ""))


def _ascii_tr(text: str) -> str:
    return (
        _fold_tr(text)
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def _wants_karsi_temyiz(user: str) -> bool:
    return "karsi temyiz" in _ascii_tr(user)


def _wants_imza_itiraz(user: str) -> bool:
    folded = _ascii_tr(user)
    return "imzaya itiraz" in folded or "imza itiraz" in folded or "imzam degil" in folded


def _overlaps_story(item: str, sentence: str) -> bool:
    if not sentence:
        return False
    a, b = _norm_line(item), _norm_line(sentence)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    wa, wb = set(a.split()), set(b.split())
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.55


def _story_sentence(belge_id: str, user: str) -> str:
    folded = _fold_tr(user)
    if belge_id == "istinaf" and ("mahkum" in folded or "hukum" in folded):
        return (
            "İlk derece mahkemesince kurulan mahkûmiyet hükmünün hukuka aykırı olduğu "
            "ileri sürülmektedir."
        )
    if belge_id == "tahliye" and ("tutuk" in folded or "cezaev" in folded or "hapis" in folded):
        return "Yürürlükteki tutuklama tedbirinin ölçüsüz kaldığı, tahliyenin yerinde olacağı beyan olunur."
    if belge_id == "temyiz_cevap" and _wants_karsi_temyiz(user):
        return KARSIT_TEMYIZ_LINE
    return STORY_LINE.get(belge_id, "")


def _as_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _formal_sebepler(belge_id: str, user: str, existing: Any) -> list[str]:
    sentence = _story_sentence(belge_id, user)
    out: list[str] = []
    if sentence:
        out.append(sentence)
    for item in _as_lines(existing):
        if _looks_like_raw_user(item, user) or _informal_meta(item):
            continue
        if _overlaps_story(item, sentence):
            continue
        out.append(item)
    return out or _as_lines(existing)


def _usul_nitelendirme(spec: dict[str, Any]) -> list[dict[str, str]]:
    belge_id = str(spec.get("id") or "")
    if belge_id in OFFENCE_BELGE:
        return []
    basis = [str(item).strip() for item in (spec.get("legal_basis") or []) if str(item).strip()]
    if not basis:
        return []
    return [{"cumle": f"Başvuru {', '.join(basis)} hükümlerine tabidir."}]


def _related_nitelendirme(engine: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hit in (engine.get("related") or [])[:3]:
        if is_court_hit(hit):
            continue
        madde = str(hit.get("article_no") or "").strip()
        if re.fullmatch(r"\d{4}/\d+", madde):
            continue
        kanun = LAW_SHORT.get(str(hit.get("law_no") or "").strip())
        if not kanun:
            continue
        cumle = hit.get("span") or hit.get("title") or ""
        if not cumle:
            continue
        rows.append(
            {
                "n": hit.get("n"),
                "madde": madde,
                "kanun": kanun,
                "cumle": cumle,
            }
        )
    return rows


def _strip_mahkumiyet(talep: str) -> str:
    chunks = [part.strip() for part in re.split(r"(?<=\.)\s+", str(talep or "").strip()) if part.strip()]
    kept = [part for part in chunks if "mahkumiyet" not in _fold_tr(part)]
    return " ".join(kept).strip() or DEFAULT_SIKAYET_TALEP


def _sanitize_meta_fields(
    parsed: dict[str, Any],
    spec: dict[str, Any],
    engine: dict[str, Any],
) -> dict[str, Any]:
    """Hüküm/karar künyesine ham kullanıcı cümlesi ve sistem notu yapıştırma."""
    user = str(engine.get("user_text") or "").strip()
    belge_id = str(spec.get("id") or engine.get("action") or "")
    example = spec.get("example") or {}
    for key in META_FIELDS.get(belge_id, ()):
        value = str(parsed.get(key) or "")
        if not value:
            continue
        if _looks_like_raw_user(value, user) or _informal_meta(value) or _is_system_note(value):
            parsed[key] = example.get(key) or value
    story_key = STORY_FIELD.get(belge_id)
    if story_key in {"sebepler", "aciklamalar"}:
        existing = parsed.get(story_key)
        lines = _formal_sebepler(belge_id, user, existing)
        parsed[story_key] = lines if isinstance(existing, list) else " ".join(lines)
    return parsed


_EMSAL_LIE_RE = re.compile(r"bu yönde değerlendirme|aynı emsale dayanır", re.I)
_TEBLIG_STAMP_RE = re.compile(
    r"tebli[gğ]\s*tarihi\s*:\s*(\d{1,2}[./]\d{1,2}[./]\d{4})",
    re.I,
)


def _teblig_stamp(engine: dict[str, Any]) -> str:
    dates = engine.get("dates") or {}
    fields = engine.get("fields") or {}
    raw = dates.get("teblig") or fields.get("teblig")
    if raw is not None and str(raw).strip():
        return _tr_day(raw)
    from document_ai.gaps import labeled_facts

    labeled = str(labeled_facts(str(engine.get("user_text") or "")).get("teblig") or "").strip()
    if labeled:
        return labeled
    found = _TEBLIG_STAMP_RE.search(str(engine.get("user_text") or ""))
    if not found:
        return ""
    return found.group(1).replace("/", ".")


def _apply_teblig_date(parsed: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    stamp = _teblig_stamp(engine)
    if not stamp:
        return parsed
    current = str(parsed.get("sure_cumlesi") or "").strip()
    extra = f"Tebliğ tarihi: {stamp}."
    if stamp in current:
        return parsed
    if re.search(r"tebliğ tarihi:\s*«\[", current, re.I):
        parsed["sure_cumlesi"] = re.sub(
            r"Tebliğ tarihi:\s*«\[[^\]]+\]»\.?", extra, current, count=1, flags=re.I
        )
        return parsed
    parsed["sure_cumlesi"] = f"{current} {extra}".strip() if current else extra
    return parsed


def _apply_last_day(parsed: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    """Katalogdaki süre kuralı durur; takvim günü yalnızca motor last_day ise basılır."""
    last = None
    for item in engine.get("deadlines") or []:
        if item.get("last_day"):
            last = item.get("last_day")
            break
    if last is None:
        return parsed
    stamp = _tr_day(last)
    if not stamp:
        return parsed
    current = str(parsed.get("sure_cumlesi") or "").strip()
    extra = f"Son gün: {stamp}."
    if stamp in current:
        return parsed
    parsed["sure_cumlesi"] = f"{current} {extra}".strip() if current else extra
    return parsed


def _apply_emsal(parsed: dict[str, Any], engine: dict[str, Any], belge_id: str = "") -> dict[str, Any]:
    """Canlı künyeyi yaz; listede olmayan esas/kararı düşür. Uyum yoksa yalan söyleme."""
    from llm.emsal import honesty_line

    emsal = pick_emsal(engine, action=belge_id or str(engine.get("action") or ""))
    parsed["emsal_atif"] = emsal_atif_or_drop(parsed.get("emsal_atif"), emsal)
    atif = str(parsed.get("emsal_atif") or "").strip()
    sebepler = parsed.get("sebepler")
    if isinstance(sebepler, list):
        parsed["sebepler"] = [item for item in sebepler if not _EMSAL_LIE_RE.search(str(item))]
        sebepler = parsed["sebepler"]
    if not atif:
        return parsed
    matched = next((item for item in emsal if atif in str(item.get("atif") or "")), emsal[0] if emsal else {})
    line = str(matched.get("cumle") or "").strip() or honesty_line(atif, bool(matched.get("uyum")))
    if isinstance(sebepler, list) and not any(atif in str(item) for item in sebepler):
        parsed["sebepler"] = list(sebepler) + [line]
    return parsed


def _mentions_annex(text: str) -> bool:
    folded = _fold_tr(text)
    return any(token in folded for token in ("ekte", "eklerde", "ek olarak", "ekler aras"))


def _apply_visual_eks(parsed: dict[str, Any], engine: dict[str, Any], belge_id: str) -> dict[str, Any]:
    visuals = normalize_visual_eks(engine.get("visual_eks"))
    if not visuals:
        return parsed
    items = [item for item in _as_lines(parsed.get("ekler")) if item not in {"—", "-"}]
    for row in visuals:
        caption = row["caption"]
        if not any(caption.lower() in item.lower() or item.lower() in caption.lower() for item in items):
            items.append(caption)
    parsed["ekler"] = items
    mention = VISUAL_EK_CUMLE_MANY if len(visuals) > 1 else VISUAL_EK_CUMLE_ONE
    scene = next((row["scene"] for row in visuals if row.get("scene")), "")
    if scene and not _mentions_annex(scene):
        if not scene.endswith("."):
            scene += "."
        mention = f"{scene} {mention}"
    story_key = STORY_FIELD.get(belge_id)
    if not story_key:
        return parsed
    value = parsed.get(story_key)
    if isinstance(value, list):
        blob = " ".join(str(item) for item in value)
        if not _mentions_annex(blob):
            parsed[story_key] = list(value) + [mention]
    else:
        blob = str(value or "")
        if not _mentions_annex(blob):
            parsed[story_key] = f"{blob.rstrip()} {mention}".strip()
    return parsed


def _finalize_belge_facts(
    parsed: dict[str, Any],
    engine: dict[str, Any],
    belge_id: str = "",
    spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Kaynakta olmayan TCK maddesini ve şikayette mahkûmiyet talebini düşür."""
    kind = (belge_id or str(engine.get("action") or "")).strip().lower()
    catalog = spec if spec and spec.get("id") == kind else None
    if catalog is None and kind:
        try:
            catalog = load_belge(kind)
        except Exception:
            catalog = spec
    if catalog:
        parsed = _sanitize_meta_fields(parsed, catalog, engine)
    allowed = _sourced_articles(engine)
    rows = parsed.get("hukuki_nitelendirme")
    fallback = _usul_nitelendirme(catalog or {"id": kind})
    if isinstance(rows, list):
        kept = [row for row in rows if not _nitelendirme_unsourced(row, allowed)]
        parsed["hukuki_nitelendirme"] = kept or fallback
    elif rows and _nitelendirme_unsourced(rows, allowed):
        parsed["hukuki_nitelendirme"] = fallback
    if kind in USUL_BELGE or kind in HUKUK_BELGE:
        parsed["hukuki_nitelendirme"] = fallback
    if kind in OFFENCE_BELGE and parsed.get("talep"):
        parsed["talep"] = _strip_mahkumiyet(str(parsed.get("talep") or ""))
    parsed = _apply_teblig_date(parsed, engine)
    parsed = _apply_last_day(parsed, engine)
    parsed = _apply_emsal(parsed, engine, kind)
    return _apply_visual_eks(parsed, engine, kind)


def extractive_parsed(spec: dict[str, Any], engine: dict[str, Any]) -> dict[str, Any]:
    """LLM yokken kalıp örneği + resmi gövde; ham konuşmayı künye satırına yazma."""
    if spec.get("family") == "kamu":
        return _extractive_kamu(spec, engine)
    parsed = dict(spec.get("example") or {})
    parsed["makam"] = spec.get("makam") or parsed.get("makam")
    user = str(engine.get("user_text") or "").strip()
    fields = engine.get("fields") or {}
    from document_ai.gaps import labeled_facts

    facts = labeled_facts(user)
    belge_id = str(spec.get("id") or "")
    story_key = STORY_FIELD.get(belge_id)
    if user and belge_id == "temyiz_cevap" and _wants_karsi_temyiz(user):
        parsed["aciklamalar"] = _formal_sebepler(belge_id, user, [])
        parsed["talep"] = KARSIT_TEMYIZ_TALEP
    elif user and story_key in {"sebepler", "aciklamalar"}:
        existing = parsed.get(story_key)
        lines = _formal_sebepler(belge_id, user, existing)
        parsed[story_key] = lines if isinstance(existing, list) else " ".join(lines)
    elif user and story_key:
        parsed[story_key] = user[:1200]
    if belge_id == "icra_borca_itiraz" and _wants_imza_itiraz(user):
        lines = _as_lines(parsed.get("sebepler"))
        if not any("imza" in _ascii_tr(item) for item in lines):
            lines.append(
                "Takibe dayanak belgedeki imzanın borçluya ait olmadığı, "
                "İİK m.62/2 uyarınca imzaya itiraz edildiği beyan olunur."
            )
            parsed["sebepler"] = lines
            parsed["konu"] = (
                "Tebliğ edilen ödeme emrine; borca, imzaya, faize ve yetkiye "
                "itirazların sunulmasıdır."
            )
    name_key = PARTY_FROM_NAME.get(belge_id)
    if name_key and (facts.get("ad_soyad") or fields.get("ad_soyad")):
        parsed[name_key] = facts.get("ad_soyad") or fields["ad_soyad"]
    if fields.get("konu"):
        parsed["konu"] = fields["konu"]
    elif not parsed.get("konu"):
        parsed["konu"] = spec.get("title")
    dates = engine.get("dates") or {}
    if dates.get("olay") or dates.get("olay_tarihi"):
        parsed["suc_tarihi"] = _tr_day(dates.get("olay") or dates.get("olay_tarihi"))
    if dates.get("teblig"):
        parsed["teblig_tarihi"] = _tr_day(dates.get("teblig"))
    if belge_id == "adli_kontrol_itiraz" and not parsed.get("talep_konusu"):
        karar = str(parsed.get("karar") or "adli kontrol kararı").strip()
        parsed["talep_konusu"] = f"{karar} aleyhine itiraz."
    if belge_id == "sikayet" and not parsed.get("konu"):
        parsed["konu"] = "Kamu davası açılması talebidir."
    if facts.get("adres") or fields.get("adres"):
        parsed["adres"] = facts.get("adres") or fields["adres"]
    elif not parsed.get("adres"):
        parsed["adres"] = "«[adres]»"
    if facts.get("sehir") or fields.get("sehir") or fields.get("il"):
        parsed["sehir"] = facts.get("sehir") or fields.get("sehir") or fields.get("il")
    if facts.get("ad_soyad") or fields.get("ad_soyad"):
        parsed["ad_soyad"] = facts.get("ad_soyad") or fields["ad_soyad"]
    if facts.get("sikayetci"):
        parsed["sikayetci"] = facts["sikayetci"]
        parsed["duyuran"] = facts["sikayetci"]
    if facts.get("esas_no"):
        parsed["esas_no"] = facts["esas_no"]
    from datetime import date as _date
    from llm.layouts import _CITY_RE

    if not parsed.get("tarih"):
        today = _date.today()
        parsed["tarih"] = f"{today.day:02d}.{today.month:02d}.{today.year}"
    if not parsed.get("sehir"):
        found = _CITY_RE.search(user)
        if found:
            parsed["sehir"] = found.group(1)
    if "hukuki_nitelendirme" in parsed:
        sourced = _related_nitelendirme(engine) or _usul_nitelendirme(spec)
        if sourced:
            parsed["hukuki_nitelendirme"] = sourced
        elif belge_id == "sikayet":
            parsed["hukuki_nitelendirme"] = [
                {"cumle": "Türk Ceza Kanunu, Ceza Muhakemesi Kanunu ve sair hukuki sebepler."}
            ]
        else:
            parsed["hukuki_nitelendirme"] = []
    parsed["onay_notu"] = "Taslaktır. UYAP’a otomatik gönderim yoktur. vatandas.uyap.gov.tr"
    return _finalize_belge_facts(_apply_islem_gaps(parsed, engine), engine, belge_id, spec)


def _attach_evolver(
    view: dict[str, Any],
    text: str,
    belge_id: str,
    parsed: dict[str, Any],
    engine: dict[str, Any],
) -> dict[str, Any]:
    """Sidecar puanı; prompt/writer yerini almaz. Paket apps/api bağımlılığı değil."""
    import sys
    from pathlib import Path

    sidecar = Path(__file__).resolve().parents[2] / "tools" / "evolver"
    if sidecar.is_dir() and str(sidecar) not in sys.path:
        sys.path.insert(0, str(sidecar))
    try:
        from hakim_evolver.score import score_and_record
    except ImportError:
        return view
    view["evolver"] = score_and_record(
        text,
        belge_id=belge_id,
        parsed=parsed,
        emsal=pick_emsal(engine, action=belge_id),
    )
    return view


def compose_belge(
    belge_id: str,
    engine: dict[str, Any],
    *,
    chat_fn: ChatFn | None = None,
    allow_ollama: bool = True,
) -> tuple[str, dict[str, Any]]:
    spec = load_belge(belge_id)
    extractive = extractive_parsed(spec, engine)
    parsed = extractive
    fn = chat_fn or resolve_writer(allow_ollama=allow_ollama)
    if fn is not None:
        base_messages = _messages(belge_id, engine, belge=True)

        def build(payload: dict[str, Any]) -> dict[str, Any]:
            merged = _alias_belge_fields(_merge_example(extractive, payload))
            return _finalize_belge_facts(_apply_islem_gaps(merged, engine), engine, belge_id, spec)

        def validate(payload: dict[str, Any]) -> list[str]:
            return validate_belge(belge_id, payload)

        candidate, raw, errors = _attempt_json(fn, base_messages, build=build, validate=validate)
        if errors:
            candidate, raw, errors = _attempt_json(
                fn, _correction_messages(base_messages, raw, errors), build=build, validate=validate
            )
            if errors:
                raise OllamaError("; ".join(errors))
        parsed = candidate
    text = render_belge(spec, parsed)
    view = _attach_evolver(petition_view(spec, parsed), text, belge_id, parsed, engine)
    return text, view


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
