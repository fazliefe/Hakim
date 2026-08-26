from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

INDEX_NAME = "hakim-legal-chunks"
# Emsal karar (Yargıtay/Danıştay) index'i — kanun maddelerinden AYRI, çünkü
# Evren'in bge-m3-embed'i (1024 dims) yerel mursit modelinden (768 dims)
# farklı boyutta; aynı ES index'in dense_vector alanı tek boyut kabul eder.
DECISION_INDEX_NAME = "hakim-court-decisions"

# mevzuat.gov.tr, mülga (yürürlükten kalkmış) fıkra/bendi metin içinde
# "(Mülga: 2/7/2012-6352/105 md.)" gibi işaretler — kolon/boşluk varyasyonu
# değişebiliyor (bkz. "(Mülga:2/3/2024-7499/19 md.)"), o yüzden geniş eşleşme.
MULGA_RE = re.compile(r"\(\s*Mülga\b[^)]*\)", re.IGNORECASE)


def detect_mulga_warning(content: str, *, is_decision: bool = False) -> str | None:
    """Madde 2 (zamansal geçerlilik): arşivdeki her maddenin tek versiyonu
    olduğu için valid_from/valid_until filtresi bugün ayırt edici değil —
    ama mevzuat.gov.tr metninin kendisi zaten hangi fıkranın mülga olduğunu
    işaretliyor. Bunu kaçırmamak, güncel-olmayan bir hükmün taslakta dayanak
    gösterilmesini önler. Kesin hukuki tespit değildir; kullanıcıyı uyarır.

    `is_decision=True` emsal karar metinleri için — canlı doğrulandı: arşivdeki
    1.240 karar (çoğu eski Yargıtay kararı, örn. 765 sayılı mülga TCK'ya atıf
    yapanlar) bu taramayı tetikliyordu, ama "Bu madde... mülga" ifadesi bir
    KARARIN kendisi için yanıltıcı — kararın kendisi mülga olmaz, kararın
    andığı bir hüküm sonradan mülga olmuş olabilir. Mesaj buna göre ayrıldı."""
    text = (content or "").strip()
    if not text:
        return None
    matches = list(MULGA_RE.finditer(text))
    if not matches:
        return None
    covered = sum(m.end() - m.start() for m in matches)
    if covered >= len(text) * 0.6:
        if is_decision:
            return (
                "Bu kararda atıfta bulunulan hükümler büyük ölçüde mülga olmuş "
                "olabilir; güncel mevzuatla karşılaştırmadan dayanak göstermeyin."
            )
        return (
            "Bu madde tamamen mülga (yürürlükten kalkmış) olabilir; "
            "taslakta dayanak olarak kullanmadan önce güncel metni doğrulayın."
        )
    if is_decision:
        return (
            f"Bu kararda atıfta bulunulan bir hüküm mülga olmuş olabilir: "
            f"{matches[0].group(0)} — güncel mevzuatla karşılaştırmadan dayanak göstermeyin."
        )
    return (
        f"Bu maddenin bir kısmı mülga: {matches[0].group(0)} — "
        "ilgili fıkra güncel değil, dikkatli kullanın."
    )


def embedding_dims() -> int:
    from hakim_config import get_models

    return get_models().embedding_dims


EMBEDDING_DIMS = 768


def index_settings(*, dims: int | None = None) -> dict[str, Any]:
    settings = copy.deepcopy(INDEX_SETTINGS)
    settings["mappings"]["properties"]["embedding"]["dims"] = int(dims or embedding_dims())
    return settings


def decision_index_settings(*, dims: int) -> dict[str, Any]:
    """Emsal karar index'i için ayrı ayarlar — kanun index'inin (`INDEX_SETTINGS`)
    şemasına dokunmadan `chamber`/`docket_no` alanlarını ekler."""
    settings = index_settings(dims=dims)
    settings["mappings"]["properties"]["chamber"] = {"type": "keyword"}
    settings["mappings"]["properties"]["docket_no"] = {"type": "keyword"}
    return settings


def corpus_filters(*, law_no: str | None = None, at: datetime | None = None) -> list[dict[str, Any]]:
    """Restrict search to a law corpus while still including court decisions."""
    filters: list[dict[str, Any]] = []
    if law_no:
        filters.append(
            {
                "bool": {
                    "should": [
                        {"term": {"law_no": law_no}},
                        {"term": {"document_type": "court_decision"}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    if at is not None:
        filters.append({"range": {"valid_from": {"lte": at.isoformat()}}})
        filters.append(
            {
                "bool": {
                    "should": [
                        {"bool": {"must_not": {"exists": {"field": "valid_until"}}}},
                        {"range": {"valid_until": {"gt": at.isoformat()}}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )
    return filters

INDEX_SETTINGS: dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "filter": {
                "turkish_stop": {"type": "stop", "stopwords": "_turkish_"},
                "turkish_stemmer": {"type": "stemmer", "language": "turkish"},
            },
            "analyzer": {
                "hakim_turkish": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "turkish_stop", "turkish_stemmer", "asciifolding"],
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "article_id": {"type": "keyword"},
            "document_type": {"type": "keyword"},
            "law_no": {"type": "keyword"},
            "article_no": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "hakim_turkish",
                "fields": {"raw": {"type": "keyword"}},
            },
            "content": {"type": "text", "analyzer": "hakim_turkish"},
            "valid_from": {"type": "date"},
            "valid_until": {"type": "date"},
            "court": {"type": "keyword"},
            "authority": {"type": "keyword"},
            "source_provider": {"type": "keyword"},
            "version": {"type": "integer"},
            "indexed_at": {"type": "date"},
            "embedding": {
                "type": "dense_vector",
                "dims": EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
            "embedding_model": {"type": "keyword"},
        }
    },
}


def chunk_from_article_row(
    row: dict[str, Any],
    *,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> dict[str, Any]:
    """Build an ES document from a Postgres article_versions join row."""
    article_id = row["article_id"]
    version = int(row["version"])
    chunk_id = f"{article_id}:v{version}"
    valid_from: datetime | None = row.get("valid_from")
    valid_until: datetime | None = row.get("valid_until")
    doc: dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": row["document_id"],
        "article_id": article_id,
        "document_type": row.get("document_type") or "law",
        "law_no": row.get("law_no") or row.get("number"),
        "article_no": row["article_no"],
        "title": row.get("title"),
        "content": row["body"],
        "valid_from": valid_from.isoformat() if valid_from else None,
        "valid_until": valid_until.isoformat() if valid_until else None,
        "court": row.get("court"),
        "authority": row.get("authority") or "official",
        "source_provider": row.get("source_provider") or "mevzuat.gov.tr",
        "version": version,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }
    if embedding is not None:
        doc["embedding"] = embedding
        doc["embedding_model"] = embedding_model or "unknown"
    return doc


def chunk_from_decision_row(
    row: dict[str, Any],
    *,
    embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> dict[str, Any]:
    chunk_id = f"{row['id']}:v1"
    decision_date = row.get("decision_date")
    doc = chunk_from_article_row(
        {
            "article_id": row["id"],
            "document_id": row["id"],
            "article_no": row.get("decision_no"),
            "version": 1,
            "title": row.get("title"),
            "body": row.get("body") or "",
            "valid_from": decision_date,
            "valid_until": None,
            "document_type": "court_decision",
            "law_no": None,
            "source_provider": row.get("source_provider"),
            "authority": "official",
            "court": row.get("court_slug") or row.get("court_id"),
        },
        embedding=embedding,
        embedding_model=embedding_model,
    )
    doc["chamber"] = row.get("chamber")
    doc["docket_no"] = row.get("docket_no")
    return doc
