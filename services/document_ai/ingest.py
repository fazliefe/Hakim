from __future__ import annotations

from dataclasses import dataclass

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

    raise UploadError("Yalnızca PDF veya TXT kabul edilir.")
