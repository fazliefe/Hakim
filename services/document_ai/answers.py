from __future__ import annotations

from datetime import date, datetime
from typing import Any

from document_ai.classify import Classification
from document_ai.schemas import FIELD_LABELS


STAGE_TR = {
    "sorusturma": "Soruşturma",
    "kovusturma": "Kovuşturma (ilk derece)",
    "istinaf": "İstinaf",
    "temyiz": "Temyiz",
    "bireysel_basvuru": "Bireysel başvuru",
    "belirsiz": "Belirsiz",
}

NATURE_TR = {
    "ceza": "ceza",
    "idare": "idare",
    "anayasa": "anayasa",
    "kamu": "kamu yazışması",
    "belirsiz": "nitelik belirsiz",
}

LAW_SHORT = {
    "5237": "TCK",
    "5271": "CMK",
    "2577": "İYUK",
    "4721": "TMK",
    "6098": "TBK",
    "2004": "İİK",
    "7201": "Tebligat K.",
    "4982": "4982 sayılı Kanun",
    "5070": "5070 sayılı Kanun",
    "2709": "Anayasa",
    "6216": "6216 sayılı Kanun",
}

BELGE_TITLE = {
    "istinaf": "istinaf dilekçesi",
    "temyiz": "temyiz dilekçesi",
    "itiraz": "itiraz dilekçesi",
    "cevap": "cevap dilekçesi",
    "sikayet": "şikayet dilekçesi",
    "suc_duyurusu": "suç duyurusu",
    "katilma": "davaya katılma talebi",
    "bireysel_basvuru": "bireysel başvuru dilekçesi",
    "idari_dava": "idari dava dilekçesi",
    "tahliye": "tahliye talebi",
    "adli_kontrol_itiraz": "adli kontrol / tutuklama itirazı",
    "ust_yazi": "üst yazı",
    "bilgi_yazisi": "bilgi yazısı",
    "olur": "olur yazısı",
    "cevap_yazisi": "cevap yazısı",
}


def excerpt(text: str, limit: int = 240) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _tr_date(value: date | str | None) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    raw = str(value)
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return raw


def format_okuyucu(quoted: str) -> tuple[str, str]:
    blob = (quoted or "").strip()
    n = len(blob)
    summary = f"{n} karakter okundu"
    alinti = excerpt(blob, 240) or "—"
    if n < 40:
        answer = (
            f"Metin yetersiz ({n} karakter). Sonraki adımlar bu okumaya bağlıdır.\n"
            f"Alıntı: «{alinti}»."
        )
    else:
        answer = f"Evrak metni okundu ({n} karakter).\nAlıntı: «{alinti}»."
    return summary, answer


def format_sinif(
    classification: Classification,
    fields: dict[str, str] | None = None,
    missing: list[str] | None = None,
) -> tuple[str, str]:
    nature = NATURE_TR.get(classification.legal_nature, classification.legal_nature)
    stage = STAGE_TR.get(classification.stage, classification.stage)
    summary = f"{classification.label} · {nature}"
    lines = [
        f"Tür: {classification.label}.",
        f"Nitelik: {nature}.",
        f"Aşama: {stage}.",
        f"Birim: {classification.unit}.",
    ]
    span = excerpt(classification.evidence_span, 180)
    if span:
        lines.append(f"Kanıt: «{span}».")
    seen = []
    for key, value in (fields or {}).items():
        if not str(value).strip():
            continue
        label = FIELD_LABELS.get(key, key)
        seen.append(f"{label}: {_tr_date(value) if key in {'teblig', 'karar', 'tarih'} else value}")
    if seen:
        lines.append("Görülen alanlar: " + "; ".join(seen) + ".")
    if missing:
        lines.append("Eksik: " + ", ".join(missing) + ".")
    else:
        lines.append("Zorunlu alan eksiği yok.")
    return summary, "\n".join(lines)


def _cite_hit(hit: dict[str, Any], n: int) -> str:
    law_no = str(hit.get("law_no") or "").strip()
    article_no = str(hit.get("article_no") or "").strip()
    title = str(hit.get("title") or "").strip()
    span = excerpt(hit.get("content") or hit.get("span") or "", 160)
    short = LAW_SHORT.get(law_no)
    if short and article_no:
        label = f"{short} m.{article_no}"
    elif law_no and article_no:
        label = f"{law_no} sayılı kanun m.{article_no}"
    elif title:
        label = title
    else:
        label = str(hit.get("document_id") or "Kaynak")
    if title and title not in label:
        label = f"{label} {title}"
    if span:
        return f"[{n}] {label}: «{span}»"
    return f"[{n}] {label}."


def format_mevzuat_hits(related: list[dict[str, Any]]) -> tuple[str, str]:
    rows = list(related or [])
    summary = f"{len(rows)} kaynak" if rows else "Eşleşen madde yok"
    if not rows:
        return format_mevzuat_empty()
    lines = ["İlgili mevzuat / emsal (index):"]
    for i, hit in enumerate(rows, start=1):
        lines.append(_cite_hit(hit, int(hit.get("n") or i)))
    return summary, "\n".join(lines)


def format_mevzuat_2646() -> tuple[str, str]:
    summary = "2646 Yönetmelik m.10–20 (statik dayanak)"
    answer = (
        "Kamu yazışması dayanağı: Resmî Yazışma Usulleri Hakkında Yönetmelik "
        "(10.03.2025 tarihli ve 2646 sayılı Cumhurbaşkanlığı Kararı) m.10–20.\n"
        "Zorunlu bloklar: başlık, sayı, konu, muhatap, ilgi, metin, imza, ek, dağıtım, olur.\n"
        "Kanun maddesi taranmadı; bu türde yazışma standardı geçerlidir."
    )
    return summary, answer


def format_mevzuat_empty() -> tuple[str, str]:
    summary = "Eşleşen madde yok"
    answer = (
        "Eşleşen mevzuat maddesi bulunamadı.\n"
        "Taslağa uydurma madde yazılmaz; üretim gerçek madde yerine geçmez."
    )
    return summary, answer


def format_sure(deadlines: list[Any] | None) -> tuple[str, str]:
    rows = list(deadlines or [])
    if not rows:
        return (
            "Bu türde kanun yolu süresi yok",
            "Bu evrak türünde kanun yolu süresi işletilmez.\n"
            "Süre kuralı yok; son gün hesaplanmadı.",
        )
    missing_any = any(getattr(item, "missing", None) for item in rows)
    if missing_any:
        summary = f"{len(rows)} kural · tetik tarihi eksik"
    else:
        summary = f"{len(rows)} süre kuralı"
    lines = ["İşleyen süreler:"]
    for item in rows:
        name = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else "Süre")
        last = getattr(item, "last_day", None)
        if last is None and isinstance(item, dict):
            last = item.get("last_day")
        missing = getattr(item, "missing", None)
        if missing is None and isinstance(item, dict):
            missing = item.get("missing")
        basis = getattr(item, "legal_basis", None)
        if basis is None and isinstance(item, dict):
            basis = item.get("legal_basis")
        label = ""
        if isinstance(basis, (list, tuple)) and basis:
            label = str(basis[0])
        elif basis:
            label = str(basis)
        if missing:
            lines.append(f"{name}: hesaplanamadı ({missing}).")
        elif last:
            extra = f" ({label})" if label else ""
            lines.append(f"{name}: son gün {_tr_date(last)}{extra}.")
        else:
            lines.append(f"{name}: son gün belirlenmedi.")
    return summary, "\n".join(lines)


def format_taslak(action: str, reason: str) -> tuple[str, str]:
    key = (action or "ust_yazi").strip()
    title = BELGE_TITLE.get(key, key.replace("_", " "))
    summary = f"Kalıp: {key}"
    why = (reason or "").strip()
    if why and not why.endswith("."):
        why += "."
    answer = (
        f"{why} Üretilecek yazı: {title}.\n"
        "Tam metin Taslaklar bölümündedir; burada uydurma hüküm yazılmaz."
    ).strip()
    return summary, answer


def format_havale(unit: str, route_reason: str = "") -> tuple[str, str]:
    target = (unit or "Evrak kayıt / ilgili birim").strip()
    summary = target
    why = (route_reason or "").strip()
    if why and not why.endswith("."):
        why += "."
    extra = f" {why}" if why else ""
    answer = (
        f"Havale birimi: {target}.{extra}\n"
        "UYAP/EBYS’ye otomatik gönderim yoktur; onay ve tebliğ kullanıcıya aittir."
    )
    return summary, answer
