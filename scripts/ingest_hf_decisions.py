#!/usr/bin/env python3
"""Bulk-ingest a filtered subset of hamzabagirsakci/turkish-court-decisions
(HuggingFace, CC0) into `court_decisions`.

Bu, "bütün emsal kararları" hedefine ulaşmanın ANA yolu — canlı Bedesten API
(`scripts/ingest_decisions.py`) haftalar sürer ve dokümante olmayan bir devlet
servisini yormak anlamına gelir; bu script tek seferlik, rate-limit'siz bir
toplu indirmeden filtrelenmiş bir alt küme seçer. İkisi de aynı
`write_decisions()`'tan geçer — tek upsert mantığı.

Kanun-alaka önceliklendirmesi (mevcut arşivdeki TCK/CMK/İYUK/6216'ya atıf
yapan kararları öne alma) ve stratified sampling (mahkeme + dönem dengesi)
uygular; 11M+ kaydın TAMAMINI ne indirir ne saklar — sadece bu alt küme.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "connectors"),
    str(ROOT / "services"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

import psycopg
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, list_repo_files

from courts.bedesten import ParsedDecision
from graph.citations import LAW_NUMBER_CONTEXT_RE
from hakim_legal_schema.ids import court_id, decision_id
from ingestion.decision_writer import write_decisions
from retrieval.bm25 import LAW_HINTS

REPO_ID = "hamzabagirsakci/turkish-court-decisions"
DATA_PREFIX = {"yargitay": "data/yargitay/", "danistay": "data/danistay/"}
# Mirror kaynak — bedesten.adalet.gov.tr ile byte-byte aynılığı indirmeden
# doğrulanamıyor (bkz. migration 003 yorumu), authority='secondary'.
HF_SOURCE_ID = "source:hf:turkish-court-decisions"

_LAW_ABBR_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in LAW_HINTS) + r")\b", re.IGNORECASE)


def _is_law_relevant(text: str) -> bool:
    """Metin, arşivde zaten yüklü kanunlardan (TCK/CMK/İYUK/6216) birine
    açıkça atıf yapıyor mu? Kesin bir hukuki eşleşme garantisi değil —
    sadece seçimde önceliklendirme sinyali (bkz. services/graph/citations.py
    ile aynı desenler)."""
    if not text:
        return False
    sample = text[:4000]  # kararın başı genelde dava konusunu/dayanağı taşır
    normalized = sample.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    if _LAW_ABBR_RE.search(normalized):
        return True
    return bool(LAW_NUMBER_CONTEXT_RE.search(sample))


def _period(year: int | None) -> str:
    if not year:
        return "bilinmiyor"
    if year < 1990:
        return "<1990"
    if year < 2000:
        return "1990-1999"
    if year < 2010:
        return "2000-2009"
    if year < 2020:
        return "2010-2019"
    return "2020+"


def _repo_shards(court: str) -> list[str]:
    prefix = DATA_PREFIX[court]
    files = list_repo_files(REPO_ID, repo_type="dataset")
    return sorted(f for f in files if f.startswith(prefix) and f.endswith(".parquet"))


def _iter_rows(court: str, shard_files: list[str], cache_dir: Path) -> Iterator[dict[str, Any]]:
    for shard in shard_files:
        path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename=shard, cache_dir=str(cache_dir))
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=2000):
            for row in batch.to_pylist():
                yield row


def row_to_parsed_decision(row: dict[str, Any], court: str) -> ParsedDecision | None:
    """HF veri seti satırını `ParsedDecision`'a çevirir — `write_decisions()`
    hem bu yoldan hem de canlı BedestenClient'tan gelen kayıtları aynı
    şekilde işler."""
    esas = str(row.get("esas_no") or "").strip()
    karar = str(row.get("karar_no") or "").strip()
    year = row.get("year")
    if not esas or not karar or not year:
        return None
    karar_tarihi = row.get("karar_tarihi")
    decision_date: date | None = None
    if karar_tarihi:
        try:
            decision_date = date.fromisoformat(str(karar_tarihi)[:10])
        except ValueError:
            decision_date = None
    text = str(row.get("text") or "")
    chamber = row.get("court")
    title_parts = [p for p in [chamber, f"{esas} E.", f"{karar} K."] if p]
    raw_sha = str(row.get("raw_sha256") or "").removeprefix("sha256:")
    content_hash = raw_sha or hashlib.sha256(text.encode("utf-8")).hexdigest()
    return ParsedDecision(
        id=decision_id(court=court, year=int(year), docket=esas, decision_no=karar),
        court_slug=court,
        court_id=court_id(court),
        year=int(year),
        docket_no=esas,
        decision_no=karar,
        decision_date=decision_date,
        title=" — ".join(title_parts),
        body=text,
        source_id=HF_SOURCE_ID,
        content_hash=content_hash,
        provider_document_id=str(row.get("document_id") or row.get("id") or ""),
        raw_snapshot_uri=None,
        chamber=chamber,
    )


def existing_decision_keys(database_url: str, courts: list[str]) -> set[str]:
    """Postgres'te zaten var olan kararların (court, year, docket_no,
    decision_no) anahtarları — tekrar çalıştırmalarda aynı kararları yeniden
    seçip boşuna embed etmemek için (seçim algoritması deterministik,
    dışlama olmadan ikinci çalıştırma neredeyse aynı kümeyi seçerdi)."""
    import psycopg

    court_ids = [court_id(c) for c in courts]
    with psycopg.connect(database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        rows = conn.execute(
            "SELECT court_id, year, docket_no, decision_no FROM court_decisions WHERE court_id = ANY(%s)",
            (court_ids,),
        ).fetchall()
    return {f"{cid}:{year}:{docket}:{no}" for cid, year, docket, no in rows}


def select_for_court(
    court: str,
    quota: int,
    cache_dir: Path,
    *,
    max_shards: int | None = None,
    relevant_ratio: float = 0.7,
    exclude: set[str] | None = None,
) -> list[ParsedDecision]:
    """Tek geçişte akış: önce kanun-alaka önceliklendirmesi (relevant_ratio
    kadar kota), sonra dönem-dengeli (stratified) rastgele doldurma.
    `exclude` verilirse (önceki çalıştırmalardan zaten ingest edilmiş
    kararlar), bunlar atlanır — böylece "N tane daha" gerçekten yeni kararlar
    getirir, aynı kararları tekrar seçip boşuna embed etmez."""
    shard_files = _repo_shards(court)
    if max_shards:
        shard_files = shard_files[:max_shards]
    relevant_target = int(quota * relevant_ratio)
    fallback_target = quota - relevant_target
    per_period_cap = max(50, fallback_target // 4 + 1)
    exclude = exclude or set()

    relevant: list[ParsedDecision] = []
    fallback_by_period: dict[str, list[ParsedDecision]] = defaultdict(list)
    seen_keys: set[str] = set()
    scanned = 0
    skipped_existing = 0

    for row in _iter_rows(court, shard_files, cache_dir):
        scanned += 1
        parsed = row_to_parsed_decision(row, court)
        if parsed is None:
            continue
        key = f"{parsed.year}:{parsed.docket_no}:{parsed.decision_no}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if f"{parsed.court_id}:{parsed.year}:{parsed.docket_no}:{parsed.decision_no}" in exclude:
            skipped_existing += 1
            continue

        text = str(row.get("text") or "")
        if len(relevant) < relevant_target and _is_law_relevant(text):
            relevant.append(parsed)
        else:
            bucket = fallback_by_period[_period(parsed.year)]
            if len(bucket) < per_period_cap:
                bucket.append(parsed)

        fallback_collected = sum(len(v) for v in fallback_by_period.values())
        if len(relevant) >= relevant_target and fallback_collected >= fallback_target:
            break

    fallback: list[ParsedDecision] = []
    periods = [p for p in fallback_by_period if fallback_by_period[p]]
    i = 0
    while len(fallback) < fallback_target and periods:
        period = periods[i % len(periods)]
        bucket = fallback_by_period[period]
        if bucket:
            fallback.append(bucket.pop())
        if not bucket:
            periods.remove(period)
            continue
        i += 1

    print(
        f"{court}: taranan={scanned} alaka_önceliklendirilen={len(relevant)} "
        f"dönem_dengeli_dolgu={len(fallback)} shard_sayısı={len(shard_files)} "
        f"zaten_var_atlanan={skipped_existing}",
        flush=True,
    )
    return relevant + fallback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--courts", default="yargitay,danistay")
    parser.add_argument("--target-count", type=int, default=12000)
    parser.add_argument("--min-per-court", type=int, default=2000)
    parser.add_argument(
        "--max-shards-per-court",
        type=int,
        default=None,
        help="Bant genişliği/süre sınırlamak için (varsayılan: tüm shard'lar taranır)",
    )
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data" / "hf_cache")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("HAKIM_DATABASE_URL", "postgresql://hakim:hakim@127.0.0.1:5433/hakim"),
    )
    parser.add_argument("--dry-run", action="store_true", help="Sadece seçim istatistiklerini göster, DB'ye yazma")
    parser.add_argument(
        "--no-exclude-existing",
        action="store_true",
        help="Postgres'te zaten var olan kararları dışlama (varsayılan: dışlanır)",
    )
    args = parser.parse_args()

    wanted = [c.strip() for c in args.courts.split(",") if c.strip()]
    unknown = [c for c in wanted if c not in DATA_PREFIX]
    if unknown:
        raise SystemExit(f"desteklenmeyen mahkeme(ler): {unknown} (destekli: {list(DATA_PREFIX)})")

    base_quota = max(args.min_per_court, args.target_count // len(wanted))
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    exclude: set[str] = set()
    if not args.no_exclude_existing:
        exclude = existing_decision_keys(args.database_url, wanted)
        print(f"zaten yüklü {len(exclude)} karar dışlanacak (tekrar embed edilmeyecek)", flush=True)

    selections: dict[str, list[ParsedDecision]] = {}
    for court in wanted:
        selections[court] = select_for_court(
            court, base_quota, args.cache_dir, max_shards=args.max_shards_per_court, exclude=exclude
        )

    total = sum(len(v) for v in selections.values())
    print(f"seçim tamamlandı: toplam={total}", flush=True)
    for court, items in selections.items():
        by_period: dict[str, int] = defaultdict(int)
        for item in items:
            by_period[_period(item.year)] += 1
        print(f"  {court}: {len(items)} karar, dönem dağılımı={dict(sorted(by_period.items()))}")

    if args.dry_run:
        print("--dry-run: veritabanına yazılmadı.")
        return

    with psycopg.connect(args.database_url) as conn:
        conn.execute("SET search_path TO hakim, public")
        for court, items in selections.items():
            for start in range(0, len(items), args.batch_size):
                batch = items[start : start + args.batch_size]
                report = write_decisions(conn, batch, source_id=HF_SOURCE_ID)
                conn.commit()
                print(
                    f"{court}: batch {start}-{start + len(batch)} "
                    f"status={report.status.value} written={report.articles_found}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
