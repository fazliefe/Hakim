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


def test_extract_udf_keeps_turkish() -> None:
    import io
    import zipfile

    content_xml = (
        '<?xml version="1.0" encoding="UTF-8" ?>'
        '<template format_id="1.8">'
        "<content><![CDATA[Gerekçeli karar. Tebliğ tarihi: 14.08.2026]]></content>"
        '<elements resolver="hvl-default">'
        '<paragraph Alignment="N" resolver="hvl-default">'
        '<content Alignment="N" resolver="hvl-default" bold="false" size="12" '
        'family="Times New Roman" foreground="-16777216" background="-1" '
        'startOffset="0" length="42" />'
        "</paragraph>"
        "</elements>"
        "</template>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content.xml", content_xml)
    out = extract_upload("karar.udf", buffer.getvalue())
    assert out.kind == "udf"
    assert "Gerekçeli" in out.text
    assert "startOffset" not in out.text


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
