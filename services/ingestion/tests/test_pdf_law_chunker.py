from __future__ import annotations

from ingestion.pdf_law_chunker import chunk_pdf_text


SAMPLE = """
BİLGİ EDİNME HAKKI KANUNU
Kanun Numarası : 4982
Kabul Tarihi : 9/10/2003

Madde 1- Bu Kanunun amacı, bilgi edinme hakkının kullanımına ilişkin esasları düzenlemektir.

Madde 2- Bu Kanun, kamu kurum ve kuruluşlarını kapsar.

Madde 3- Tanımlar bu maddede yer alır.
"""


def test_chunk_pdf_text_splits_articles() -> None:
    bundle = chunk_pdf_text(
        SAMPLE,
        source_file="bilgi edinme kanunu.pdf",
        extract_method="text_layer",
        pages=1,
    )
    assert bundle.law_no == "4982"
    assert bundle.document_id == "law:4982"
    assert len(bundle.chunks) >= 3
    assert all(c.kind == "article" for c in bundle.chunks)
    assert bundle.chunks[0].article_no == "1"
    assert "bilgi edinme" in bundle.chunks[0].body.lower()


def test_chunk_fallback_windows_without_articles() -> None:
    text = "Bu metinde madde basligi yok. " * 200
    bundle = chunk_pdf_text(text, source_file="notlar.pdf", extract_method="text_layer", pages=1)
    assert bundle.chunks
    assert bundle.chunks[0].kind == "text_window"
