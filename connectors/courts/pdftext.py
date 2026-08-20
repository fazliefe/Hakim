from __future__ import annotations

import io


def looks_like_pdf(data: bytes) -> bool:
    return data[:5].startswith(b"%PDF")


def pdf_to_text(data: bytes, *, max_pages: int = 12) -> str:
    if not looks_like_pdf(data):
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages[:max_pages]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
