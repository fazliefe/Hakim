from __future__ import annotations

from llm.formats import load_belge
from llm.render import render_belge
from llm.resmi_yazisma import load_sablon, render_resmi_yazi, variant_for_document_type


def test_sablon_block_order_ust_yazi() -> None:
    sablon = load_sablon()
    variant = sablon["varyantlar"]["ust_yazi"]
    assert variant["blok_sirasi"] == [
        "baslik",
        "sayi_konu",
        "muhatap",
        "ilgi",
        "metin",
        "imza",
        "ek",
        "dagitim",
        "onay",
    ]


def test_render_ust_yazi_follows_2646_layout() -> None:
    spec = load_belge("ust_yazi")
    text = render_belge(spec, spec["example"])
    assert text.index("T.C.") < text.index("Sayı\t:") < text.index("Konu\t:")
    assert text.index("Konu\t:") < text.index("İLGİLİ BİRİM")
    assert text.index("İLGİLİ BİRİM") < text.index("İlgi\t:")
    assert text.index("İlgi\t:") < text.index("Gereğini rica ederim")
    assert "Dağıtım:" in text
    assert "Gereği:" in text
    assert "Ek:" in text


def test_render_olur_has_olur_block() -> None:
    spec = load_belge("olur")
    text = render_belge(spec, spec["example"])
    assert "MAKAMINA" in text
    assert text.index("arz ederim") < text.index("OLUR")
    assert "Bakan" in text


def test_render_cevap_yazisi_ilgi_before_metin() -> None:
    spec = load_belge("cevap_yazisi")
    text = render_belge(spec, spec["example"])
    assert text.index("İlgi\t:") < text.index("arz ederim")


def test_variant_for_document_type() -> None:
    assert variant_for_document_type("olur") == "olur"
    assert variant_for_document_type("genelge") == "bilgi_yazisi"
    assert variant_for_document_type("cevap_yazisi") == "cevap_yazisi"


def test_render_resmi_yazi_multi_ilgi() -> None:
    text = render_resmi_yazi(
        "ust_yazi",
        {
            "kurum": "Test Bakanlığı",
            "sayi": "1",
            "tarih": "2026-08-18",
            "konu": "Test",
            "muhatap": "MUHATABA",
            "ilgi_listesi": [
                "01.01.2026 tarihli ve 1 sayılı yazı.",
                "02.01.2026 tarihli ve 2 sayılı yazı.",
            ],
            "metin": "Gereği için.",
        },
    )
    assert "a)" in text
    assert "b)" in text


def test_kamu_draft_takes_fields_from_incoming_evrak(monkeypatch) -> None:
    from llm import writer as writer_mod
    from llm.writer import write_belge

    monkeypatch.setattr(writer_mod, "api_configured", lambda: False)
    monkeypatch.setattr(writer_mod, "ollama_enabled", lambda: False)
    evrak = (
        "T.C.\nANKARA VALİLİĞİ\n"
        "Sayı : E-99887766-804.02-15\n"
        "Konu : Personel görevlendirme\n\n"
        "MALİ HİZMETLER MÜDÜRLÜĞÜNE\n"
        "İlgi : 01.08.2026 tarihli ve E-1 sayılı yazı.\n\n"
        "İlgi yazı gereği personel görevlendirmesi uygun görülmüştür."
    )
    text = write_belge(
        "ust_yazi",
        {
            "user_text": evrak,
            "fields": {
                "sayi": "E-99887766-804.02-15",
                "konu": "Personel görevlendirme",
                "muhatap": "MALİ HİZMETLER MÜDÜRLÜĞÜNE",
                "kurum": "ANKARA VALİLİĞİ",
                "ilgi": "01.08.2026 tarihli ve E-1 sayılı yazı.",
            },
            "classification": {
                "document_type": "ust_yazi",
                "label": "Üst yazı",
                "unit": "Evrak kayıt ve havale",
            },
        },
    )
    assert text is not None
    assert "E-99887766-804.02-15" in text
    assert "MALİ HİZMETLER MÜDÜRLÜĞÜNE" in text
    assert "Personel görevlendirme" in text
    assert "E-12345678" not in text
    assert "personel görevlendirmesi uygun" in text.lower()
    assert "TESPİTLER" not in text
