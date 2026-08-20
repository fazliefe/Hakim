from __future__ import annotations

from document_ai.classify import classify_document
from document_ai.extract import extract_fields, extract_resmi_body, missing_fields
from document_ai.pipeline import analyze_document


def test_parses_ust_yazi_sayi_konu() -> None:
    text = (
        "T.C.\nANKARA VALİLİĞİ\n"
        "Sayı: E-06.01.2026-1240\n"
        "Konu: Evrak havalesi\n"
        "ÜST YAZI\n"
        "Evrak havale olunur."
    )
    fields = extract_fields(text)
    assert fields["sayi"] == "E-06.01.2026-1240"
    assert fields["konu"] == "Evrak havalesi"
    assert fields["kurum"] == "ANKARA VALİLİĞİ"
    assert missing_fields("ust_yazi", fields) == []


def test_missing_konu_on_olur() -> None:
    text = "T.C.\nANKARA VALİLİĞİ\nOLUR\nMakamın oluruna arz olunur. Olura arz ederim."
    fields = extract_fields(text)
    assert "Konu" in missing_fields("olur", fields)


def test_layout_without_title_is_ust_yazi() -> None:
    text = "T.C.\nANKARA VALİLİĞİ\nSayı: E-1\nKonu: Bilgi\nGereğini rica ederim."
    assert classify_document(text).document_type == "ust_yazi"


def test_analyze_exposes_fields_and_missing() -> None:
    analysis = analyze_document(
        "T.C.\nANKARA VALİLİĞİ\nCEVAP YAZISI\nYazınıza cevaben işlem tamamlanmıştır."
    )
    assert analysis.classification.document_type == "cevap_yazisi"
    assert "İlgi" in analysis.missing
    assert analysis.verdict
    assert "Cevap yazısı" in analysis.verdict


def test_extract_resmi_body_skips_header_blocks() -> None:
    text = (
        "T.C.\nANKARA VALİLİĞİ\n"
        "Sayı : E-99\nKonu : Havale\n\n"
        "MALİ HİZMETLER MÜDÜRLÜĞÜNE\n"
        "İlgi : 1 sayılı yazı.\n\n"
        "İlgi yazı gereği havalesi uygun görülmüştür."
    )
    body = extract_resmi_body(text)
    assert "havalesi uygun" in body.lower()
    assert "T.C." not in body
    assert "E-99" not in body
