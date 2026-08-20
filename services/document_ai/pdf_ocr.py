from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "scripts" / "paddle_ocr_worker.py"
OCR_VENV_PY = ROOT / ".venv-ocr" / ("Scripts" if os.name == "nt" else "bin") / (
    "python.exe" if os.name == "nt" else "python"
)


@dataclass(frozen=True, slots=True)
class PdfExtractResult:
    text: str
    method: str  # "text_layer" | "ocr" | "empty"
    pages: int
    note: str = ""


def _default_tesseract_cmd() -> str | None:
    env = os.environ.get("TESSERACT_CMD") or os.environ.get("HAKIM_TESSERACT_CMD")
    if env and Path(env).exists():
        return env
    which = shutil.which("tesseract")
    if which:
        return which
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _configure_tesseract() -> str | None:
    cmd = _default_tesseract_cmd()
    if not cmd:
        return None
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = cmd
    except ImportError:
        return None
    return cmd


def _pdf_page_count(data: bytes) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return 0


def extract_pdf_text_layer(data: bytes, *, max_pages: int | None = None) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]
    parts: list[str] = []
    for page in pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip(), len(reader.pages)


def paddle_ocr_available() -> bool:
    return OCR_VENV_PY.exists() and WORKER.exists()


def tesseract_ocr_available() -> bool:
    if _configure_tesseract() is None:
        return False
    try:
        import fitz  # noqa: F401
        import pytesseract  # noqa: F401

        return True
    except ImportError:
        return False


def ocr_available() -> bool:
    return paddle_ocr_available() or tesseract_ocr_available()


def extract_pdf_ocr_paddle(
    data: bytes,
    *,
    max_pages: int = 0,
    dpi: int = 180,
    pdf_path: Path | None = None,
    work_dir: Path | None = None,
) -> str:
    """Render+OCR via dedicated Python 3.12 venv (PaddleOCR). max_pages=0 means all."""
    if not paddle_ocr_available():
        raise RuntimeError("PaddleOCR venv (.venv-ocr) or worker script missing")

    tmp_path: Path | None = None
    if pdf_path is None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        pdf_path = tmp_path
    cmd = [
        str(OCR_VENV_PY),
        str(WORKER),
        str(pdf_path),
        "--max-pages",
        str(max_pages),
        "--dpi",
        str(dpi),
    ]
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--work-dir", str(work_dir)])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=None,
            check=False,
        )
        if work_dir is not None:
            content = work_dir / "content.txt"
            if content.exists():
                return content.read_text(encoding="utf-8").strip()
        if proc.returncode != 0 and not (proc.stdout or "").strip():
            err = (proc.stderr or proc.stdout or "paddleocr failed").strip()
            raise RuntimeError(err[:800])
        return (proc.stdout or "").strip()
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def extract_pdf_ocr_tesseract(
    data: bytes, *, max_pages: int = 40, lang: str = "tur+eng", dpi: int = 200
) -> str:
    """Render PDF pages with PyMuPDF, then Tesseract OCR."""
    import fitz
    import pytesseract
    from PIL import Image

    cmd = _configure_tesseract()
    if not cmd:
        raise RuntimeError("tesseract not found")

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        limit = len(doc) if max_pages <= 0 else min(len(doc), max_pages)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        parts: list[str] = []
        for i in range(limit):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            # Prefer tur+eng; fall back to eng if Turkish data missing
            try:
                parts.append(pytesseract.image_to_string(image, lang=lang) or "")
            except pytesseract.TesseractError:
                parts.append(pytesseract.image_to_string(image, lang="eng") or "")
        return "\n".join(parts).strip()
    finally:
        doc.close()


def extract_pdf_ocr(data: bytes, *, max_pages: int = 0, **kwargs) -> tuple[str, str]:
    """Return (text, engine_note). Prefer PaddleOCR, then Tesseract."""
    page_note = "all" if max_pages <= 0 else f"<={max_pages}"
    if paddle_ocr_available():
        text = extract_pdf_ocr_paddle(
            data,
            max_pages=max_pages,
            pdf_path=kwargs.get("pdf_path"),
            work_dir=kwargs.get("work_dir"),
        )
        return text, f"paddleocr+pymupdf pages {page_note}"
    text = extract_pdf_ocr_tesseract(data, max_pages=max_pages)
    return text, f"tesseract+pymupdf lang=tur+eng pages {page_note}"


def extract_pdf_bytes(
    data: bytes,
    *,
    min_chars: int = 200,
    prefer_ocr: bool = False,
    max_ocr_pages: int = 0,
    pdf_path: Path | None = None,
    work_dir: Path | None = None,
) -> PdfExtractResult:
    pages = _pdf_page_count(data)
    if not prefer_ocr:
        try:
            text, pages = extract_pdf_text_layer(data)
            layer_note = "pypdf"
        except Exception as exc:
            text, layer_note = "", f"text_layer_error: {exc}"
        if len(text) >= min_chars:
            return PdfExtractResult(text=text, method="text_layer", pages=pages, note=layer_note)

    if ocr_available():
        try:
            ocr_text, engine_note = extract_pdf_ocr(
                data,
                max_pages=max_ocr_pages,
                pdf_path=pdf_path,
                work_dir=work_dir,
            )
        except Exception as exc:
            return PdfExtractResult(text="", method="empty", pages=pages, note=f"ocr_failed: {exc}")
        if len(ocr_text) >= min_chars:
            return PdfExtractResult(text=ocr_text, method="ocr", pages=pages, note=engine_note)
        return PdfExtractResult(text=ocr_text, method="empty", pages=pages, note="ocr_too_short")

    return PdfExtractResult(
        text="",
        method="empty",
        pages=pages,
        note="OCR yok: PaddleOCR (.venv-ocr) veya Tesseract yok; metin katmanı da yetersiz.",
    )


def extract_pdf_path(path: str | bytes, **kwargs) -> PdfExtractResult:
    if isinstance(path, bytes):
        return extract_pdf_bytes(path, **kwargs)
    data = Path(path).read_bytes()
    return extract_pdf_bytes(data, **kwargs)
