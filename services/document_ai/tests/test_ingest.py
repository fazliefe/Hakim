from document_ai.ingest import UploadError, extract_upload


def test_extract_txt_keeps_turkish() -> None:
    raw = "Gerekçeli karar. Tebliğ tarihi: 14.08.2026\n".encode("utf-8")
    out = extract_upload("karar.txt", raw)
    assert out.kind == "txt"
    assert "Gerekçeli" in out.text
    assert out.filename == "karar.txt"


def test_extract_rejects_unknown_extension() -> None:
    try:
        extract_upload("scan.png", b"not-a-pdf")
    except UploadError as exc:
        assert "PDF" in str(exc) or "TXT" in str(exc)
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
