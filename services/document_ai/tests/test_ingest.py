from document_ai.ingest import UploadError, extract_upload


def test_extract_txt_keeps_turkish() -> None:
    raw = "Gerekçeli karar. Tebliğ tarihi: 14.08.2026\n".encode("utf-8")
    out = extract_upload("karar.txt", raw)
    assert out.kind == "txt"
    assert "Gerekçeli" in out.text
    assert out.filename == "karar.txt"


def test_extract_docx_keeps_turkish() -> None:
    import io
    import zipfile

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Gerekçeli karar. Tebliğ tarihi: 14.08.2026</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    out = extract_upload("karar.docx", buffer.getvalue())
    assert out.kind == "docx"
    assert "Gerekçeli" in out.text


def test_extract_png_uses_vlm(monkeypatch) -> None:
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    monkeypatch.setattr(
        "document_ai.vlm_ocr.transcribe_images",
        lambda _images: "El yazısı tutanak. Tarih 14.08.2026.",
    )
    out = extract_upload("tutanak.png", png)
    assert out.kind == "image"
    assert "El yazısı" in out.text
    assert "Evren" in out.note or "görüntü" in out.note.lower() or "vlm" in out.note.lower() or "llm-fast" in out.note


def test_extract_rejects_broken_image() -> None:
    try:
        extract_upload("scan.png", b"not-an-image")
    except UploadError as exc:
        msg = str(exc).lower()
        assert "görüntü" in msg or "resim" in msg or "foto" in msg
    else:
        raise AssertionError("expected UploadError")


def test_extract_rejects_unknown_extension() -> None:
    try:
        extract_upload("virus.exe", b"MZ")
    except UploadError as exc:
        assert "PDF" in str(exc) or "TXT" in str(exc) or "görüntü" in str(exc).lower()
    else:
        raise AssertionError("expected UploadError")


def test_extract_pdf_without_text_does_not_use_vlm(monkeypatch) -> None:
    from document_ai.pdf_ocr import PdfExtractResult

    monkeypatch.setattr(
        "document_ai.pdf_ocr.extract_pdf_bytes",
        lambda *_a, **_k: PdfExtractResult(text="", method="empty", pages=1, note="ocr_too_short"),
    )

    def boom(_data):
        raise AssertionError("PDF must not call VLM")

    monkeypatch.setattr("document_ai.vlm_ocr.transcribe_pdf_bytes", boom)
    try:
        extract_upload("tarama.pdf", b"%PDF-1.4 scanned")
    except UploadError as exc:
        assert "PDF" in str(exc) or "metin" in str(exc).lower()
    else:
        raise AssertionError("expected UploadError")


def test_extract_rejects_unreadable_pdf() -> None:
    try:
        extract_upload("bos.pdf", b"%PDF-1.4 empty")
    except UploadError as exc:
        msg = str(exc).lower()
        assert "pdf" in msg or "metin" in msg or "taran" in msg
    else:
        raise AssertionError("expected UploadError")
