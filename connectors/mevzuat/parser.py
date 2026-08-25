from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from bs4 import BeautifulSoup

from hakim_legal_schema.ids import article_id, article_version_id, law_id

ARTICLE_RE = re.compile(
    r"^(Ek\s+)?(Ge[cç]ici\s+)?Madde\s+([0-9]+(?:/[A-Z])?)\s*[-–—]\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
NUMBER_RE = re.compile(r"Kanun\s+Numaras[ıi]\s*:\s*([0-9]+)", re.IGNORECASE)
GAZETTE_RE = re.compile(
    r"Yay[ıi]mland[ıi][gğ][ıi]\s+Resm[îi]\s+Gazete\s*:\s*Tarih\s*:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})\s+Say[ıi]\s*:\s*([0-9]+)",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})$")
# mevzuat.gov.tr başlığın sonuna birden fazla değişiklik-dipnotu ekleyebilir,
# örn. "... itiraz [67] [68]" — hepsini (tek değil) temizle.
TRAILING_FOOTNOTE_RE = re.compile(r"(?:\s*\[\d+\])+\s*$")
# mevzuat.gov.tr HTML'i genelde "charset=Windows-1254" beyan eder ama gövde
# bayt olarak zaten UTF-8'dir. Bu string bize UTF-8 olarak decode edilmiş
# hâlde gelir; lxml yine de bu meta etiketini görüp bazı paragrafları (buffer
# sınırına göre değişen, öngörülemeyen bir alt kümeyi) yeniden (yanlış)
# Windows-1252 gibi çözümleyip mojibake üretebiliyor — örn. "Madde 281 –"
# içindeki tire "Ã¢â‚¬â€œ" benzeri bozuk karakterlere dönüşüp regex'i kırıyor,
# bu da CMK'da madde 281'den sonrasının (m.291 dâhil) hiç ayrıştırılmamasına
# yol açıyordu (285 → 356 madde, etiket silinince). Ayrıştırmadan önce silmek
# lxml'in bu yanlış ipucuna göre yeniden kodlamasını önlüyor.
CHARSET_META_RE = re.compile(r"<meta[^>]*charset[^>]*>", re.IGNORECASE)


def _strip_footnotes(text: str) -> str:
    return TRAILING_FOOTNOTE_RE.sub("", text).strip()


@dataclass(slots=True)
class ParsedArticle:
    id: str
    version_id: str
    article_no: str
    text: str
    version: int = 1
    title: str | None = None
    valid_from: datetime = field(
        default_factory=lambda: datetime(2004, 10, 12, tzinfo=timezone.utc)
    )
    valid_until: datetime | None = None


@dataclass(slots=True)
class ParsedLaw:
    id: str
    number: str
    title: str
    publication_date: date
    gazette_number: str | None
    content_hash: str
    articles: list[ParsedArticle]
    raw_snapshot_uri: str | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _parse_tr_date(value: str) -> date:
    match = DATE_RE.match(value.strip())
    if not match:
        raise ValueError(f"invalid date: {value}")
    day, month, year = map(int, match.groups())
    return date(year, month, day)


def _is_structural_heading(text: str) -> bool:
    upper = text.upper()
    markers = (
        "KİTAP",
        "KITAP",
        "KISIM",
        "BÖLÜM",
        "BOLUM",
        "KANUN NUMARASI",
        "KABUL TARİHİ",
        "KABUL TARIHI",
        "YAYIMLANDIĞI",
        "YAYIMLANDIGI",
        "GENEL HÜKÜMLER",
        "GENEL HUKUMLER",
    )
    if any(marker in upper for marker in markers):
        return True
    if text.isupper() and len(text.split()) <= 6:
        return True
    return False


def parse_mevzuat_html(
    html: str,
    *,
    law_number: str,
    content_hash: str = "",
    version: int = 1,
    valid_from: datetime | None = None,
) -> ParsedLaw:
    soup = BeautifulSoup(CHARSET_META_RE.sub("", html), "lxml")
    # mevzuat.gov.tr mixes MsoNormal and plain <p> blocks for later articles.
    paragraphs = [_clean(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p]

    title = paragraphs[0] if paragraphs else f"Kanun {law_number}"
    title = _strip_footnotes(title)

    number = law_number
    publication_date = date(2004, 10, 12)
    gazette_number: str | None = None
    joined = "\n".join(paragraphs[:20])
    if m := NUMBER_RE.search(joined):
        number = m.group(1)
    if m := GAZETTE_RE.search(joined):
        publication_date = _parse_tr_date(m.group(1))
        gazette_number = m.group(2)

    starts: list[tuple[int, str, str, str]] = []
    for idx, text in enumerate(paragraphs):
        match = ARTICLE_RE.match(text)
        if match:
            # "Ek Madde 7" ve "Geçici Madde 7", aynı kanunda sıradan "Madde 7"
            # ile aynı numarayı taşıyabilir (İYUK'ta olduğu gibi). article_no
            # tek başına ("7") kimlik için yeterli değil — id_kind bunu ayırt
            # eder, yoksa ikisi aynı canonical id'yi üretip biri diğerinin
            # üzerine yazar (bkz. rapor: İYUK "Geçici Madde 7" gerçek "Madde 7"
            # / dava açma süresini sessizce sildi).
            id_kind = "gecici" if match.group(2) else "ek" if match.group(1) else "madde"
            starts.append((idx, match.group(3), text, id_kind))

    vf = valid_from or datetime(
        publication_date.year,
        publication_date.month,
        publication_date.day,
        tzinfo=timezone.utc,
    )
    articles: list[ParsedArticle] = []
    for i, (start_idx, article_no, first_line, id_kind) in enumerate(starts):
        end_idx = starts[i + 1][0] if i + 1 < len(starts) else len(paragraphs)
        body_parts = [first_line] + paragraphs[start_idx + 1 : end_idx]
        body = "\n".join(body_parts).strip()
        title_candidate = paragraphs[start_idx - 1] if start_idx > 0 else None
        if title_candidate and (ARTICLE_RE.match(title_candidate) or _is_structural_heading(title_candidate)):
            title_candidate = None
        if title_candidate:
            # mevzuat.gov.tr madde başlığının sonuna değişiklik dipnotu ekler,
            # örn. "Trafik güvenliğini tehlikeye sokma [77]" — dipnot madde
            # metninin parçası değildir, atıflarda başlık gibi görünmemeli.
            title_candidate = _strip_footnotes(title_candidate) or None
        # "Ek"/"Geçici" önekini numaraya kat: Postgres'te articles tablosu
        # UNIQUE(document_id, article_no) zorunlu kılıyor, düz "7" ikisi için
        # de kullanılırsa ikinci INSERT constraint ihlaliyle patlar (önce
        # sessiz üzerine-yazma vardı, şimdi en azından görünür bir hata).
        if id_kind != "madde":
            article_no = f"{id_kind}-{article_no}"
        articles.append(
            ParsedArticle(
                id=article_id(number, article_no),
                version_id=article_version_id(number, article_no, version),
                article_no=article_no,
                title=title_candidate,
                text=body,
                version=version,
                valid_from=vf,
            )
        )

    return ParsedLaw(
        id=law_id(number),
        number=number,
        title=title,
        publication_date=publication_date,
        gazette_number=gazette_number,
        content_hash=content_hash,
        articles=articles,
    )
