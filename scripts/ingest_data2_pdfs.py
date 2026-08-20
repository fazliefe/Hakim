#!/usr/bin/env python3
"""Parse PDFs under data2/ (or --input): text-layer first, OCR fallback, madde chunks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "services"),
    str(ROOT / "connectors"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

from document_ai.pdf_ocr import (
    PdfExtractResult,
    extract_pdf_bytes,
    ocr_available,
    paddle_ocr_available,
    tesseract_ocr_available,
)
from ingestion.pdf_law_chunker import _slug, chunk_pdf_text, write_bundle

OCR_WORK = ROOT / "data" / "raw" / "pdf_ocr_work"
OCR_WORK_ROOTS = [
    ROOT / "pdf_ocr_work",
    OCR_WORK,
]


def _norm_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _slug(name))


def find_ocr_work(pdf: Path) -> Path | None:
    """Locate Colab/local OCR folder; slugs may differ (unicode hyphens)."""
    want = _slug(pdf.name)
    want_n = _norm_key(pdf.name)
    loose: list[Path] = []
    for root in OCR_WORK_ROOTS:
        if not root.exists():
            continue
        direct = root / want
        if (direct / "content.txt").exists():
            return direct
        for folder in root.iterdir():
            if not folder.is_dir() or not (folder / "content.txt").exists():
                continue
            src = ""
            done = folder / "done.json"
            if done.exists():
                try:
                    src = str(json.loads(done.read_text(encoding="utf-8")).get("source") or "")
                except Exception:
                    src = ""
            if Path(src).name.casefold() == pdf.name.casefold():
                return folder
            if _norm_key(folder.name) == want_n:
                loose.append(folder)
    return loose[0] if loose else None


def _write_one(pdf: Path, extracted: PdfExtractResult, *, out_root: Path, day: str) -> None:
    print(f"  method={extracted.method} pages={extracted.pages} chars={len(extracted.text)} note={extracted.note}")
    if not extracted.text.strip():
        print("  SKIP: no text")
        return
    bundle = chunk_pdf_text(
        extracted.text,
        source_file=pdf.name,
        extract_method=extracted.method,
        pages=extracted.pages,
        note=extracted.note,
    )
    out_dir = out_root / _slug(pdf.name) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "content.txt").write_text(extracted.text, encoding="utf-8")
    (out_dir / "source.pdf").write_bytes(pdf.read_bytes())
    write_bundle(bundle, out_dir)
    print(
        f"  law_no={bundle.law_no} doc={bundle.document_id} "
        f"chunks={len(bundle.chunks)} "
        f"articles={sum(1 for c in bundle.chunks if c.kind == 'article')}"
    )
    print(f"  wrote {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR/parse/chunk law PDFs one by one")
    parser.add_argument("--input", type=Path, default=ROOT / "data2", help="Folder of PDFs")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "raw" / "pdf_laws",
        help="Archive root for content.txt + chunks.jsonl",
    )
    parser.add_argument("--prefer-ocr", action="store_true")
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument(
        "--max-ocr-pages",
        type=int,
        default=0,
        help="OCR page cap; 0 = entire PDF",
    )
    parser.add_argument("--limit", type=int, default=0, help="Process only first N PDFs (0=all)")
    parser.add_argument("--only", type=str, default="", help="Substring filter on PDF filename")
    parser.add_argument(
        "--from-ocr-work",
        action="store_true",
        help="Chunk already-OCR'd texts from data/raw/pdf_ocr_work (no new OCR)",
    )
    args = parser.parse_args()

    pdfs = sorted(args.input.glob("*.pdf"), key=lambda p: p.stat().st_size)
    if args.only:
        needle = args.only.casefold()
        pdfs = [p for p in pdfs if needle in p.name.casefold()]
    if args.limit > 0:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        print(f"No PDFs in {args.input}")
        return

    print(
        f"OCR available: {ocr_available()} "
        f"(paddle={paddle_ocr_available()}, tesseract={tesseract_ocr_available()})"
    )
    print(f"Found {len(pdfs)} PDF(s) in {args.input}")
    day = date.today().isoformat()

    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        work_dir = find_ocr_work(pdf) if args.from_ocr_work else (OCR_WORK / _slug(pdf.name))
        if args.from_ocr_work:
            if work_dir is None:
                print("  SKIP: OCR work not ready")
                continue
            content = work_dir / "content.txt"
            pages = 0
            engine = "paddleocr-gpu"
            done = work_dir / "done.json"
            if done.exists():
                meta = json.loads(done.read_text(encoding="utf-8"))
                pages = int(meta.get("pages_total") or 0)
                engine = str(meta.get("engine") or engine)
            extracted = PdfExtractResult(
                text=content.read_text(encoding="utf-8"),
                method="ocr",
                pages=pages,
                note=f"{engine} pages all from {work_dir.name}",
            )
            _write_one(pdf, extracted, out_root=args.out, day=day)
            continue

        data = pdf.read_bytes()
        extracted = extract_pdf_bytes(
            data,
            min_chars=args.min_chars,
            prefer_ocr=args.prefer_ocr,
            max_ocr_pages=args.max_ocr_pages,
            pdf_path=pdf,
            work_dir=work_dir if args.prefer_ocr else None,
        )
        _write_one(pdf, extracted, out_root=args.out, day=day)


if __name__ == "__main__":
    main()
