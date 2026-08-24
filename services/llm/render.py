from __future__ import annotations

import re
from typing import Any

RESEARCH_HEADINGS = (
    "Sonuç",
    "Hukuki dayanak",
    "İlgili hükümler",
    "Değerlendirme",
    "Kaynak",
)

KAYNAK_UYARI = "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır."
MIN_SONUC_SENTENCES = 5
_SONUC_PAD = (
    "Bu hüküm arşivdeki resmi metnin lafzına göre okunur; kaynakta olmayan unsur yazılmaz [{n}].",
    "Somut olayın maddede aranan hareket, sonuç ve kast unsurlarını taşıyıp taşımadığı dosya incelemesine bağlıdır [{n}].",
    "Nitelendirme madde başlığıyla yetinmez; ilgili fıkra ve seçimlik hareket birlikte bakılır [{n}].",
    "Bu metin nitelendirme çerçevesi verir; mahkeme hükmü veya savcılık takdirinin yerini tutmaz [{n}].",
    "Komşu maddeler aynı konuyu düzenlese de asıl dayanak yine bu kaynak olarak kalır [{n}].",
)


def count_sonuc_sentences(text: str) -> int:
    blob = str(text or "").strip()
    if not blob:
        return 0
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜÂÊÎÔÛ«\"])", blob)
    return len([part for part in parts if part.strip()])


def ensure_sonuc(text: str, *, min_sentences: int = MIN_SONUC_SENTENCES) -> str:
    current = str(text or "").strip()
    if not current:
        return current
    cite = "1"
    found = re.search(r"\[(\d+)\]", current)
    if found:
        cite = found.group(1)
    folded = current.casefold()
    for pad in _SONUC_PAD:
        if count_sonuc_sentences(current) >= min_sentences:
            break
        line = pad.replace("{n}", cite)
        if line.casefold() in folded:
            continue
        current = f"{current} {line}"
        folded = current.casefold()
    return current


def _lines(*parts: str) -> str:
    return "\n".join(part for part in parts if part is not None)


def _with_cite(text: str, n: Any) -> str:
    cumle = str(text or "").strip()
    if not cumle:
        return ""
    if n is not None and f"[{n}]" not in cumle:
        return f"{cumle} [{n}]"
    return cumle


def render_research_memo(
    *,
    sonuc: str,
    gerekce: list[str] | None = None,
    ilgili: list[str] | None = None,
    degerlendirme: str | None = None,
    uyari: str | None = None,
) -> str:
    """Hukuki mütalaa düzeni: Sonuç → dayanak → ilgili → değerlendirme → kaynak."""
    parts: list[str] = ["Sonuç", ensure_sonuc(str(sonuc or "").strip())]
    dayanak = [line.strip() for line in (gerekce or []) if str(line).strip()]
    if dayanak:
        numbered = "\n".join(f"{index}. {line}" for index, line in enumerate(dayanak, start=1))
        parts.extend(["Hukuki dayanak", numbered])
    komsu = [line.strip() for line in (ilgili or []) if str(line).strip()]
    if komsu:
        bullets = "\n".join(f"• {line}" for line in komsu)
        parts.extend(["İlgili hükümler", bullets])
    note = str(degerlendirme or "").strip()
    if note:
        parts.extend(["Değerlendirme", note])
    kaynak = str(uyari or KAYNAK_UYARI).strip().strip("_")
    parts.extend(["Kaynak", kaynak])
    return "\n\n".join(part for part in parts if part)


def render_arastirma(parsed: dict[str, Any]) -> str:
    gerekce: list[str] = []
    for item in parsed.get("gerekce") or []:
        if isinstance(item, dict):
            line = _with_cite(item.get("cumle"), item.get("n"))
        else:
            line = str(item).strip()
        if line:
            gerekce.append(line)
    ilgili: list[str] = []
    for item in parsed.get("ilgili") or []:
        if isinstance(item, dict):
            line = _with_cite(item.get("neden"), item.get("n"))
        else:
            line = str(item).strip()
        if line:
            ilgili.append(line)
    return render_research_memo(
        sonuc=str(parsed.get("ozet") or "").strip(),
        gerekce=gerekce,
        ilgili=ilgili,
        uyari=str(parsed.get("kaynak_uyari") or "") or None,
    )


def render_evrak(parsed: dict[str, Any]) -> str:
    blocks = [
        str(parsed.get("baslik") or "Evrak özeti"),
        "",
        str(parsed.get("tur_cumlesi") or ""),
        "",
        "TESPİTLER",
    ]
    for item in parsed.get("tespitler") or []:
        if isinstance(item, dict):
            blocks.append(f"- {item.get('baslik')}: {item.get('metin')}")
        else:
            blocks.append(f"- {item}")
    eksik = parsed.get("eksik") or []
    if eksik:
        blocks.extend(["", "EKSİK"])
        for item in eksik:
            blocks.append(f"- {item}")
    blocks.extend(["", str(parsed.get("ozet") or "")])
    return _lines(*blocks)


def render_surec(parsed: dict[str, Any]) -> str:
    blocks = [str(parsed.get("asama_cumlesi") or ""), ""]
    yollar = parsed.get("kanun_yollari") or []
    if yollar:
        blocks.append("KANUN YOLLARI")
        for item in yollar:
            if isinstance(item, dict):
                blocks.append(f"- {item.get('id')}: {item.get('cumle')}")
            else:
                blocks.append(f"- {item}")
        blocks.append("")
    blocks.append("SÜRELER")
    for item in parsed.get("sureler") or []:
        if isinstance(item, dict):
            blocks.append(f"- {item.get('rule_id')}: {item.get('anlatim')}")
        else:
            blocks.append(f"- {item}")
    blocks.extend(["", str(parsed.get("uyari") or "")])
    return _lines(*blocks)


def _kamu_parsed(spec: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    makam = str(parsed.get("makam") or parsed.get("kurum") or spec.get("makam") or "")
    return {
        "kurum": makam,
        "birim": parsed.get("birim") or "",
        "sayi": parsed.get("sayi") or "—",
        "tarih": parsed.get("tarih") or "",
        "konu": parsed.get("konu") or "",
        "muhatap": parsed.get("muhatap") or "",
        "muhatap_birim": parsed.get("muhatap_birim") or "",
        "ilgi": parsed.get("ilgi") or "",
        "ilgi_listesi": parsed.get("ilgi_listesi"),
        "metin": parsed.get("metin") or "",
        "imza_ad": parsed.get("imza_ad") or "Yetkili",
        "imza_unvan": parsed.get("imza_unvan") or makam,
        "olur_ad": parsed.get("olur_ad") or "",
        "olur_unvan": parsed.get("olur_unvan") or "",
        "ekler": parsed.get("ekler"),
        "dagitim": parsed.get("dagitim"),
        "onay_notu": parsed.get("onay_notu") or "",
    }


def render_belge(spec: dict[str, Any], parsed: dict[str, Any]) -> str:
    from llm.layouts import petition_view as build_view, render_petition_text

    if spec.get("family") == "kamu":
        from llm.resmi_yazisma import render_resmi_yazi

        variant = str(spec.get("resmi_sablon") or spec.get("id") or "ust_yazi")
        return render_resmi_yazi(variant, _kamu_parsed(spec, parsed))
    return render_petition_text(build_view(spec, parsed))


def petition_view(spec: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    from llm.layouts import petition_view as build_view

    return build_view(spec, parsed)


def render_islem_module(parsed: dict[str, Any]) -> str:
    blocks = [
        "T.C.",
        str(parsed.get("makam") or "İLGİLİ MAKAM").upper(),
        "",
        str(parsed.get("konu") or ""),
        "",
        str(parsed.get("aciklama") or ""),
        "",
    ]
    tespitler = parsed.get("tespitler") or []
    if tespitler:
        blocks.append("TESPİTLER")
        for item in tespitler:
            blocks.append(f"- {item}")
        blocks.append("")
    if parsed.get("sure_cumlesi"):
        blocks.extend([str(parsed["sure_cumlesi"]), ""])
    blocks.extend(
        [
            "SONUÇ VE TALEP",
            str(parsed.get("talep") or ""),
            "",
            str(parsed.get("onay_notu") or "Taslaktır. UYAP’a otomatik gönderim yoktur."),
        ]
    )
    return _lines(*blocks)
