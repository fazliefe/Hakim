from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from retrieval.embeddings import Embedder, HashingEmbedder
from retrieval.mapping import INDEX_NAME, chunk_from_article_row, chunk_from_decision_row, index_settings

logger = logging.getLogger(__name__)


ARTICLE_SQL = """
SELECT
    a.id AS article_id,
    a.document_id,
    a.article_no,
    av.version,
    av.title,
    av.body,
    av.valid_from,
    av.valid_until,
    ld.document_type,
    ld.number AS law_no,
    s.provider AS source_provider,
    s.authority::text AS authority
FROM article_versions av
JOIN articles a ON a.id = av.article_id
JOIN legal_documents ld ON ld.id = a.document_id
JOIN sources s ON s.id = ld.source_id
WHERE av.valid_until IS NULL
  AND (%s::text IS NULL OR a.document_id = %s)
ORDER BY a.document_id, a.article_no
"""


class LegalChunkIndexer:
    def __init__(
        self,
        es_client: Any,
        *,
        index_name: str = INDEX_NAME,
        embedder: Embedder | None = None,
        batch_size: int = 32,
        settings_builder: Callable[..., dict[str, Any]] = index_settings,
    ) -> None:
        self.es = es_client
        self.index_name = index_name
        self.embedder = embedder or HashingEmbedder()
        self.batch_size = batch_size
        # Karar index'i (`hakim-court-decisions`) `chamber`/`docket_no` alanları
        # eklenmiş ayrı bir şema (`mapping.decision_index_settings`) kullanır —
        # kanun index'inin `INDEX_SETTINGS`'ine dokunmadan.
        self._settings_builder = settings_builder

    def ensure_index(self, *, recreate: bool = False) -> None:
        exists = self.es.indices.exists(index=self.index_name)
        if exists and recreate:
            self.es.indices.delete(index=self.index_name)
            exists = False
        if not exists:
            self.es.indices.create(index=self.index_name, body=self._settings_builder(dims=self.embedder.dims))

    def index_rows(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        model_name = getattr(self.embedder, "model_name", type(self.embedder).__name__)
        for start in range(0, len(rows), self.batch_size):
            batch = rows[start : start + self.batch_size]
            texts = [
                f"{row.get('title') or ''}\n{row.get('body') or ''}".strip()
                for row in batch
            ]
            vectors = self.embedder.embed(texts)
            operations: list[dict[str, Any]] = []
            for row, vector in zip(batch, vectors, strict=True):
                doc = chunk_from_article_row(
                    row, embedding=vector, embedding_model=str(model_name)
                )
                operations.append({"index": {"_index": self.index_name, "_id": doc["chunk_id"]}})
                operations.append(doc)
            # Bulk isteği HER batch için ayrı gönderilir — tümünü tek seferde
            # biriktirip en sonda göndermek büyük korpuslarda (örn. 11K+ emsal
            # karar) ES'in/proxy'nin gövde boyutu sınırını (413) aşıyor;
            # canlı doğrulandı.
            self.es.bulk(operations=operations, refresh=True)
        return len(rows)

    def index_from_postgres(self, conn, *, document_id: str | None = None) -> int:
        rows = conn.execute(ARTICLE_SQL, (document_id, document_id)).fetchall()
        cols = [
            "article_id",
            "document_id",
            "article_no",
            "version",
            "title",
            "body",
            "valid_from",
            "valid_until",
            "document_type",
            "law_no",
            "source_provider",
            "authority",
        ]
        dict_rows = [dict(zip(cols, row, strict=True)) for row in rows]
        self.ensure_index()
        return self.index_rows(dict_rows)

    def _existing_chunk_ids(self) -> set[str]:
        """Index'te zaten var olan chunk_id'ler — `terms` aggregation ile
        (max_result_window sınırına takılmadan, `chunk_id` zaten keyword).
        Kesintiye uğrayan/artımlı çalıştırmalarda aynı kararı boşuna tekrar
        embed etmemek için (canlı doğrulandı: 11K+ karar sonrası yeni
        eklenenleri indekslerken tüm korpusu yeniden embed etmek saatler
        sürerdi)."""
        if not self.es.indices.exists(index=self.index_name):
            return set()
        try:
            response = self.es.search(
                index=self.index_name,
                size=0,
                aggs={"ids": {"terms": {"field": "chunk_id", "size": 100000}}},
            )
            buckets = response.get("aggregations", {}).get("ids", {}).get("buckets", [])
            return {b["key"] for b in buckets}
        except Exception:
            return set()

    def index_decisions_from_postgres(self, conn, *, skip_existing: bool = True) -> int:
        rows = conn.execute(
            """
            SELECT cd.id, cd.title, cd.body, cd.decision_no, cd.decision_date,
                   cd.court_id, c.slug AS court_slug, s.provider AS source_provider,
                   cd.chamber, cd.docket_no
            FROM court_decisions cd
            JOIN courts c ON c.id = cd.court_id
            JOIN sources s ON s.id = cd.source_id
            """
        ).fetchall()
        cols = [
            "id",
            "title",
            "body",
            "decision_no",
            "decision_date",
            "court_id",
            "court_slug",
            "source_provider",
            "chamber",
            "docket_no",
        ]
        dict_rows = [dict(zip(cols, row, strict=True)) for row in rows]
        self.ensure_index()
        if not dict_rows:
            return 0
        if skip_existing:
            existing = self._existing_chunk_ids()
            if existing:
                dict_rows = [row for row in dict_rows if f"{row['id']}:v1" not in existing]
            if not dict_rows:
                return 0
        model_name = getattr(self.embedder, "model_name", type(self.embedder).__name__)
        for start in range(0, len(dict_rows), self.batch_size):
            batch = dict_rows[start : start + self.batch_size]
            # Bazı kararlar (özellikle Ceza/Hukuk Genel Kurulu) 100K+ karakter
            # olabiliyor — canlı doğrulandı (200K+ karakterlik gerçek bir
            # karar Evren'in bge-m3-embed max_input_tokens=8192 sınırını aştı,
            # ContextWindowExceededError). Embedding sadece anlam yakalamak
            # için; tam metin zaten Postgres'te/ES `content` alanında duruyor.
            texts = [
                f"{row.get('title') or ''}\n{row.get('body') or ''}".strip()[:6000] for row in batch
            ]
            vectors = self.embedder.embed(texts)
            operations: list[dict[str, Any]] = []
            for row, vector in zip(batch, vectors, strict=True):
                doc = chunk_from_decision_row(row, embedding=vector, embedding_model=str(model_name))
                operations.append({"index": {"_index": self.index_name, "_id": doc["chunk_id"]}})
                operations.append(doc)
            # HER batch ayrı gönderilir — 11K+ karar tek istekte ES/proxy'nin
            # gövde boyutu sınırını (413) aşıyordu, canlı doğrulandı.
            self.es.bulk(operations=operations, refresh=True)
        return len(dict_rows)

    def index_pdf_law_jsonl(self, root: str | Path) -> int:
        """Index latest chunks.jsonl under data/raw/pdf_laws/<slug>/<date>/."""
        root = Path(root)
        if not root.exists():
            return 0
        rows: list[dict[str, Any]] = []
        for law_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            dated = sorted((p for p in law_dir.iterdir() if p.is_dir()), reverse=True)
            if not dated:
                continue
            path = dated[0] / "chunks.jsonl"
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                law_no = chunk.get("law_no")
                article_no = str(chunk.get("article_no") or chunk.get("ordinal") or "")
                rows.append(
                    {
                        "article_id": chunk.get("chunk_id", "").rsplit(":v", 1)[0]
                        or f"law:{law_no}:article:{article_no}",
                        "document_id": chunk.get("document_id") or (f"law:{law_no}" if law_no else ""),
                        "article_no": article_no,
                        "version": 1,
                        "title": chunk.get("title"),
                        "body": chunk.get("body") or "",
                        "valid_from": None,
                        "valid_until": None,
                        "document_type": "law",
                        "law_no": law_no,
                        "source_provider": "pdf_ocr",
                        "authority": "official",
                    }
                )
        self.ensure_index()
        logger.info("pdf_laws chunks=%d", len(rows))
        return self.index_rows(rows)
