from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from hakim_legal_schema.ids import article_id, article_version_id, law_id

# PDF satır kırılımlarına toleranslı madde başlığı.
ARTICLE_HEAD_RE = re.compile(
    r"(?m)^(?:Ek\s+)?(?:Ge[cç]ici\s+)?Madde\s+([0-9]+(?:/[A-Za-z])?)\s*[-–—.:)]*\s*(.*)$",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"Kanun\s+Numaras[ıi]\s*:\s*([0-9]+)", re.IGNORECASE)
TITLE_LINE_RE = re.compile(r"^[A-ZÇĞİÖŞÜÂÊÎÔÛ0-9\s,'’\-()]{8,}$")
FALLBACK_CHUNK = 1800
FALLBACK_OVERLAP = 200


@dataclass(slots=True)
class TextChunk:
    chunk_id: str
    document_id: str
    law_no: str | None
    article_no: str | None
    title: str | None
    body: str
    kind: str  # article | window_window
    source_method: str
    ordinal: int


@dataclass(slots=True)
class PdfLawBundle:
    document_id: str
    law_no: str | None
    title: str
    source_file: str
    content_hash: str
    extract_method: str
    pages: int
    note: str
    chunks: list[TextChunk]
    full_text_path: str | None = None


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
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "doc"


def _guess_title(text: str, fallback: str) -> str:
    for line in text.splitlines()[:40]:
        clean = " ".join(line.split())
        if len(clean) < 8:
            continue
        if "KANUN" in clean.upper() or "ANAYASA" in clean.upper():
            return clean[:180]
        if TITLE_LINE_RE.match(clean) and "MADDE" not in clean.upper():
            return clean[:180]
    return fallback


def _split_articles(text: str, *, law_no: str) -> list[TextChunk]:
    matches = list(ARTICLE_HEAD_RE.finditer(text))
    if len(matches) < 2:
        return []
    chunks: list[TextChunk] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        article_no = match.group(1)
        rest = (match.group(2) or "").strip()
        title = rest[:120] if rest and len(rest) < 120 else None
        doc_id = law_id(law_no)
        chunks.append(
            TextChunk(
                chunk_id=article_version_id(law_no, article_no, 1),
                document_id=doc_id,
                law_no=law_no,
                article_no=article_no,
                title=title,
                body=body,
                kind="article",
                source_method="",
                ordinal=i + 1,
            )
        )
    return chunks


def _window_chunks(text: str, *, document_id: str, law_no: str | None) -> list[TextChunk]:
    body = " ".join(text.split())
    if not body:
        return []
    chunks: list[TextChunk] = []
    start = 0
    n = 1
    while start < len(body):
        end = min(len(body), start + FALLBACK_CHUNK)
        piece = body[start:end].strip()
        if piece:
            chunks.append(
                TextChunk(
                    chunk_id=f"{document_id}:window:{n}",
                    document_id=document_id,
                    law_no=law_no,
                    article_no=None,
                    title=f"Parça {n}",
                    body=piece,
                    kind="text_window",
                    source_method="",
                    ordinal=n,
                )
            )
            n += 1
        if end >= len(body):
            break
        start = max(0, end - FALLBACK_OVERLAP)
    return chunks


def chunk_pdf_text(
    text: str,
    *,
    source_file: str,
    extract_method: str,
    pages: int,
    note: str = "",
) -> PdfLawBundle:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    law_match = NUMBER_RE.search(text[:4000])
    law_no = law_match.group(1) if law_match else None
    title = _guess_title(text, Path(source_file).stem)
    if law_no:
        document_id = law_id(law_no)
        chunks = _split_articles(text, law_no=law_no)
        if not chunks:
            chunks = _window_chunks(text, document_id=document_id, law_no=law_no)
    else:
        document_id = f"pdf:{_slug(source_file)}"
        chunks = _window_chunks(text, document_id=document_id, law_no=None)

    for chunk in chunks:
        chunk.source_method = extract_method

    return PdfLawBundle(
        document_id=document_id,
        law_no=law_no,
        title=title,
        source_file=source_file,
        content_hash=content_hash,
        extract_method=extract_method,
        pages=pages,
        note=note,
        chunks=chunks,
    )


def write_bundle(bundle: PdfLawBundle, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "document_id": bundle.document_id,
        "law_no": bundle.law_no,
        "title": bundle.title,
        "source_file": bundle.source_file,
        "content_hash": bundle.content_hash,
        "extract_method": bundle.extract_method,
        "pages": bundle.pages,
        "note": bundle.note,
        "chunk_count": len(bundle.chunks),
        "article_chunks": sum(1 for c in bundle.chunks if c.kind == "article"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "official": True,
        "kind": "pdf_law",
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    chunks_path = out_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as fh:
        for chunk in bundle.chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    return out_dir
