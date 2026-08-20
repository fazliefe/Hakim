#!/usr/bin/env python3
"""PaddleOCR worker (Python 3.12). One PDF or a whole folder; page-by-page with resume."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Windows/CPU: avoid Paddle 3.3 + oneDNN PIR crash before importing paddle.
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def _slug(name: str) -> str:
    stem = Path(name).stem
    folded = (
        stem.lower()
        .replace("ı", "i")
        .replace("İ", "i")
        .replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    import re

    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "doc"


def _lines_from_result(result) -> list[str]:
    lines: list[str] = []
    if result is None:
        return lines
    if isinstance(result, dict):
        for t in result.get("rec_texts") or result.get("texts") or []:
            if t:
                lines.append(str(t))
        return lines
    if hasattr(result, "get") and callable(result.get):
        texts = result.get("rec_texts") or result.get("texts")
        if texts:
            for t in texts:
                if t:
                    lines.append(str(t))
            return lines
    if hasattr(result, "rec_texts"):
        for t in result.rec_texts or []:
            if t:
                lines.append(str(t))
        return lines
    if isinstance(result, list):
        for item in result:
            if item is None:
                continue
            if isinstance(item, dict) or hasattr(item, "rec_texts") or hasattr(item, "get"):
                lines.extend(_lines_from_result(item))
                continue
            if isinstance(item, list):
                for row in item:
                    if not row:
                        continue
                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                        payload = row[1]
                        if isinstance(payload, (list, tuple)) and payload:
                            lines.append(str(payload[0]))
                        elif isinstance(payload, str):
                            lines.append(payload)
                    elif isinstance(row, str):
                        lines.append(row)
            elif isinstance(item, str):
                lines.append(item)
    return lines


def _page_image(doc, index: int, dpi: int):
    import pymupdf
    from PIL import Image

    zoom = dpi / 72.0
    page = doc.load_page(index)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


ROOT = Path(__file__).resolve().parents[1]


def _archive_ocr_content(pdf_path: Path) -> Path | None:
    """Reuse a finished OCR under data/raw/pdf_laws/<slug>/*/content.txt."""
    archive = ROOT / "data" / "raw" / "pdf_laws" / _slug(pdf_path.name)
    if not archive.exists():
        return None
    metas = sorted(archive.rglob("metadata.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for meta in metas:
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("extract_method") != "ocr":
            continue
        content = meta.parent / "content.txt"
        if content.exists() and content.stat().st_size > 200:
            return content
    return None


def _load_progress(work_dir: Path) -> dict:
    path = work_dir / "progress.json"
    if not path.exists():
        return {"done_pages": 0, "pages_total": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def ocr_pdf(
    ocr,
    pdf_path: Path,
    *,
    max_pages: int,
    dpi: int,
    work_dir: Path,
) -> str:
    import numpy as np
    import pymupdf

    work_dir.mkdir(parents=True, exist_ok=True)
    partial = work_dir / "partial.txt"
    progress_path = work_dir / "progress.json"
    done_path = work_dir / "done.json"

    if done_path.exists() and (work_dir / "content.txt").exists():
        print(f"[skip] already done: {pdf_path.name}", file=sys.stderr, flush=True)
        return (work_dir / "content.txt").read_text(encoding="utf-8")

    archived = _archive_ocr_content(pdf_path)
    if archived is not None:
        text = archived.read_text(encoding="utf-8")
        (work_dir / "content.txt").write_text(text, encoding="utf-8")
        done_path.write_text(
            json.dumps(
                {
                    "source": str(pdf_path),
                    "engine": "paddleocr",
                    "skipped": True,
                    "from": str(archived),
                    "chars": len(text),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[skip] reuse prior OCR: {pdf_path.name} ({archived})", file=sys.stderr, flush=True)
        return text

    doc = pymupdf.open(pdf_path)
    completed = False
    limit = 0
    total = 0
    try:
        total = len(doc)
        limit = total if max_pages <= 0 else min(total, max_pages)
        state = _load_progress(work_dir)
        start = int(state.get("done_pages") or 0)
        if start > limit:
            start = 0
            if partial.exists():
                partial.unlink()

        print(
            f"[ocr] {pdf_path.name} pages {start + 1}-{limit} / {total} dpi={dpi}",
            file=sys.stderr,
            flush=True,
        )
        t0 = time.time()
        for i in range(start, limit):
            image = _page_image(doc, i, dpi)
            result = ocr.predict(np.array(image))
            page_text = "\n".join(_lines_from_result(result)).strip()
            with partial.open("a", encoding="utf-8") as fh:
                if i > 0 or start > 0:
                    fh.write("\n\n")
                fh.write(page_text)
                fh.flush()
            elapsed = time.time() - t0
            per = elapsed / (i - start + 1)
            eta = per * (limit - i - 1)
            print(
                f"  page {i + 1}/{limit} chars={len(page_text)} "
                f"elapsed={elapsed:.0f}s eta={eta:.0f}s",
                file=sys.stderr,
                flush=True,
            )
            progress_path.write_text(
                json.dumps(
                    {
                        "done_pages": i + 1,
                        "pages_total": total,
                        "pages_ocr": limit,
                        "source": str(pdf_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        completed = True
    finally:
        doc.close()

    text = partial.read_text(encoding="utf-8").strip() if partial.exists() else ""
    if not completed:
        return text
    (work_dir / "content.txt").write_text(text, encoding="utf-8")
    done_path.write_text(
        json.dumps(
            {
                "source": str(pdf_path),
                "pages_ocr": limit,
                "pages_total": total,
                "chars": len(text),
                "engine": "paddleocr",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"# meta pages_ocr={limit} pages_total={total} engine=paddleocr chars={len(text)}",
        file=sys.stderr,
        flush=True,
    )
    return text


def _build_ocr(lang: str):
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang=lang,
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path, nargs="?")
    parser.add_argument("--batch-dir", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, default=None, help="Resume/work folder for one PDF")
    parser.add_argument("--out-root", type=Path, default=None, help="Batch work root (per-slug subdirs)")
    parser.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--lang", default="en")
    args = parser.parse_args()

    pdfs: list[Path] = []
    if args.batch_dir:
        pdfs = sorted(args.batch_dir.glob("*.pdf"), key=lambda p: p.stat().st_size)
        if not pdfs:
            print(f"no pdfs in {args.batch_dir}", file=sys.stderr)
            return 2
    elif args.pdf:
        if not args.pdf.exists():
            print(f"missing: {args.pdf}", file=sys.stderr)
            return 2
        pdfs = [args.pdf]
    else:
        parser.error("pdf path or --batch-dir required")

    ocr = _build_ocr(args.lang)
    sys.stdout.reconfigure(encoding="utf-8")

    last_text = ""
    failed = 0
    for pdf in pdfs:
        if args.batch_dir:
            root = args.out_root or (args.batch_dir.parent / "data" / "raw" / "pdf_ocr_work")
            work = root / _slug(pdf.name)
        else:
            work = args.work_dir or (pdf.parent / f".ocr-{_slug(pdf.name)}")
        try:
            last_text = ocr_pdf(
                ocr,
                pdf,
                max_pages=args.max_pages,
                dpi=args.dpi,
                work_dir=work,
            )
        except Exception as exc:
            failed += 1
            print(f"[fail] {pdf.name}: {exc}", file=sys.stderr, flush=True)

    if len(pdfs) == 1:
        print(last_text)
    if failed:
        print(f"[done] failed={failed}/{len(pdfs)}", file=sys.stderr, flush=True)
        return 1
    return 0 if last_text or args.batch_dir else 1


if __name__ == "__main__":
    raise SystemExit(main())
