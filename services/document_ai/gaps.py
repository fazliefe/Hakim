from __future__ import annotations

import re
from typing import Any

from document_ai.extract import BARE_DATE_RE, extract_dates

NAME_RE = re.compile(
    r"\b[A-ZÇĞİÖŞÜÂÊÎÔÛ][a-zçğıöşüâêîôû]+\s+[A-ZÇĞİÖŞÜÂÊÎÔÛ][a-zçğıöşüâêîôû]+\b"
)
PLACE_RE = re.compile(
    r"\b(ankara|istanbul|izmir|bursa|adana|antalya|konya|gaziantep|mersin|"
    r"adres|mahalle|ilçe|ilce|sokak|cadde|şube|sube)\b",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(
    r"\b(dekont|ekstre|tanık|tanik|mesaj|whatsapp|kamera|kayit|kayıt|belge|delil|yazışma|yazisma)",
    re.IGNORECASE,
)
SUSPECT_RE = re.compile(
    r"\b(süpheli|şüpheli|sanık|sanik|fail|bir kişi|birisi|tanımadığım)\b",
    re.IGNORECASE,
)
COURT_RE = re.compile(
    r"\b(ağır ceza|agir ceza|asliye ceza|sulh ceza|bölge adliye|yargıtay|yargitay|mahkeme)\b",
    re.IGNORECASE,
)
DOCKET_RE = re.compile(r"\b(?:esas|karar)\s*(?:no)?\s*[:/]?\s*\d{4}\s*/\s*\d+", re.IGNORECASE)

_GAP: dict[str, dict[str, str]] = {
    "anlatim": {
        "label": "Olay anlatımı",
        "hint": "Ne olduğunu, mümkünse tarih ve yerle birlikte yazın.",
    },
    "sikayetci": {
        "label": "Şikayetçi adı-soyadı",
        "hint": "Dilekçede kimlik uydurulmaz; adınızı yazın.",
    },
    "sikayet_edilen": {
        "label": "Şikayet edilen / şüpheli",
        "hint": "Bilinmiyorsa «kimliği belirsiz şüpheli» yeter; bir ad varsa yazın.",
    },
    "olay_tarihi": {
        "label": "Olay veya tebliğ tarihi",
        "hint": "gg.aa.yyyy biçiminde tarih yazın.",
    },
    "olay_yeri": {
        "label": "Olay yeri",
        "hint": "İl / ilçe veya şube belirtin.",
    },
    "delil": {
        "label": "Delil",
        "hint": "Dekont, mesaj, tanık, kamera kaydı gibi dayanakları yazın.",
    },
    "teblig": {
        "label": "Tebliğ tarihi",
        "hint": "Kanun yolu süresi tebliğden işler; gg.aa.yyyy yazın.",
    },
    "mahkeme": {
        "label": "Mahkeme",
        "hint": "Hükmü veren mahkemenin adını yazın.",
    },
    "esas": {
        "label": "Esas / karar no",
        "hint": "Örn. Esas No: 2025/412.",
    },
}


def _row(gap_id: str) -> dict[str, str]:
    meta = _GAP[gap_id]
    return {"id": gap_id, "label": meta["label"], "hint": meta["hint"]}


def _fold(text: str) -> str:
    return (text or "").replace("İ", "i").replace("I", "i").replace("ı", "i")


def diagnose_islem_gaps(
    action: str,
    text: str,
    fields: dict[str, Any] | None = None,
    dates: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Kullanıcı anlatısındaki boşluklar. Kimlik ve tarih uydurulmaz."""
    raw = (text or "").strip()
    folded = _fold(raw)
    fields = fields or {}
    dates = dates or {}
    found_dates = extract_dates(raw)
    has_date = bool(found_dates or dates.get("teblig") or dates.get("karar") or BARE_DATE_RE.search(raw))
    names = NAME_RE.findall(raw)
    gaps: list[dict[str, str]] = []

    if len(raw) < 48:
        gaps.append(_row("anlatim"))

    kind = (action or "").strip().lower()
    if kind in {"sikayet", "suc_duyurusu"}:
        if not names:
            gaps.append(_row("sikayetci"))
        if len(names) < 2 and not SUSPECT_RE.search(folded):
            gaps.append(_row("sikayet_edilen"))
        if not has_date:
            gaps.append(_row("olay_tarihi"))
        if not PLACE_RE.search(folded):
            gaps.append(_row("olay_yeri"))
        if not EVIDENCE_RE.search(folded):
            gaps.append(_row("delil"))
    elif kind in {"istinaf", "temyiz", "itiraz", "adli_kontrol_itiraz"}:
        if not (found_dates.get("teblig") or dates.get("teblig") or fields.get("teblig")):
            if not has_date:
                gaps.append(_row("teblig"))
        if not COURT_RE.search(folded) and not fields.get("kurum"):
            gaps.append(_row("mahkeme"))
        if not DOCKET_RE.search(raw):
            gaps.append(_row("esas"))
    elif kind == "tahliye":
        if not names:
            gaps.append(_row("sikayetci"))
        if not has_date:
            gaps.append(_row("olay_tarihi"))
    elif len(raw) < 80:
        if not has_date:
            gaps.append(_row("olay_tarihi"))

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in gaps:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        out.append(item)
    return out


PLACEHOLDERS = {
    "sikayetci": "«[şikayetçi adı-soyadı]»",
    "sikayet_edilen": "Kimliği belirsiz şüpheli",
    "delil": "«[deliller — dekont, yazışma, tanık]»",
    "olay_tarihi": "«[olay tarihi gg.aa.yyyy]»",
    "olay_yeri": "«[olay yeri]»",
    "teblig": "«[tebliğ tarihi gg.aa.yyyy]»",
    "mahkeme": "«[mahkeme adı]»",
    "esas": "«[esas / karar no]»",
}

_NARRATIVE_KEYS = (
    "olay",
    "hukum",
    "karar",
    "tutuklama",
    "islem",
    "dava",
    "esasa_cevap",
    "itiraz_olunan",
)


def apply_gap_placeholders(
    parsed: dict[str, Any],
    gaps: list[dict[str, str]],
    user_text: str,
) -> dict[str, Any]:
    ids = {item.get("id") for item in gaps}
    if "sikayetci" in ids:
        parsed["sikayetci"] = PLACEHOLDERS["sikayetci"]
        parsed["duyuran"] = PLACEHOLDERS["sikayetci"]
    if "sikayet_edilen" in ids:
        parsed["sikayet_edilen"] = PLACEHOLDERS["sikayet_edilen"]
    if "delil" in ids:
        parsed["deliller"] = [PLACEHOLDERS["delil"]]
    notes: list[str] = []
    if "olay_tarihi" in ids:
        notes.append(f"Tarih: {PLACEHOLDERS['olay_tarihi']}")
    if "olay_yeri" in ids:
        notes.append(f"Yer: {PLACEHOLDERS['olay_yeri']}")
    if notes:
        extra = " ".join(notes)
        for key in _NARRATIVE_KEYS:
            current = str(parsed.get(key) or "").strip()
            if current:
                parsed[key] = f"{current} {extra}"
                break
        else:
            parsed["olay"] = extra
    if "teblig" in ids and not parsed.get("sure_cumlesi"):
        parsed["sure_cumlesi"] = f"Süre, {PLACEHOLDERS['teblig']} tebliğinden itibaren işler."
    if "mahkeme" in ids:
        for key in ("hukum", "karar", "itiraz_olunan"):
            val = str(parsed.get(key) or "")
            if COURT_RE.search(_fold(val)) or COURT_RE.search(_fold(user_text)):
                break
            parsed[key] = (
                f"{val.strip()} Mahkeme: {PLACEHOLDERS['mahkeme']}".strip()
                if val.strip()
                else PLACEHOLDERS["mahkeme"]
            )
            break
    if "esas" in ids and not parsed.get("esas_no"):
        parsed["esas_no"] = PLACEHOLDERS["esas"]
    if gaps:
        parsed["eksikler"] = [f"{item['label']}: {item['hint']}" for item in gaps]
    return parsed
