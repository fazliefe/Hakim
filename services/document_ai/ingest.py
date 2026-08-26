from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MIN_TEXT_CHARS = 8


class UploadError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedEvrak:
    text: str
    filename: str
    kind: str
    note: str


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except Exception as exc:
        raise UploadError("Word dosyası okunamadı.") from exc
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for para in root.findall(".//w:p", ns):
        pieces = [(node.text or "") + (node.tail or "") for node in para.findall(".//w:t", ns)]
        line = "".join(pieces).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_udf(data: bytes) -> str:
    # UDF (UYAP Doküman Formatı) = ZIP içinde tek bir content.xml; kök
    # <template>'in DOĞRUDAN çocuğu olan <content> elemanı CDATA düz metni
    # taşır (bkz. apps/web/lib/exportDocument.ts::udfBlob — bu şemayı biz
    # üretiyoruz). <elements>/<paragraph> altındaki iç içe <content .../>
    # elemanları yalnızca biçimlendirme özniteliği taşır, metin değil —
    # root.find("content") (yalnızca doğrudan çocuklara bakar) bu ikisini
    # otomatik ayırır.
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("content.xml")
    except Exception as exc:
        raise UploadError("UDF dosyası okunamadı.") from exc
    try:
        root = ElementTree.fromstring(xml)
    except Exception as exc:
        raise UploadError("UDF içeriği (content.xml) çözümlenemedi.") from exc
    node = root.find("content")
    return (node.text or "").strip() if node is not None else ""


def extract_upload(filename: str, data: bytes) -> ExtractedEvrak:
    name = (filename or "evrak").strip() or "evrak"
    lower = name.lower()
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("Dosya 8 MB sınırını aşıyor.")
    if not data:
        raise UploadError("Dosya boş.")

    if lower.endswith(".pdf") or data.startswith(b"%PDF"):
        try:
            from document_ai.pdf_ocr import extract_pdf_bytes

            extracted = extract_pdf_bytes(data, min_chars=MIN_TEXT_CHARS)
            text = extracted.text.strip()
        except UploadError:
            raise
        except Exception as exc:
            raise UploadError("PDF okunamadı. Bozuk dosya veya taranmış sayfa olabilir.") from exc
        if len(text) < MIN_TEXT_CHARS:
            raise UploadError(
                "PDF’den metin çıkmadı. Taranmış sayfa olabilir; Tesseract OCR kurun "
                "veya metin-PDF / TXT yükleyin."
            )
        note = (
            "PDF metin katmanından okundu."
            if extracted.method == "text_layer"
            else f"PDF OCR ile okundu ({extracted.note})."
        )
        return ExtractedEvrak(text=text, filename=name, kind="pdf", note=note)

    if lower.endswith((".txt", ".md")):
        text = _decode_text(data).strip()
        if len(text) < MIN_TEXT_CHARS:
            raise UploadError("Metin dosyası çok kısa.")
        return ExtractedEvrak(text=text, filename=name, kind="txt", note="Düz metin okundu.")

    if lower.endswith(".docx"):
        text = _extract_docx(data)
        if len(text) < MIN_TEXT_CHARS:
            raise UploadError("Word dosyasından yeterli metin çıkmadı.")
        return ExtractedEvrak(text=text, filename=name, kind="docx", note="Word belgesi okundu.")

    if lower.endswith(".udf"):
        text = _extract_udf(data)
        if len(text) < MIN_TEXT_CHARS:
            raise UploadError("UDF dosyasından yeterli metin çıkmadı.")
        return ExtractedEvrak(text=text, filename=name, kind="udf", note="UDF (UYAP) belgesi okundu.")

    if lower.endswith(".doc"):
        raise UploadError("Eski .doc yerine .docx, PDF veya TXT yükleyin.")

    raise UploadError("Yalnızca PDF, Word (.docx), UDF veya TXT kabul edilir.")
