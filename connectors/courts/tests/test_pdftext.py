from __future__ import annotations

from courts.pdftext import looks_like_pdf, pdf_to_text


def test_looks_like_pdf() -> None:
    assert looks_like_pdf(b"%PDF-1.4\n")
    assert not looks_like_pdf(b"<html></html>")


def test_pdf_to_text_empty_on_html() -> None:
    assert pdf_to_text(b"<html>not a pdf</html>") == ""
