from __future__ import annotations

import re
from typing import Any, Iterator

from elasticsearch.helpers import scan

SENT_RE = re.compile(r"(?<=[.!?])\s+")


def window_chunks(text: str, size: int, overlap: int) -> list[str]:
    blob = (text or "").strip()
    if not blob:
        return []
    if size <= 0 or len(blob) <= size:
        return [blob]
    step = max(size - overlap, 1)
    out: list[str] = []
    i = 0
    while i < len(blob):
        out.append(blob[i : i + size])
        i += step
    return out


def sentence_chunks(text: str, max_chars: int = 512) -> list[str]:
    blob = (text or "").strip()
    if not blob:
        return []
    parts = [p.strip() for p in SENT_RE.split(blob) if p.strip()]
    if not parts:
        return window_chunks(blob, max_chars, 0)
    packed: list[str] = []
    buf = ""
    for part in parts:
        if not buf:
            buf = part
        elif len(buf) + 1 + len(part) <= max_chars:
            buf = f"{buf} {part}"
        else:
            packed.append(buf)
            buf = part
    if buf:
        packed.append(buf)
    return packed


def iter_source_docs(es: Any, index: str) -> Iterator[dict[str, Any]]:
    for hit in scan(es, index=index, query={"query": {"match_all": {}}}):
        yield hit.get("_source") or {}


METHODS: dict[str, tuple[str, int, int]] = {
    "chunk256": ("window", 256, 0),
    "chunk512": ("window", 512, 0),
    "chunk1024": ("window", 1024, 0),
    "chunk512o64": ("window", 512, 64),
    "chunk_sent": ("sentence", 512, 0),
}


def split_doc(src: dict[str, Any], method: str) -> list[dict[str, Any]]:
    kind, size, overlap = METHODS[method]
    body = str(src.get("content") or "")
    pieces = sentence_chunks(body, size) if kind == "sentence" else window_chunks(body, size, overlap)
    rows: list[dict[str, Any]] = []
    base_id = str(src.get("article_id") or src.get("chunk_id") or "art")
    version = int(src.get("version") or 1)
    for i, piece in enumerate(pieces, start=1):
        rows.append(
            {
                "article_id": base_id,
                "document_id": src.get("document_id"),
                "article_no": src.get("article_no"),
                "version": version,
                "title": src.get("title"),
                "body": piece,
                "valid_from": None,
                "valid_until": None,
                "document_type": src.get("document_type") or "law",
                "law_no": src.get("law_no"),
                "source_provider": src.get("source_provider"),
                "authority": src.get("authority"),
                "_window": i,
            }
        )
    return rows


def ensure_chunk_index(es: Any, method: str, *, source_index: str = "hakim-legal-chunks") -> str:
    from retrieval.embeddings import HashingEmbedder
    from retrieval.indexer import LegalChunkIndexer
    from retrieval.mapping import chunk_from_article_row

    del chunk_from_article_row
    target = f"hakim-bench-{method}"
    if method not in METHODS:
        raise KeyError(method)
    if es.indices.exists(index=target):
        count = es.count(index=target).get("count") or 0
        if count:
            return target
    indexer = LegalChunkIndexer(es, index_name=target, embedder=HashingEmbedder())
    indexer.ensure_index(recreate=True)
    batch: list[dict[str, Any]] = []
    n = 0
    for src in iter_source_docs(es, source_index):
        for row in split_doc(src, method):
            row["chunk_id"] = f"{row['article_id']}:v{row['version']}:w{row['_window']}"
            batch.append(row)
            if len(batch) >= 32:
                n += _flush(indexer, batch)
                batch = []
                if n % 512 == 0:
                    print(f"chunk index {target}: {n}", flush=True)
    if batch:
        n += _flush(indexer, batch)
    es.indices.refresh(index=target)
    print(f"chunk index {target}: {n} windows", flush=True)
    return target


def _flush(indexer: Any, rows: list[dict[str, Any]]) -> int:
    from retrieval.mapping import chunk_from_article_row

    model_name = type(indexer.embedder).__name__
    texts = [f"{row.get('title') or ''}\n{row.get('body') or ''}".strip() for row in rows]
    vectors = indexer.embedder.embed(texts)
    operations: list[dict[str, Any]] = []
    for row, vector in zip(rows, vectors, strict=True):
        doc = chunk_from_article_row(row, embedding=vector, embedding_model=model_name)
        doc["chunk_id"] = row["chunk_id"]
        doc["content"] = row["body"]
        operations.append({"index": {"_index": indexer.index_name, "_id": row["chunk_id"]}})
        operations.append(doc)
    indexer.es.bulk(operations=operations, refresh=False)
    return len(rows)
