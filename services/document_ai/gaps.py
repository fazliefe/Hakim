from __future__ import annotations

import re
from typing import Any

from document_ai.extract import BARE_DATE_RE, extract_dates

NAME_RE = re.compile(
    r"\b[A-ZÇĞİÖŞÜÂÊÎÔÛ][a-zçğıöşüâêîôû]+\s+[A-ZÇĞİÖŞÜÂÊÎÔÛ][a-zçğıöşüâêîôû]+\b"
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
COURT_TYPE_RE = re.compile(
    r"\b(agir ceza|asliye ceza|sulh ceza|asliye hukuk|sulh hukuk|"
    r"idare mahkeme|vergi mahkeme|bolge adliye|yargitay|danistay|"
    r"anayasa mahkeme|icra)\b"
)
DOCKET_RE = re.compile(r"\b(?:esas|karar)\s*(?:no)?\s*[:/]?\s*\d{4}\s*/\s*\d+", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"\b(mah(alle)?\.?|sok(ak)?\.?|cad(de)?\.?|bulvar|no\s*[:.]?\s*\d+|daire|apt\.?|apartman)\b",
    re.IGNORECASE,
)
TEBLIG_WORD_RE = re.compile(r"tebli[gğ]", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"«\[([^\]]+)\]»")
LABELED_FACT_RE = re.compile(
    r"(?im)^(adres|il|ad soyad|şikayetçi|sikayetci|şikayet edilen|"
    r"olay tarihi|olay yeri|deliller|tebliğ tarihi|teblig tarihi|"
    r"mahkeme|esas no)\s*:\s*(.+)$"
)
_NOT_PERSON_RE = re.compile(
    r"mahkem|hakimli|savcil|bakanl|valilik|beledi|mudurl|adliye|"
    r"yargitay|danistay|anayasa|mahall|sokak|cadd|bulvar|baskanl|"
    r"cumhuriyet|bassavci"
)
_ILLER_RE = re.compile(
    r"\b(adana|adiyaman|afyonkarahisar|afyon|agri|aksaray|amasya|ankara|"
    r"antalya|ardahan|artvin|aydin|balikesir|bartin|batman|bayburt|bilecik|"
    r"bingol|bitlis|bolu|burdur|bursa|canakkale|cankiri|corum|denizli|"
    r"diyarbakir|duzce|edirne|elazig|erzincan|erzurum|eskisehir|gaziantep|"
    r"giresun|gumushane|hakkari|hatay|igdir|isparta|istanbul|izmir|"
    r"kahramanmaras|karabuk|karaman|kars|kastamonu|kayseri|kilis|kirikkale|"
    r"kirklareli|kirsehir|kocaeli|konya|kutahya|malatya|manisa|mardin|"
    r"mersin|mugla|mus|nevsehir|nigde|ordu|osmaniye|rize|sakarya|samsun|"
    r"sanliurfa|siirt|sinop|sivas|sirnak|tekirdag|tokat|trabzon|tunceli|"
    r"usak|van|yalova|yozgat|zonguldak)\b"
)
_PLACEHOLDER_GAP = {
    "adres": "adres",
    "il": "il",
    "ad soyad": "ad_soyad",
    "şikayetçi adı-soyadı": "sikayetci",
    "şikayetçi": "sikayetci",
    "olay tarihi gg.aa.yyyy": "olay_tarihi",
    "olay tarihi": "olay_tarihi",
    "olay yeri": "olay_yeri",
    "deliller — dekont, yazışma, tanık": "delil",
    "deliller": "delil",
    "tebliğ tarihi gg.aa.yyyy": "teblig",
    "tebliğ tarihi": "teblig",
    "mahkeme adı": "mahkeme",
    "esas / karar no": "esas",
}
_LABEL_TO_FIELD = {
    "adres": "adres",
    "il": "sehir",
    "ad soyad": "ad_soyad",
    "şikayetçi": "sikayetci",
    "sikayetci": "sikayetci",
    "şikayet edilen": "sikayet_edilen",
    "olay tarihi": "olay_tarihi",
    "olay yeri": "olay_yeri",
    "deliller": "deliller",
    "tebliğ tarihi": "teblig",
    "teblig tarihi": "teblig",
    "mahkeme": "mahkeme",
    "esas no": "esas_no",
}

_GAP: dict[str, dict[str, str]] = {
    "anlatim": {
        "label": "Olay anlatımı",
        "hint": "Ne olduğunu, mümkünse tarih ve yerle birlikte yazın.",
    },
    "sikayetci": {
        "label": "Şikayetçi adı-soyadı",
        "hint": "Dilekçede kimlik uydurulmaz; adınızı yazın.",
    },
    "ad_soyad": {
        "label": "Ad soyad",
        "hint": "Dilekçenin altındaki imza için adınızı ve soyadınızı yazın.",
    },
    "adres": {
        "label": "Adres",
        "hint": "Mahalle, sokak ve kapı no yazın; dilekçede adres uydurulmaz.",
    },
    "il": {
        "label": "İl",
        "hint": "Dilekçenin yazıldığı ili yazın.",
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
        "hint": "Hükmü veren mahkemenin tam adını yazın (il ve daire).",
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


def _ascii_fold(text: str) -> str:
    return (
        _fold(text)
        .lower()
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
    )


def _has_city(text: str) -> bool:
    return bool(_ILLER_RE.search(_ascii_fold(text)))


def _has_address(text: str) -> bool:
    return bool(ADDRESS_RE.search(text or ""))


def _person_names(text: str) -> list[str]:
    names: list[str] = []
    for match in NAME_RE.finditer(text or ""):
        blob = match.group(0)
        if _NOT_PERSON_RE.search(_ascii_fold(blob)):
            continue
        names.append(blob)
    return names


def _has_specific_court(text: str, fields: dict[str, Any]) -> bool:
    blob = _ascii_fold(f"{text or ''} {fields.get('kurum') or ''}")
    if re.search(r"\d+\.\s*(agir|asliye|sulh|idare|vergi)", blob):
        return True
    if re.search(r"\b(yargitay|danistay|anayasa mahkeme)\b", blob):
        return True
    if COURT_TYPE_RE.search(blob) and (_has_city(text) or re.search(r"\d+\.", blob)):
        return True
    return False


def _has_teblig(text: str, has_date: bool) -> bool:
    return bool(TEBLIG_WORD_RE.search(text or "") and has_date)


def labeled_facts(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in LABELED_FACT_RE.finditer(text or ""):
        key = _LABEL_TO_FIELD.get(_fold(match.group(1)).strip().lower())
        value = match.group(2).strip().strip("«»[]")
        if key and value and not value.startswith("["):
            out[key] = value
    return out


def _uniq(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in rows:
        gap_id = item.get("id") or ""
        if not gap_id or gap_id in seen:
            continue
        if gap_id == "ad_soyad" and "sikayetci" in seen:
            continue
        if gap_id == "sikayetci" and "ad_soyad" in seen:
            continue
        seen.add(gap_id)
        out.append(item)
    return out


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
    names = _person_names(raw)
    facts = labeled_facts(raw)
    gaps: list[dict[str, str]] = []
    kind = (action or "").strip().lower()
    complaint = kind in {"sikayet", "suc_duyurusu"}
    appeal = kind in {"istinaf", "temyiz", "itiraz", "adli_kontrol_itiraz"}
    casefile = kind in {"cevap", "katilma", "tahliye", "bireysel_basvuru", "idari_dava"}

    if len(raw) < 48:
        gaps.append(_row("anlatim"))

    if complaint:
        if not names and not facts.get("sikayetci"):
            gaps.append(_row("sikayetci"))
        if len(names) < 2 and not SUSPECT_RE.search(folded) and not facts.get("sikayet_edilen"):
            gaps.append(_row("sikayet_edilen"))
        if not has_date:
            gaps.append(_row("olay_tarihi"))
        if not _has_city(raw) and not re.search(r"\b(ilce|ilçe|sube|şube)\b", folded):
            gaps.append(_row("olay_yeri"))
        if not EVIDENCE_RE.search(folded):
            gaps.append(_row("delil"))
    else:
        if not names and not facts.get("ad_soyad") and not facts.get("sikayetci"):
            gaps.append(_row("ad_soyad"))

    if not facts.get("adres") and not _has_address(raw):
        gaps.append(_row("adres"))
    if not facts.get("sehir") and not _has_city(raw):
        gaps.append(_row("il"))

    if appeal or kind in {"cevap", "katilma", "bireysel_basvuru"}:
        if not _has_teblig(raw, has_date) and not facts.get("teblig"):
            gaps.append(_row("teblig"))
        if not _has_specific_court(raw, fields):
            gaps.append(_row("mahkeme"))
        if not DOCKET_RE.search(raw) and not facts.get("esas_no"):
            gaps.append(_row("esas"))
    elif kind == "tahliye":
        if not has_date:
            gaps.append(_row("olay_tarihi"))
        if not _has_specific_court(raw, fields):
            gaps.append(_row("mahkeme"))
    elif kind == "idari_dava":
        if not has_date:
            gaps.append(_row("olay_tarihi"))
        if not _has_specific_court(raw, fields):
            gaps.append(_row("mahkeme"))
    elif not complaint and not casefile and len(raw) < 80:
        if not has_date:
            gaps.append(_row("olay_tarihi"))

    return _uniq(gaps)


def merge_placeholder_gaps(
    existing: list[dict[str, str]] | None,
    *blobs: Any,
) -> list[dict[str, str]]:
    """Dilekçede kalan «[…]» yer tutucularını eksik listesine ekle."""
    rows = list(existing or [])
    seen = {item.get("id") for item in rows if item.get("id")}
    text = "\n".join(blob if isinstance(blob, str) else str(blob or "") for blob in blobs)
    for match in PLACEHOLDER_RE.finditer(text):
        inner = _fold(match.group(1)).strip().lower()
        gap_id = _PLACEHOLDER_GAP.get(inner)
        if not gap_id:
            for key, mapped in _PLACEHOLDER_GAP.items():
                if key in inner or inner in key:
                    gap_id = mapped
                    break
        if not gap_id or gap_id in seen:
            continue
        if gap_id == "ad_soyad" and ("sikayetci" in seen):
            continue
        if gap_id == "sikayetci" and ("ad_soyad" in seen):
            continue
        seen.add(gap_id)
        rows.append(_row(gap_id))
    return _uniq(rows)


PLACEHOLDERS = {
    "sikayetci": "«[şikayetçi adı-soyadı]»",
    "ad_soyad": "«[ad soyad]»",
    "adres": "«[adres]»",
    "il": "«[il]»",
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
    "esasa_cevap",
    "dava",
    "sebepler",
    "islem",
)


def apply_gap_placeholders(
    parsed: dict[str, Any],
    gaps: list[dict[str, str]],
    user_text: str,
) -> dict[str, Any]:
    ids = {item.get("id") for item in gaps}
    facts = labeled_facts(user_text)
    if facts.get("adres"):
        parsed["adres"] = facts["adres"]
    if facts.get("sehir"):
        parsed["sehir"] = facts["sehir"]
    if facts.get("ad_soyad"):
        parsed["ad_soyad"] = facts["ad_soyad"]
    if facts.get("sikayetci"):
        parsed["sikayetci"] = facts["sikayetci"]
        parsed["duyuran"] = facts["sikayetci"]
    if facts.get("esas_no"):
        parsed["esas_no"] = facts["esas_no"]
    if "sikayetci" in ids:
        parsed["sikayetci"] = PLACEHOLDERS["sikayetci"]
        parsed["duyuran"] = PLACEHOLDERS["sikayetci"]
    if "ad_soyad" in ids:
        parsed["ad_soyad"] = PLACEHOLDERS["ad_soyad"]
    if "adres" in ids:
        parsed["adres"] = PLACEHOLDERS["adres"]
    if "il" in ids:
        parsed["sehir"] = PLACEHOLDERS["il"]
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
    teblig = facts.get("teblig")
    if teblig:
        extra = f"Tebliğ tarihi: {teblig}."
        current = str(parsed.get("sure_cumlesi") or "").strip()
        if teblig not in current:
            parsed["sure_cumlesi"] = f"{current} {extra}".strip() if current else extra
    elif "teblig" in ids:
        stamp = PLACEHOLDERS["teblig"]
        current = str(parsed.get("sure_cumlesi") or "").strip()
        if stamp not in current:
            extra = f"Tebliğ tarihi: {stamp}."
            parsed["sure_cumlesi"] = f"{current} {extra}".strip() if current else extra
    if "mahkeme" in ids:
        for key in ("hukum", "karar", "itiraz_olunan"):
            val = str(parsed.get(key) or "")
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
