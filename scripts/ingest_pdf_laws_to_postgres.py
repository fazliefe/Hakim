#!/usr/bin/env python3
"""Ingest already-chunked PDF/OCR law data (data/raw/pdf_laws/) into PostgreSQL,
via the same write_parsed_law() writer the official mevzuat.gov.tr HTML path uses.

Bu script'ten ÖNCE bu kanunlar hiç Postgres'e girmemişti — yalnızca
scripts/index_legal_chunks.py --pdf-laws ile doğrudan Elasticsearch'e
yazılıyordu. Bu, "Postgres tek kaynak" mimarisini bozuyordu.

ÖNEMLİ DÜZELTME (bkz. konuşma): chunks.jsonl'deki article_no, "Ek Madde N" /
"Geçici Madde N" önekini kaybediyor — aynı kanunda "Madde 1" ile "Geçici
Madde 1" aynı article_no="1" ile işaretlenmiş durumda geldi. Postgres'in
UNIQUE(document_id, article_no) kısıtı yüzünden bu, ikincinin ilkinin üzerine
SESSİZCE yazılmasına yol açardı. connectors/mevzuat/parser.py'de AYNI bug
HTML yolu için zaten keşfedilip düzeltilmişti (bkz. o dosyadaki yorum:
"İYUK Geçici Madde 7 gerçek Madde 7'yi sessizce sildi") — burada da aynı
id_kind kuralını (ARTICLE_RE ile chunk body'sinin başındaki "Ek "/"Geçici "
önekini yeniden tespit edip) uyguluyoruz. Bu düzeltmeden SONRA da bir
çakışma kalırsa (örn. aynı kanunun farklı değişiklik metinlerinden gelen iki
ayrı "Geçici Madde 1"), veriyi kaybetmemek için numaralı bir son ek (-2, -3)
eklenir ve bu, çıktıda "manuel inceleme gerekiyor" olarak işaretlenir.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "connectors"),
    str(ROOT / "services"),
    str(ROOT / "packages" / "legal-schema" / "src"),
]

import psycopg  # noqa: E402

from hakim_legal_schema.ids import article_id, article_version_id, law_id  # noqa: E402
from ingestion.postgres_writer import write_parsed_law  # noqa: E402
from mevzuat.parser import ParsedArticle, ParsedLaw  # noqa: E402

PDF_LAWS_ROOT = ROOT / "data" / "raw" / "pdf_laws"

# connectors/mevzuat/parser.py::ARTICLE_RE'nin bir üst kümesi: resmi HTML
# parser'ı "Madde 309/A" gibi yalnızca BÜYÜK harfli ekleri tanıyor ([A-Z]).
# Bu OCR'lı PDF metinlerinde aynı ek küçük Türkçe harflerle basılı geliyor
# ("Madde 309/ç", "309/ğ" gibi) — İİK'da bu deseni gözden kaçırmak 5 farklı
# maddeyi ("309/ç", "309/ğ", "309/ö", "309/ş", "309/ü") aynı article_no="309"
# altında çakıştırıyordu. Paylaşılan connectors/mevzuat/parser.py'yi (HTML
# yolunu, başka yerlerde test edilmiş) değiştirmek yerine burada yerel,
# daha geniş bir kopyasını kullanıyoruz.
ARTICLE_RE = re.compile(
    r"^(Ek\s+)?(Ge[cç]ici\s+)?Madde\s+([0-9]+(?:/[A-ZÇĞİÖŞÜa-zçğıöşü])?)\s*[-–—]\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)

# turk-medeni-kanunu'nda OCR "Tarihi:" yazmış (fazladan bir "i"); diğerlerinde
# "Tarih:"/"Tarih :" — ikisini de tolere ediyoruz. \s zaten satır sonlarını
# da eşleştirdiği için farklı satırlara bölünmüş başlıklar da yakalanıyor.
GAZETTE_RE = re.compile(
    r"Yay[ıi]mland[ıi][gğ][ıi]\s+Resm[îi]\s+Gazete\s*:?\s*Tarih[iİ]?\s*:\s*"
    r"([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s+Say[ıi]\s*:\s*([0-9]+)",
    re.IGNORECASE,
)

TARGET_SLUGS = [
    "turk-medeni-kanunu",
    "borclar-kanunu",
    "icra-kanunu",
    "anayasa",
    "tebligat-kanunu",
    "bilgi-edinme-kanunu",
    "elektronik-imza-kanunu",
]


def _latest_snapshot(slug: str) -> Path:
    base = PDF_LAWS_ROOT / slug
    dated = sorted(p for p in base.iterdir() if p.is_dir())
    if not dated:
        raise FileNotFoundError(f"{base} altında tarihli klasör yok")
    return dated[-1]


def _extract_gazette(content_text: str) -> tuple[date, str | None]:
    m = GAZETTE_RE.search(content_text[:3000])
    if not m:
        raise ValueError("Resmî Gazete tarihi/sayısı metinde bulunamadı — uydurma tarih koymuyoruz, dur.")
    day, month, year = (int(x) for x in m.group(1).split("/"))
    return date(year, month, day), m.group(2)


def build_law(slug: str) -> tuple[ParsedLaw, dict[str, int], list[str]]:
    folder = _latest_snapshot(slug)
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    content_text = (folder / "content.txt").read_text(encoding="utf-8")
    law_no = str(metadata["law_no"])
    title = str(metadata["title"])
    content_hash = str(metadata.get("content_hash") or "")

    pub_date, gazette_no = _extract_gazette(content_text)
    valid_from = datetime(pub_date.year, pub_date.month, pub_date.day, tzinfo=timezone.utc)

    stats = {"madde": 0, "ek": 0, "gecici": 0, "unrecognized": 0, "collision_renamed": 0}
    needs_review: list[str] = []
    seen_ids: set[str] = set()
    articles: list[ParsedArticle] = []

    with (folder / "chunks.jsonl").open(encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            chunk = json.loads(raw_line)
            body = str(chunk.get("body") or "")
            m = ARTICLE_RE.match(body)
            if m:
                id_kind = "gecici" if m.group(2) else "ek" if m.group(1) else "madde"
                raw_no = m.group(3)
            else:
                id_kind = "unrecognized"
                raw_no = str(chunk.get("article_no") or "")
            stats[id_kind] = stats.get(id_kind, 0) + 1
            article_no = raw_no if id_kind == "madde" else f"{id_kind}-{raw_no}"

            candidate_id = article_id(law_no, article_no)
            if candidate_id in seen_ids:
                # id_kind düzeltmesinden SONRA da çakışma varsa (örn. iki ayrı
                # değişiklik metninden gelen iki farklı "Geçici Madde 1") —
                # veriyi kaybetmemek için numaralandır, manuel incelemeye işaretle.
                n = 2
                while article_id(law_no, f"{article_no}-{n}") in seen_ids:
                    n += 1
                article_no = f"{article_no}-{n}"
                candidate_id = article_id(law_no, article_no)
                stats["collision_renamed"] += 1
                needs_review.append(candidate_id)
            seen_ids.add(candidate_id)

            articles.append(
                ParsedArticle(
                    id=candidate_id,
                    version_id=article_version_id(law_no, article_no, 1),
                    article_no=article_no,
                    title=chunk.get("title"),
                    text=body,
                    version=1,
                    valid_from=valid_from,
                )
            )

    law = ParsedLaw(
        id=law_id(law_no),
        number=law_no,
        title=title,
        publication_date=pub_date,
        gazette_number=gazette_no,
        content_hash=content_hash,
        articles=articles,
        raw_snapshot_uri=str((folder / "content.txt").relative_to(ROOT)),
    )
    return law, stats, needs_review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slugs", nargs="*", default=TARGET_SLUGS)
    parser.add_argument(
        "--database-url",
        default="postgresql://hakim:hakim@127.0.0.1:5433/hakim",
    )
    parser.add_argument("--dry-run", action="store_true", help="Sadece istatistik göster, yazma")
    args = parser.parse_args()

    all_needs_review: dict[str, list[str]] = {}
    with psycopg.connect(args.database_url, autocommit=False) as conn:
        conn.execute("SET search_path TO hakim, public")
        for slug in args.slugs:
            law, stats, needs_review = build_law(slug)
            print(
                f"{slug} (law:{law.number}, {law.title}): {len(law.articles)} madde "
                f"[madde={stats['madde']} ek={stats['ek']} gecici={stats['gecici']} "
                f"tanimsiz={stats['unrecognized']} cakisma_yeniden_adlandirildi={stats['collision_renamed']}]"
                f" | yayim: {law.publication_date} sayı:{law.gazette_number}"
            )
            if needs_review:
                all_needs_review[slug] = needs_review
                print(f"  MANUEL İNCELEME GEREKİYOR: {needs_review}")
            if not args.dry_run:
                report = write_parsed_law(conn, law, source_id="source:mevzuat.gov.tr")
                conn.commit()
                print(f"  -> yazıldı: status={report.status.value} content_changed={report.content_changed}")

    if args.dry_run:
        print("\n--dry-run: veritabanına yazılmadı.")
    if all_needs_review:
        print("\n=== Manuel incelenmesi gereken madde id'leri (çakışma sonrası yeniden adlandırıldı) ===")
        for slug, ids in all_needs_review.items():
            print(f"  {slug}: {ids}")


if __name__ == "__main__":
    main()
