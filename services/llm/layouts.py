from __future__ import annotations

import re
from typing import Any

TASLAK_NOTU = "Taslaktır. UYAP’a otomatik gönderim yoktur. vatandas.uyap.gov.tr"

# Her kalıbın kendi evrak düzeni: hitap, kimlik satırları, gövde, kapanış.
LAYOUTS: dict[str, dict[str, Any]] = {
    "sikayet": {
        "layout": "savcilik",
        "subtitle": "ŞİKAYET DİLEKÇESİDİR",
        "meta": (("Şikayetçi", "sikayetci"), ("Şikayet edilen", "sikayet_edilen"), ("Konu", "konu")),
        "body": (
            ("olay", "Açıklamalar", "prose"),
            ("hukuki_nitelendirme", "Hukuki nitelendirme", "cite"),
            ("deliller", "Deliller", "list"),
            ("talep", "Sonuç ve istem", "prose"),
        ),
        "closing": "Arz olunur.",
        "signature": "Şikayetçi",
    },
    "suc_duyurusu": {
        "layout": "ihbar",
        "subtitle": "SUÇ DUYURUSUDUR",
        "meta": (("Duyuran", "duyuran"), ("Konu", "konu")),
        "body": (
            ("olay", "Öğrenilen olay", "prose"),
            ("hukuki_nitelendirme", "Olası hukuki nitelik", "cite"),
            ("deliller", "Bilinen deliller", "list"),
            ("talep", "Talep", "prose"),
        ),
        "closing": "Gereğinin yapılması arz olunur.",
        "signature": "Duyuran",
    },
    "cevap": {
        "layout": "cevap",
        "subtitle": "CEVAP DİLEKÇESİDİR",
        "meta": (("Esas no", "esas_no"), ("Cevap veren", "cevap_veren"), ("Konu", "konu")),
        "body": (
            ("usul", "Usule ilişkin beyanlar", "prose"),
            ("esasa_cevap", "Esasa cevap", "prose"),
            ("hukuki_nitelendirme", "Hukuki değerlendirme", "cite"),
            ("deliller", "Delil bildirimi", "list"),
            ("talep", "Sonuç ve talep", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "Cevap veren",
    },
    "itiraz": {
        "layout": "itiraz",
        "subtitle": "İTİRAZ DİLEKÇESİDİR",
        "meta": (("İtiraz olunan karar", "itiraz_olunan"), ("Esas / karar no", "esas_no"), ("Süre (CMK m.268)", "sure_cumlesi")),
        "body": (
            ("sebepler", "İtiraz sebepleri", "numbered"),
            ("hukuki_nitelendirme", "Hukuki dayanak", "cite"),
            ("talep", "Sonuç ve talep", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "İtiraz eden",
    },
    "adli_kontrol_itiraz": {
        "layout": "itiraz",
        "subtitle": "ADLİ KONTROL / TUTUKLAMA İTİRAZIDIR",
        "meta": (("İtiraz olunan karar", "karar"), ("Esas / karar no", "esas_no"), ("Süre (CMK m.268)", "sure_cumlesi")),
        "body": (
            ("sebepler", "İtiraz sebepleri", "numbered"),
            ("talep", "Sonuç ve talep", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "İtiraz eden",
    },
    "istinaf": {
        "layout": "istinaf",
        "via": "İlgili ilk derece mahkemesi aracılığıyla",
        "subtitle": "İSTİNAF DİLEKÇESİDİR",
        "meta": (("İstinaf olunan hüküm", "hukum"), ("Esas / karar no", "esas_no"), ("Süre (CMK m.273)", "sure_cumlesi")),
        "body": (
            ("sebepler", "İstinaf sebepleri", "numbered"),
            ("hukuki_nitelendirme", "Hukuki dayanak", "cite"),
            ("talep", "Sonuç", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "İstinaf eden",
    },
    "temyiz": {
        "layout": "temyiz",
        "via": "Bölge Adliye Mahkemesi aracılığıyla",
        "subtitle": "TEMYİZ DİLEKÇESİDİR",
        "meta": (("Temyiz olunan karar", "karar"), ("Esas / karar no", "esas_no"), ("Süre (CMK m.291)", "sure_cumlesi")),
        "body": (
            ("sebepler", "Temyiz sebepleri", "numbered"),
            ("hukuki_nitelendirme", "Hukuki dayanak", "cite"),
            ("talep", "Bozma talebi", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "Temyiz eden",
    },
    "katilma": {
        "layout": "katilma",
        "subtitle": "KATILMA TALEBİDİR",
        "meta": (("Esas no", "esas_no"), ("Katılma talep eden", "katilan")),
        "body": (
            ("dava", "Katılınan dava", "prose"),
            ("zarar", "Suçtan zarar görme", "prose"),
            ("hukuki_nitelendirme", "Hukuki dayanak", "cite"),
            ("talep", "Talep", "prose"),
        ),
        "closing": "Arz olunur.",
        "signature": "Katılma talep eden",
    },
    "tahliye": {
        "layout": "tahliye",
        "subtitle": "TAHLİYE TALEBİDİR",
        "meta": (("Esas no", "esas_no"), ("Talep eden", "talep_eden"), ("Tutuklama kararı", "tutuklama")),
        "body": (
            ("sebepler", "Tahliye sebepleri", "numbered"),
            ("adli_kontrol", "Adli kontrol teklifi", "prose"),
            ("talep", "Talep", "prose"),
        ),
        "closing": "Arz ederim.",
        "signature": "Talep eden",
    },
    "bireysel_basvuru": {
        "layout": "aym",
        "subtitle": "BİREYSEL BAŞVURU",
        "meta": (("Başvurucu", "basvurucu"),),
        "body": (
            ("tuketilen_yollar", "I. Tüketilen kanun yolları", "list"),
            ("ihlal", "II. İhlal iddiası", "prose"),
            ("olay", "III. Olaylar", "prose"),
            ("sure_cumlesi", "IV. Süre (6216 s.K. m.47)", "prose"),
            ("talep", "V. Talepler", "prose"),
        ),
        "closing": "Saygılarımla arz olunur.",
        "signature": "Başvurucu",
    },
    "idari_dava": {
        "layout": "idari",
        "subtitle": "DAVA DİLEKÇESİDİR",
        "meta": (("Davacı", "davaci"), ("Davalı idare", "davali"), ("Dava konusu", "islem")),
        "body": (
            ("sure_cumlesi", "Dava açma süresi (İYUK m.7)", "prose"),
            ("sebepler", "Hukuka aykırılık sebepleri", "numbered"),
            ("talep", "Sonuç ve istem", "prose"),
        ),
        "closing": "Arz olunur.",
        "signature": "Davacı",
    },
}

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "sure_cumlesi": ("sure",),
    "itiraz_olunan": ("karar",),
    "cevap_veren": ("taraflar",),
    "sebepler": ("hukuki_sebepler",),
    "hukum": ("karar",),
}


def tr_upper(text: str) -> str:
    return str(text or "").replace("i", "İ").replace("ı", "I").upper()


def hitap(makam: str) -> str:
    """Resmî dilekçe hitabı: T.C. satırındaki makam, -na/-ne ekli, bağıran büyük harf yok."""
    return hitap_official(makam)


def hitap_official(makam: str) -> str:
    text = " ".join(str(makam or "").split())
    if not text:
        return "İlgili makama"
    folded = text.replace("I", "ı").replace("İ", "i").casefold()
    if folded.endswith(("na", "ne", "'na", "'ne", "’na", "’ne")):
        return text
    last_vowel = ""
    for ch in reversed(text):
        if ch in "aıouAIOUâÂ":
            last_vowel = "back"
            break
        if ch in "eiöüEIÖÜîÎ":
            last_vowel = "front"
            break
    suffix = "ne" if last_vowel == "front" else "na"
    return text + suffix


def belge_layout(spec: dict[str, Any]) -> str:
    if spec.get("family") == "kamu":
        return "resmi"
    cfg = LAYOUTS.get(str(spec.get("id") or ""))
    if cfg:
        return str(cfg["layout"])
    return "dilekce"


def _get(parsed: dict[str, Any], key: str) -> Any:
    value = parsed.get(key)
    if value not in (None, "", []):
        return value
    for alias in FIELD_ALIASES.get(key, ()):
        value = parsed.get(alias)
        if value not in (None, "", []):
            return value
    return None


def _cite_line(item: dict[str, Any]) -> str:
    cumle = str(item.get("cumle") or item.get("metin") or "").strip()
    madde = str(item.get("madde") or "").strip()
    kanun = str(item.get("kanun") or item.get("law") or "").strip()
    n = item.get("n")
    parts: list[str] = []
    already = bool(madde and re.search(rf"\bm\.\s*{re.escape(madde)}\b", cumle, re.IGNORECASE))
    if madde and not already:
        if kanun:
            parts.append(f"{kanun} m.{madde}")
        elif re.search(r"\b(CMK|İYUK|IYUK|TCK|TMK|TBK|Anayasa)\b", cumle):
            pass
        else:
            parts.append(f"TCK m.{madde}")
    if cumle:
        parts.append(cumle)
    text = " — ".join(parts)
    if n not in (None, "") and text:
        text = f"{text} [{n}]"
    return text.strip()


def _format_value(value: Any, kind: str) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, list):
        lines: list[str] = []
        for idx, item in enumerate(value, start=1):
            if isinstance(item, dict):
                line = _cite_line(item)
            else:
                line = str(item).strip()
            if not line:
                continue
            if kind == "numbered":
                lines.append(f"{idx}) {line}")
            elif kind == "cite":
                lines.append(line)
            else:
                lines.append(f"• {line}")
        return "\n".join(lines)
    if isinstance(value, dict):
        return _cite_line(value)
    return str(value).strip()


def _meta_rows(cfg: dict[str, Any], spec: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, key in cfg.get("meta") or ():
        value = _get(parsed, key)
        if key == "konu" and value in (None, ""):
            value = parsed.get("konu") or spec.get("title")
        if value in (None, "", [], "—"):
            continue
        rows.append({"label": label, "value": " ".join(str(value).split())})
    return rows


CLASSIC_CLOSING = "Gereğini arz ederim."
SHEET_WIDTH = 64
ADRES_PLACEHOLDER = "«[adres]»"
NAME_PLACEHOLDER = "«[ad soyad]»"
CITY_PLACEHOLDER = "«[il]»"

_CITY_RE = re.compile(
    r"\b(Adana|Ankara|Antalya|Bursa|Gaziantep|İstanbul|Istanbul|İzmir|Izmir|Konya|Mersin)\b",
    re.IGNORECASE,
)
_SIGNER_KEYS = (
    "ad_soyad",
    "imza_ad",
    "sikayetci",
    "duyuran",
    "cevap_veren",
    "katilan",
    "talep_eden",
    "davaci",
    "basvurucu",
)
_GENERIC_NAMES = {
    "şikayetçi",
    "duyuran",
    "sanık / müdafi",
    "cevap veren",
    "suçtan zarar gören",
    "davacı",
    "başvurucu",
    "talep eden",
    "istinaf eden",
    "itiraz eden",
    "katılma talep eden",
}
_DEFAULT_EKLER = {
    "istinaf": ["Gerekçeli karar fotokopisi"],
    "temyiz": ["Bölge adliye mahkemesi kararı fotokopisi"],
    "itiraz": ["İtiraz olunan karar fotokopisi"],
    "adli_kontrol_itiraz": ["Tedbir kararı fotokopisi"],
    "tahliye": ["Tutuklama müzekkeresi fotokopisi"],
    "idari_dava": ["Dava konusu işlemin örneği"],
    "bireysel_basvuru": ["Nihai karar örneği"],
    "katilma": ["İddianame / esas belgesi fotokopisi"],
    "cevap": ["İddianame fotokopisi"],
}
_EKLER_SKIP_KEYS = {"deliller"}


def _sheet_date(parsed: dict[str, Any]) -> str:
    raw = str(parsed.get("tarih") or "").strip()
    match = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", raw)
    if match:
        return f"{int(match.group(1)):02d}.{int(match.group(2)):02d}.{match.group(3)}"
    from datetime import date

    today = date.today()
    return f"{today.day:02d}.{today.month:02d}.{today.year}"


def _sheet_city(parsed: dict[str, Any]) -> str:
    raw = str(parsed.get("sehir") or parsed.get("il") or "").strip()
    if raw and raw not in {"—", "-"}:
        return raw if raw.startswith("«") else _city_title(raw)
    blob = " ".join(
        str(parsed.get(key) or "")
        for key in ("olay", "hukum", "karar", "makam", "adres", "islem")
    )
    found = _CITY_RE.search(blob)
    if found:
        return _city_title(found.group(1))
    return CITY_PLACEHOLDER


def _city_title(raw: str) -> str:
    key = raw.replace("I", "ı").replace("İ", "i").casefold()
    names = {
        "adana": "Adana",
        "ankara": "Ankara",
        "antalya": "Antalya",
        "bursa": "Bursa",
        "gaziantep": "Gaziantep",
        "istanbul": "İstanbul",
        "izmir": "İzmir",
        "konya": "Konya",
        "mersin": "Mersin",
    }
    return names.get(key, raw.strip())


def _signer_name(parsed: dict[str, Any]) -> str:
    for key in _SIGNER_KEYS:
        value = str(parsed.get(key) or "").strip()
        if not value or value in {"—", "-"}:
            continue
        if value.lower() in _GENERIC_NAMES:
            continue
        return _official_name(value)
    return NAME_PLACEHOLDER


def _official_name(name: str) -> str:
    if name.startswith("«"):
        return name
    parts = name.split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]) + " " + tr_upper(parts[-1])
    return name


def _sheet_adres(parsed: dict[str, Any]) -> str:
    value = str(parsed.get("adres") or "").strip()
    if value and value not in {"—", "-", "...", "…"}:
        return value
    return ADRES_PLACEHOLDER


def _collect_ekler(belge_id: str, parsed: dict[str, Any]) -> list[str]:
    raw = parsed.get("ekler")
    if isinstance(raw, list):
        items = [str(item).strip() for item in raw if str(item).strip()]
        if items:
            return items
    if isinstance(raw, str) and raw.strip() and raw.strip() not in {"—", "-"}:
        return [raw.strip()]
    deliller = parsed.get("deliller")
    if isinstance(deliller, list):
        items = [str(item).strip() for item in deliller if str(item).strip()]
        if items:
            return items
    return list(_DEFAULT_EKLER.get(belge_id) or ["—"])


def _lead_paragraph(belge_id: str, parsed: dict[str, Any]) -> str:
    esas = str(_get(parsed, "esas_no") or "").strip()
    esas_bit = f" ({esas})" if esas and esas not in {"—", "-"} else ""
    sure = str(_get(parsed, "sure_cumlesi") or "").strip()
    if belge_id == "istinaf":
        hukum = str(_get(parsed, "hukum") or "").strip()
        head = f"{hukum}{esas_bit} aleyhine istinaf yoluna başvurulmaktadır." if hukum else ""
        return " ".join(part for part in (head, sure) if part)
    if belge_id in {"itiraz", "adli_kontrol_itiraz"}:
        karar = str(_get(parsed, "itiraz_olunan") or _get(parsed, "karar") or "").strip()
        head = f"{karar}{esas_bit} aleyhine itiraz yoluna başvurulmaktadır." if karar else ""
        return " ".join(part for part in (head, sure) if part)
    if belge_id == "temyiz":
        karar = str(_get(parsed, "karar") or "").strip()
        head = f"{karar}{esas_bit} aleyhine temyiz yoluna başvurulmaktadır." if karar else ""
        return " ".join(part for part in (head, sure) if part)
    if belge_id == "tahliye":
        tutuklama = str(_get(parsed, "tutuklama") or "").strip()
        head = f"{tutuklama}{esas_bit} hakkında tahliye talebinde bulunulmaktadır." if tutuklama else ""
        return head
    if belge_id == "idari_dava":
        islem = str(_get(parsed, "islem") or "").strip()
        head = f"{islem} aleyhine iptal davası açılmaktadır." if islem else ""
        return " ".join(part for part in (head, sure) if part)
    if belge_id == "sikayet":
        kim = str(parsed.get("sikayet_edilen") or "").strip()
        if kim and kim.lower() not in {"kimliği belirsiz şüpheli"}:
            return f"{kim} hakkında şikayette bulunulmaktadır."
    return ""


def _body_paragraphs(cfg: dict[str, Any], parsed: dict[str, Any], belge_id: str) -> list[str]:
    paragraphs: list[str] = []
    lead = _lead_paragraph(belge_id, parsed)
    if lead:
        paragraphs.append(lead)
    for key, _label, kind in cfg.get("body") or ():
        if key in _EKLER_SKIP_KEYS:
            continue
        text = _format_value(_get(parsed, key), kind)
        if not text:
            continue
        if lead and _fold_simple(text) in _fold_simple(lead):
            continue
        paragraphs.append(text)
    return paragraphs


def _fold_simple(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _center(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if len(raw) >= SHEET_WIDTH:
        return raw
    return raw.center(SHEET_WIDTH).rstrip()


def _right(text: str) -> str:
    raw = str(text or "").strip()
    if len(raw) >= SHEET_WIDTH:
        return raw
    return raw.rjust(SHEET_WIDTH)


def _format_ekler_block(items: list[str]) -> list[str]:
    lines = ["EKLER:"]
    for idx, item in enumerate(items, start=1):
        lines.append(f"EK-{idx}  {item}")
    return lines


def _body_sections(cfg: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for key, label, kind in cfg.get("body") or ():
        text = _format_value(_get(parsed, key), kind)
        if not text:
            continue
        sections.append({"id": key, "label": label, "text": text, "kind": kind})
    return sections
    sections: list[dict[str, str]] = []
    for key, label, kind in cfg.get("body") or ():
        text = _format_value(_get(parsed, key), kind)
        if not text:
            continue
        sections.append({"id": key, "label": label, "text": text, "kind": kind})
    return sections


def petition_view(spec: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    layout = belge_layout(spec)
    makam = str(parsed.get("makam") or spec.get("makam") or "")
    onay = str(parsed.get("onay_notu") or TASLAK_NOTU)
    if layout == "resmi":
        return {
            "id": spec.get("id"),
            "title": spec.get("title"),
            "family": spec.get("family") or "kamu",
            "layout": "resmi",
            "makam": makam,
            "hitap": hitap(makam),
            "konu": parsed.get("konu") or spec.get("title"),
            "via": None,
            "subtitle": spec.get("title"),
            "meta": [],
            "sections": [],
            "closing": "",
            "signature": None,
            "onay_notu": onay,
        }

    cfg = LAYOUTS.get(str(spec.get("id") or ""), {})
    belge_id = str(spec.get("id") or "")
    sections = [section for section in _body_sections(cfg, parsed) if section.get("kind") != "eksik"]
    paragraphs = _body_paragraphs(cfg, parsed, belge_id)
    name = _signer_name(parsed)
    adres = _sheet_adres(parsed)
    ekler = _collect_ekler(belge_id, parsed)
    return {
        "id": spec.get("id"),
        "title": spec.get("title"),
        "family": spec.get("family") or "ceza",
        "layout": layout,
        "form": "dilekce",
        "makam": makam,
        "hitap": hitap(makam),
        "via": cfg.get("via"),
        "subtitle": None,
        "konu": parsed.get("konu") or spec.get("title"),
        "tarih": _sheet_date(parsed),
        "sehir": _sheet_city(parsed),
        "adres": adres,
        "ekler": ekler,
        "paragraphs": paragraphs,
        "meta": _meta_rows(cfg, spec, parsed),
        "sections": sections,
        "closing": CLASSIC_CLOSING,
        "signature": {"role": "(imza)", "name": name},
        "onay_notu": onay,
    }


def _adres_lines(adres: str) -> list[str]:
    raw = str(adres or ADRES_PLACEHOLDER).strip()
    parts = [part.strip() for part in re.split(r"[\n;]+", raw) if part.strip()]
    if not parts:
        parts = [ADRES_PLACEHOLDER]
    return ["Adres:"] + parts


def render_petition_text(view: dict[str, Any]) -> str:
    lines: list[str] = [_center("T.C.")]
    via = str(view.get("via") or "").strip()
    if via:
        lines.append(_center(via[0].upper() + via[1:] if via else via))
    lines.append(_center(str(view.get("hitap") or "İlgili makama")))
    sehir = str(view.get("sehir") or "").strip()
    if sehir:
        lines.append(_center(sehir))
    lines.append("")
    lines.append("")
    first = True
    for paragraph in view.get("paragraphs") or []:
        text = str(paragraph or "").strip()
        if not text:
            continue
        lines.append(("     " + text) if first else text)
        first = False
        lines.append("")
    closing = str(view.get("closing") or CLASSIC_CLOSING).strip()
    if closing:
        lines.append("     " + closing)
        lines.append("")
    tarih = str(view.get("tarih") or _sheet_date({}))
    signature = view.get("signature") or {}
    name = str(signature.get("name") or NAME_PLACEHOLDER).strip()
    left = _adres_lines(str(view.get("adres") or ADRES_PLACEHOLDER))
    right = [tarih, "(imza)", name]
    rows = max(len(left), len(right))
    for idx in range(rows):
        lft = left[idx] if idx < len(left) else ""
        rgt = right[idx] if idx < len(right) else ""
        if rgt:
            gap = max(2, SHEET_WIDTH - len(lft) - len(rgt))
            lines.append(f"{lft}{' ' * gap}{rgt}")
        else:
            lines.append(lft)
    lines.append("")
    lines.extend(_format_ekler_block(list(view.get("ekler") or ["—"])))
    lines.append("")
    lines.append(str(view.get("onay_notu") or TASLAK_NOTU))
    return "\n".join(part for part in lines).strip() + "\n"
