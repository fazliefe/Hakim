from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SABLON_PATH = ROOT / "data" / "formats" / "resmi_yazisma" / "sablon.json"

KAMU_BELGE_IDS = frozenset({"ust_yazi", "bilgi_yazisi", "cevap_yazisi", "olur", "tekit"})


def load_sablon() -> dict[str, Any]:
    return json.loads(SABLON_PATH.read_text(encoding="utf-8"))


def variant_for_document_type(document_type: str) -> str:
    sablon = load_sablon()
    return str(sablon.get("evrak_turu_eslestirme", {}).get(document_type) or "ust_yazi")


def _blank(n: int) -> list[str]:
    return [""] * max(0, n)


def _format_ilgi(raw: str, *, coklu: list[str] | None = None) -> str:
    if coklu:
        letters = "abcdefghijklmnopqrstuvwxyz"
        parts = []
        for idx, item in enumerate(coklu[:4]):
            letter = letters[idx] if idx < len(letters) else str(idx + 1)
            parts.append(f"{letter}) {item}")
        return "\n".join(parts)
    text = str(raw or "").strip()
    if not text:
        return ""
    if text.lower().startswith("ilgi"):
        return text
    return text if text.endswith(".") else f"{text}."


def _format_ekler(ekler: list[str] | str | None) -> str:
    if not ekler:
        return ""
    if isinstance(ekler, str):
        return ekler
    if len(ekler) == 1:
        return ekler[0]
    return "\n".join(f"{idx}- {item}" for idx, item in enumerate(ekler, start=1))


def _format_dagitim(dagitim: dict[str, Any] | None) -> tuple[str, str]:
    if not dagitim:
        return "", ""
    geregi = dagitim.get("geregi") or []
    bilgi = dagitim.get("bilgi") or []
    geregi_txt = "\n".join(str(x) for x in geregi) if geregi else ""
    bilgi_txt = "\n".join(str(x) for x in bilgi) if bilgi else ""
    return geregi_txt, bilgi_txt


def _ensure_kapanis(metin: str, kapanis: str) -> str:
    body = " ".join(str(metin or "").split())
    if not body:
        return f"Gereğini {kapanis}."
    lowered = body.lower()
    if any(token in lowered for token in ("arz ederim", "rica ederim", "arz/rica", "arz ve rica")):
        return body if body.endswith(".") else f"{body}."
    return f"{body} Gereğini {kapanis}." if body.endswith(".") else f"{body}. Gereğini {kapanis}."


def render_resmi_yazi(variant_id: str, data: dict[str, Any]) -> str:
    """Yönetmelik Ek (2646) blok sırasına göre düz metin üst yazı üretir."""
    sablon = load_sablon()
    variant = sablon["varyantlar"].get(variant_id) or sablon["varyantlar"]["ust_yazi"]
    blocks = sablon["bloklar"]

    kurum = str(data.get("kurum") or data.get("makam") or "İLGİLİ İDARE").strip()
    birim = str(data.get("birim") or "").strip()
    sayi = str(data.get("sayi") or "—")
    tarih = str(data.get("tarih") or date.today().isoformat())
    konu = str(data.get("konu") or "—")
    muhatap = str(data.get("muhatap") or variant.get("varsayilan_muhatap") or "İLGİLİ MAKAMA")
    muhatap_birim = str(data.get("muhatap_birim") or "").strip()
    ilgi = _format_ilgi(str(data.get("ilgi") or ""), coklu=data.get("ilgi_listesi"))
    metin = _ensure_kapanis(str(data.get("metin") or ""), str(variant.get("kapanis") or "rica ederim"))
    imza_ad = str(data.get("imza_ad") or "Yetkili")
    imza_unvan = str(data.get("imza_unvan") or kurum)
    olur_ad = str(data.get("olur_ad") or "Oluru alan makam")
    olur_unvan = str(data.get("olur_unvan") or "Makam")
    ek_txt = _format_ekler(data.get("ekler"))
    geregi_txt, bilgi_txt = _format_dagitim(data.get("dagitim"))
    onay = str(
        data.get("onay_notu") or "Taslaktır. EBYS/UYAP’a otomatik gönderim yoktur."
    )

    lines: list[str] = []
    for block_id in variant.get("blok_sirasi") or []:
        spec = blocks.get(block_id) or {}
        lines.extend(_blank(int(spec.get("once_bos_satir") or 0)))

        if block_id == "baslik":
            lines.append("T.C.")
            lines.append(kurum.upper())
            if birim:
                lines.append(birim)
            continue

        if block_id == "acele":
            lines.append("ACELE")
            continue

        if block_id == "sayi_konu":
            lines.append(f"Sayı\t: {sayi}\t{tarih}")
            lines.append(f"Konu\t: {konu}")
            lines.extend(_blank(2))
            continue

        if block_id == "muhatap":
            lines.append(muhatap.upper())
            if muhatap_birim:
                lines.append(f"({muhatap_birim})")
            continue

        if block_id == "ilgi":
            if ilgi:
                for row in ilgi.splitlines():
                    if row.strip().lower().startswith(("a)", "b)", "c)", "ç)", "d)")):
                        lines.append(f"İlgi\t: {row}")
                    else:
                        lines.append(f"İlgi\t: {row}")
            continue

        if block_id == "metin":
            lines.extend(_blank(int(spec.get("once_bos_satir") or 1)))
            lines.append(metin)
            continue

        if block_id == "imza":
            lines.extend(_blank(2))
            lines.append(imza_ad)
            lines.append(imza_unvan)
            continue

        if block_id == "olur":
            lines.extend(_blank(1))
            lines.append("OLUR")
            lines.append(olur_ad)
            lines.append(olur_unvan)
            continue

        if block_id == "ek":
            if ek_txt:
                if "\n" in ek_txt:
                    lines.append("Ek:")
                    lines.append(ek_txt)
                else:
                    lines.append(f"Ek: {ek_txt}")
            continue

        if block_id == "dagitim":
            if geregi_txt or bilgi_txt:
                lines.append("Dağıtım:")
                if geregi_txt:
                    lines.append("Gereği:")
                    lines.extend(geregi_txt.splitlines())
                if bilgi_txt:
                    lines.append("Bilgi:")
                    lines.extend(bilgi_txt.splitlines())
            continue

        if block_id == "onay":
            lines.extend(_blank(1))
            lines.append(onay)

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip() + "\n"


def draft_data_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """Evrak analiz JSON'undan resmi yazı alanlarını doldur."""
    classification = analysis.get("classification") or {}
    fields = analysis.get("fields") or {}
    dates = analysis.get("dates") or {}
    doc_type = str(classification.get("document_type") or "ust_yazi")
    variant = variant_for_document_type(doc_type)

    kurum = str(fields.get("kurum") or classification.get("unit") or "İlgili idare")
    konu = str(fields.get("konu") or classification.get("label") or "—")
    sayi = str(fields.get("sayi") or "—")
    tarih = str(fields.get("tarih") or dates.get("karar") or dates.get("teblig") or date.today().isoformat())
    ilgi = str(fields.get("ilgi") or "")
    muhatap = str(fields.get("muhatap") or "")
    if not muhatap:
        if variant == "bilgi_yazisi":
            muhatap = "DAĞITIM YERLERİNE"
        elif variant == "olur":
            muhatap = f"{kurum.upper()} MAKAMINA"
        else:
            muhatap = "İLGİLİ BİRİME"

    from document_ai.extract import extract_resmi_body

    body = extract_resmi_body(str(analysis.get("user_text") or ""))
    if body:
        metin = body
    else:
        label = str(classification.get("label") or "evrak")
        metin = f"İşbu yazı, {label} incelenmesi üzerine ilgili birime iletilmek üzere hazırlanmıştır."

    dagitim = None
    if variant in {"ust_yazi", "bilgi_yazisi"}:
        dagitim = {
            "geregi": [str(classification.get("unit") or "İlgili birim")],
            "bilgi": ["Evrak kayıt"],
        }

    return {
        "variant": variant,
        "kurum": kurum,
        "birim": str(classification.get("unit") or ""),
        "sayi": sayi,
        "tarih": tarih,
        "konu": konu,
        "muhatap": muhatap,
        "ilgi": ilgi,
        "metin": metin,
        "ekler": [f"İlgi evrak ({classification.get('label', 'evrak')})"] if ilgi else [],
        "dagitim": dagitim,
        "havale": str(classification.get("unit") or ""),
        "onay_notu": "Taslaktır. EBYS/UYAP’a otomatik gönderim yoktur.",
    }
