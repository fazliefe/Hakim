from __future__ import annotations

from datetime import date
import re

from document_ai.schemas import FIELD_LABELS, required_fields

DATE_RE = re.compile(
    r"(?P<label>tebli[gğ]\s*tarihi|karar\s*tarihi|tebli[gğ]\s*g[uü]n[uü])\s*[:\-]?\s*"
    r"(?P<d>\d{1,2})[./](?P<m>\d{1,2})[./](?P<y>\d{4})",
    re.IGNORECASE,
)
BARE_DATE_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b")
LINE_FIELD_RE = re.compile(
    r"^(?P<key>sayı|sayi|konu|ilgi|ek|dağıtım|dagitim)\s*[:：]\s*(?P<val>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
HEADER_RE = re.compile(r"T\.C\.\s*\n\s*([^\n]+)", re.IGNORECASE)
MUHATAP_RE = re.compile(
    r"(?m)^([A-ZÇĞİÖŞÜÂÊÎÔÛ ]{8,}(?:NE|NA|YE|YA))\s*$"
)
GENELGE_NO_RE = re.compile(r"(\d{4}\s*/\s*\d+)\s*sayılı\s*genelge", re.IGNORECASE)

def _fold_key(value: str) -> str:
    return value.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()


def parse_tr_date(day: str, month: str, year: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def extract_dates(text: str) -> dict[str, date]:
    found: dict[str, date] = {}
    for match in DATE_RE.finditer(text):
        value = parse_tr_date(match.group("d"), match.group("m"), match.group("y"))
        if value is None:
            continue
        label = match.group("label").lower()
        if "tebli" in label:
            found["teblig"] = value
        elif "karar" in label:
            found["karar"] = value
    if "teblig" not in found:
        bare = BARE_DATE_RE.search(text)
        if value := (parse_tr_date(*bare.groups()) if bare else None):
            found["teblig"] = value
    return found


def extract_fields(text: str) -> dict[str, str]:
    """Resmî yazışma ve yargı evrakından görünen alanları çıkarır; uydurmaz."""
    fields: dict[str, str] = {}
    for match in LINE_FIELD_RE.finditer(text):
        key = {"sayi": "sayi", "konu": "konu", "ilgi": "ilgi", "ek": "ek", "dagitim": "dagitim"}.get(
            _fold_key(match.group("key")).replace("ğ", "g")
        )
        val = " ".join(match.group("val").split())
        if key and val:
            fields[key] = val
    header = HEADER_RE.search(text)
    if header:
        fields.setdefault("kurum", " ".join(header.group(1).split()))
    muhatap = MUHATAP_RE.search(text)
    if muhatap:
        fields.setdefault("muhatap", " ".join(muhatap.group(1).split()))
    genelge = GENELGE_NO_RE.search(text)
    if genelge:
        fields.setdefault("sayi", re.sub(r"\s+", "", genelge.group(1)))
    dates = extract_dates(text)
    if "teblig" in dates:
        fields.setdefault("teblig", dates["teblig"].isoformat())
        fields.setdefault("tarih", dates["teblig"].isoformat())
    if "karar" in dates:
        fields.setdefault("karar", dates["karar"].isoformat())
        fields.setdefault("tarih", dates["karar"].isoformat())
    if "tarih" not in fields:
        bare = BARE_DATE_RE.search(text)
        if bare:
            value = parse_tr_date(*bare.groups())
            if value:
                fields["tarih"] = value.isoformat()
    return fields


def missing_fields(document_type: str, fields: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for key in required_fields(document_type):
        if not (fields.get(key) or "").strip():
            missing.append(FIELD_LABELS.get(key, key))
    return missing


def looks_like_resmi_yazi(text: str) -> bool:
    blob = text.lower().replace("ı", "i")
    return ("sayi:" in blob or "sayı:" in blob) and ("konu:" in blob)


def extract_resmi_body(text: str) -> str:
    """Sayı/Konu/Muhatap başlığından sonraki yazı gövdesi; tüm evrakı metne yapıştırma."""
    lines = [ln.strip() for ln in str(text or "").splitlines()]
    body: list[str] = []
    past_header = False
    for line in lines:
        if not line:
            if past_header and body:
                body.append("")
            continue
        low = line.lower().replace("ı", "i")
        if not past_header:
            if MUHATAP_RE.match(line) or (
                len(line) > 8 and line == line.upper() and low.endswith(("ne", "na", "ye", "ya"))
            ):
                past_header = True
            continue
        if low == "t.c." or LINE_FIELD_RE.match(line):
            continue
        body.append(line)
    return " ".join(" ".join(body).split())
