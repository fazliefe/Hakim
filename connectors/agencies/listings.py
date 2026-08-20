from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from hakim_legal_schema.ids import court_id, decision_id

from courts.bedesten import ParsedDecision, html_to_text, parse_tr_date
from courts.http import CurlJson
from courts.pdftext import looks_like_pdf, pdf_to_text

REKABET_LIST = "https://www.rekabet.gov.tr/tr/Kararlar"
REKABET_BASE = "https://www.rekabet.gov.tr"
KVKK_LIST = "https://www.kvkk.gov.tr/Icerik/5419/kurul-kararlari"
KVKK_BASE = "https://www.kvkk.gov.tr"
UYUSMAZLIK_LIST = "https://kararlar.uyusmazlik.gov.tr/"
RG_HOME = "https://www.resmigazete.gov.tr/"
TBMM_SON = "https://www.tbmm.gov.tr/Tutanaklar/SonTutanak"
SAYISTAY_LIST = "https://www.sayistay.gov.tr/KararlarGenelKurul"


@dataclass(slots=True)
class ListingHit:
    court: str
    source_id: str
    key: str
    title: str
    url: str
    docket_no: str
    decision_no: str
    year: int
    decision_date: date | None = None
    extra: dict[str, Any] | None = None


def _abs(base: str, href: str) -> str:
    return urljoin(base, href)


def _year(value: date | None, token: str | None, fallback: int) -> int:
    if value:
        return value.year
    if token:
        match = re.search(r"(19|20)\d{2}", token)
        if match:
            return int(match.group(0))
    return fallback


def parse_rekabet_listing(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    seen: set[str] = set()
    for table in soup.select("div#kararList table.equalDivide, table.equalDivide"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        cells1 = rows[0].find_all("td")
        cells2 = rows[1].find_all("td")
        title_cell = rows[2].find("td")
        link = title_cell.find("a", href=True) if title_cell else None
        href = str(link["href"]) if link else ""
        qs = parse_qs(urlparse(href).query)
        karar_id = (qs.get("kararId") or [""])[0]
        if not karar_id or karar_id in seen:
            continue
        seen.add(karar_id)
        title = (link.get_text(" ", strip=True) if link else "") or karar_id
        dec_num = cells1[1].get_text(strip=True) if len(cells1) > 1 else karar_id
        dec_date = parse_tr_date(cells2[0].get_text(strip=True) if cells2 else None)
        hits.append(
            ListingHit(
                court="rekabet",
                source_id="source:rekabet.gov.tr",
                key=karar_id,
                title=title,
                url=_abs(REKABET_BASE, href or f"/Karar?kararId={karar_id}"),
                docket_no=karar_id,
                decision_no=dec_num or karar_id,
                year=_year(dec_date, dec_num, fallback_year),
                decision_date=dec_date,
            )
        )
    if hits:
        return hits
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        qs = parse_qs(urlparse(href).query)
        karar_id = (qs.get("kararId") or [""])[0]
        if not karar_id or karar_id in seen:
            continue
        if "/Karar" not in href and "kararId=" not in href:
            continue
        seen.add(karar_id)
        title = a.get_text(" ", strip=True) or karar_id
        hits.append(
            ListingHit(
                court="rekabet",
                source_id="source:rekabet.gov.tr",
                key=karar_id,
                title=title,
                url=_abs(REKABET_BASE, href),
                docket_no=karar_id,
                decision_no=karar_id,
                year=fallback_year,
            )
        )
    return hits


def parse_kvkk_listing(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        blob = f"{href} {text}".lower()
        if "/icerik/" not in href.lower():
            continue
        if not re.search(r"karar|ilke", blob):
            continue
        path = urlparse(href).path.strip("/")
        parts = path.split("/")
        if len(parts) < 2:
            continue
        key = "/".join(parts[1:3]) if len(parts) >= 3 else parts[-1]
        if key in seen or key.lower() in {"5419/kurul-kararlari", "5463/kurul-kararlari"}:
            continue
        seen.add(key)
        number = None
        match = re.search(r"(\d{4}[/-]\d+)", text)
        if match:
            number = match.group(1).replace("-", "/")
        hits.append(
            ListingHit(
                court="kvkk",
                source_id="source:kvkk.gov.tr",
                key=key.replace("/", "-"),
                title=text or key,
                url=_abs(KVKK_BASE, href),
                docket_no=key.replace("/", "-"),
                decision_no=number or key.replace("/", "-"),
                year=_year(parse_tr_date(text.split(" ")[0] if text else None), number or text, fallback_year),
            )
        )
    return hits


def parse_uyusmazlik_listing(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    seen: set[str] = set()
    grid = soup.find("table", id="GridView1")
    rows = grid.find_all("tr")[1:] if grid else []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        link = cells[3].find("a", href=True)
        href = str(link["href"]) if link else ""
        if "uploads" not in href.lower() and not href.lower().endswith(".pdf"):
            continue
        esas = cells[0].get_text(strip=True) or "esas"
        karar = cells[1].get_text(strip=True) or Path(urlparse(href).path).stem
        karar_date = parse_tr_date(cells[2].get_text(strip=True))
        key = Path(urlparse(href).path).stem
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            ListingHit(
                court="uyusmazlik",
                source_id="source:uyusmazlik.gov.tr",
                key=key,
                title=f"{esas} E. {karar} K.",
                url=_abs(UYUSMAZLIK_LIST, href),
                docket_no=esas.replace(":", "-"),
                decision_no=karar.replace(":", "-"),
                year=_year(karar_date, key, fallback_year),
                decision_date=karar_date,
            )
        )
    if hits:
        return hits
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if "uploads/" not in href.lower() or not href.lower().endswith(".pdf"):
            continue
        key = Path(urlparse(href).path).stem
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            ListingHit(
                court="uyusmazlik",
                source_id="source:uyusmazlik.gov.tr",
                key=key,
                title=key,
                url=_abs(UYUSMAZLIK_LIST, href),
                docket_no=key,
                decision_no=key,
                year=_year(None, key, fallback_year),
            )
        )
    return hits


def parse_resmi_gazete_listing(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if "/eskiler/" not in href.lower() or not href.lower().endswith(".htm"):
            continue
        stem = Path(urlparse(href).path).stem
        if stem in seen:
            continue
        seen.add(stem)
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)) or stem
        date_match = re.match(r"^(\d{4})(\d{2})(\d{2})", stem)
        issued = None
        year = fallback_year
        if date_match:
            year = int(date_match.group(1))
            try:
                issued = date(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
            except ValueError:
                issued = None
        hits.append(
            ListingHit(
                court="resmi_gazete",
                source_id="source:resmigazete.gov.tr",
                key=stem,
                title=title,
                url=_abs(RG_HOME, href),
                docket_no=stem,
                decision_no=stem,
                year=year,
                decision_date=issued,
            )
        )
    return hits


def parse_tbmm_son_tutanak(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    embed = soup.find("embed", src=True) or soup.find("iframe", src=True)
    src = str(embed["src"]).split("#", 1)[0] if embed else ""
    if not src:
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if "cdn.tbmm.gov.tr" in href and href.lower().endswith(".pdf"):
                src = href
                break
    if not src:
        return hits
    key = Path(urlparse(src).path).stem
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else "TBMM son tutanak"
    hits.append(
        ListingHit(
            court="tbmm",
            source_id="source:tbmm.gov.tr",
            key=key,
            title=title,
            url=_abs("https://www.tbmm.gov.tr/", src),
            docket_no=key,
            decision_no=key,
            year=_year(None, src, fallback_year),
        )
    )
    return hits


def parse_sayistay_listing(html: str, *, fallback_year: int) -> list[ListingHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[ListingHit] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not re.search(r"Karar(lar)?(Detay|/GetDocument|pdf)", href, re.I):
            continue
        key = Path(urlparse(href).path).stem or hashlib.sha1(href.encode()).hexdigest()[:12]
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            ListingHit(
                court="sayistay",
                source_id="source:sayistay.gov.tr",
                key=key,
                title=text or key,
                url=_abs("https://www.sayistay.gov.tr/", href),
                docket_no=key,
                decision_no=key,
                year=fallback_year,
            )
        )
    return hits


class AgencyClient:
    def __init__(self, *, http: CurlJson | None = None, archive_root: str | Path = "data/raw") -> None:
        self.http = http or CurlJson()
        self.archive_root = Path(archive_root)

    def _fetch_text(self, url: str) -> str:
        payload = self.http.get(url)
        return payload if isinstance(payload, str) else str(payload)

    def _fetch_body(self, url: str) -> tuple[str, str]:
        data = self.http.get_bytes(url)
        if looks_like_pdf(data):
            return pdf_to_text(data), "application/pdf"
        text = data.decode("utf-8", errors="replace")
        if "<html" in text[:400].lower() or "<!doctype" in text[:400].lower() or "<body" in text.lower():
            return html_to_text(text), "text/html"
        return html_to_text(text), "text/html"

    def _to_decision(self, hit: ListingHit, body: str, snapshot: Path, mime: str) -> ParsedDecision:
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return ParsedDecision(
            id=decision_id(
                court=hit.court,
                year=hit.year,
                docket=hit.docket_no,
                decision_no=hit.decision_no,
            ),
            court_slug=hit.court,
            court_id=court_id(hit.court),
            year=hit.year,
            docket_no=hit.docket_no,
            decision_no=hit.decision_no,
            decision_date=hit.decision_date,
            title=hit.title,
            body=body or hit.title,
            source_id=hit.source_id,
            content_hash=content_hash,
            provider_document_id=hit.key,
            raw_snapshot_uri=str(snapshot),
        )

    def ingest_hits(self, hits: list[ListingHit], *, limit: int = 3) -> list[ParsedDecision]:
        day = datetime.now(timezone.utc).date().isoformat()
        decisions: list[ParsedDecision] = []
        for hit in hits[:limit]:
            body, mime = self._fetch_body(hit.url)
            archive_dir = self.archive_root / hit.court / hit.key / day
            archive_dir.mkdir(parents=True, exist_ok=True)
            snapshot = archive_dir / ("content.pdf.txt" if mime == "application/pdf" else "content.html.txt")
            snapshot.write_text(body, encoding="utf-8")
            meta = {
                "provider": hit.source_id,
                "court": hit.court,
                "official": True,
                "url": hit.url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "mime": mime,
            }
            (archive_dir / "metadata.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            decisions.append(self._to_decision(hit, body, snapshot, mime))
        return decisions

    def ingest_rekabet(self, *, limit: int = 3) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(REKABET_LIST)
        return self.ingest_hits(parse_rekabet_listing(html, fallback_year=year), limit=limit)

    def ingest_kvkk(self, *, limit: int = 3) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(KVKK_LIST)
        return self.ingest_hits(parse_kvkk_listing(html, fallback_year=year), limit=limit)

    def ingest_uyusmazlik(self, *, limit: int = 3) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(UYUSMAZLIK_LIST)
        return self.ingest_hits(parse_uyusmazlik_listing(html, fallback_year=year), limit=limit)

    def ingest_resmi_gazete(self, *, limit: int = 3) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(RG_HOME)
        return self.ingest_hits(parse_resmi_gazete_listing(html, fallback_year=year), limit=limit)

    def ingest_tbmm(self, *, limit: int = 1) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(TBMM_SON)
        return self.ingest_hits(parse_tbmm_son_tutanak(html, fallback_year=year), limit=limit)

    def ingest_sayistay(self, *, limit: int = 2) -> list[ParsedDecision]:
        year = datetime.now().year
        html = self._fetch_text(SAYISTAY_LIST)
        return self.ingest_hits(parse_sayistay_listing(html, fallback_year=year), limit=limit)
