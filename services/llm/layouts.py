from __future__ import annotations

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
        "meta": (("İtiraz olunan karar", "itiraz_olunan"), ("Süre (CMK m.268)", "sure_cumlesi")),
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
        "meta": (("İtiraz olunan karar", "karar"), ("Süre (CMK m.268)", "sure_cumlesi")),
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
        "meta": (("İstinaf olunan hüküm", "hukum"), ("Süre (CMK m.273)", "sure_cumlesi")),
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
        "meta": (("Temyiz olunan karar", "karar"), ("Süre (CMK m.291)", "sure_cumlesi")),
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
    text = " ".join(str(makam or "").split())
    if not text:
        return "İLGİLİ MAKAMA"
    upper = tr_upper(text)
    if upper.endswith(("NA", "NE", "'NA", "'NE", "’NA", "’NE")):
        return upper
    return f"{upper}'NA"


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
    madde = item.get("madde")
    n = item.get("n")
    parts: list[str] = []
    if madde:
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
        if value in (None, "", []):
            continue
        rows.append({"label": label, "value": " ".join(str(value).split())})
    return rows


def _body_sections(cfg: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, str]]:
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
    subtitle = str(cfg.get("subtitle") or spec.get("title") or "DİLEKÇEDİR")
    sections = _body_sections(cfg, parsed)
    eksikler = parsed.get("eksikler") or []
    if eksikler:
        if isinstance(eksikler, list):
            text = "\n".join(f"• {line}" for line in eksikler if str(line).strip())
        else:
            text = str(eksikler).strip()
        if text:
            sections.insert(
                0,
                {
                    "id": "eksikler",
                    "label": "Eksik hususlar — şurada eksikliğin var",
                    "text": text,
                    "kind": "eksik",
                },
            )
    return {
        "id": spec.get("id"),
        "title": spec.get("title"),
        "family": spec.get("family") or "ceza",
        "layout": layout,
        "makam": makam,
        "hitap": hitap(makam),
        "via": cfg.get("via"),
        "subtitle": subtitle,
        "konu": parsed.get("konu") or spec.get("title"),
        "meta": _meta_rows(cfg, spec, parsed),
        "sections": sections,
        "closing": cfg.get("closing") or "Arz olunur.",
        "signature": {"role": cfg.get("signature") or "", "name": "(İmza)"},
        "onay_notu": onay,
    }


def render_petition_text(view: dict[str, Any]) -> str:
    lines: list[str] = ["T.C."]
    via = str(view.get("via") or "").strip()
    if via:
        lines.append(tr_upper(via))
    lines.append(str(view.get("hitap") or "İLGİLİ MAKAMA"))
    lines.append("")
    subtitle = str(view.get("subtitle") or "").strip()
    if subtitle:
        lines.append(subtitle)
        lines.append("")
    for row in view.get("meta") or []:
        label = str(row.get("label") or "")
        value = str(row.get("value") or "")
        pad = " " * max(1, 24 - len(label))
        lines.append(f"{label}{pad}: {value}")
    if view.get("meta"):
        lines.append("")
    for section in view.get("sections") or []:
        label = str(section.get("label") or "").strip()
        text = str(section.get("text") or "").strip()
        if not text:
            continue
        if label:
            lines.append(tr_upper(label))
        lines.append(text)
        lines.append("")
    closing = str(view.get("closing") or "").strip()
    if closing:
        lines.append(closing)
        lines.append("")
    signature = view.get("signature") or {}
    role = str(signature.get("role") or "").strip()
    name = str(signature.get("name") or "").strip()
    if role or name:
        indent = " " * 36
        if role:
            lines.append(f"{indent}{role}")
        if name:
            lines.append(f"{indent}{name}")
        lines.append("")
    lines.append(str(view.get("onay_notu") or TASLAK_NOTU))
    return "\n".join(part for part in lines).strip() + "\n"
