from __future__ import annotations

from typing import Any


def _lines(*parts: str) -> str:
    return "\n".join(part for part in parts if part is not None)


def render_arastirma(parsed: dict[str, Any]) -> str:
    blocks = [str(parsed.get("ozet") or "").strip()]
    for item in parsed.get("gerekce") or []:
        if isinstance(item, dict):
            n = item.get("n")
            cumle = str(item.get("cumle") or "").strip()
            if not cumle:
                continue
            if n is not None and f"[{n}]" not in cumle:
                cumle = f"{cumle} [{n}]"
            blocks.append(cumle)
        else:
            blocks.append(str(item))
    ilgili_parts: list[str] = []
    for item in parsed.get("ilgili") or []:
        if isinstance(item, dict):
            n = item.get("n")
            neden = str(item.get("neden") or "").strip()
            if not neden:
                continue
            if n is not None and f"[{n}]" not in neden:
                neden = f"{neden} [{n}]"
            ilgili_parts.append(neden)
        else:
            ilgili_parts.append(str(item))
    if ilgili_parts:
        blocks.append("Ayrıca " + " ".join(ilgili_parts))
    uyari = str(parsed.get("kaynak_uyari") or "Bu metin yalnızca yukarıdaki resmi kaynaklara dayanır.")
    blocks.append(f"_{uyari}_")
    return "\n\n".join(part for part in blocks if part)


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
