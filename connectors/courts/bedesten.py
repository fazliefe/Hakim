from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from hakim_legal_schema.ids import court_id, decision_id

from courts.http import CurlJson

BEDESTEN_BASE = "https://bedesten.adalet.gov.tr"
SEARCH_PATH = "/emsal-karar/searchDocuments"
DOC_PATH = "/emsal-karar/getDocumentContent"
MIN_INTERVAL_S = 3.6

COURT_TYPES = {
    "yargitay": "YARGITAYKARARI",
    "danistay": "DANISTAYKARAR",
    "yerelhukuk": "YERELHUKUK",
    "istinafhukuk": "ISTINAFHUKUK",
    "kyb": "KYB",
}

SOURCE_IDS = {
    "yargitay": "source:yargitay.gov.tr",
    "danistay": "source:danistay.gov.tr",
    "yerelhukuk": "source:emsal.uyap.gov.tr",
    "istinafhukuk": "source:emsal.uyap.gov.tr",
    "kyb": "source:emsal.uyap.gov.tr",
}


@dataclass(slots=True)
class ParsedDecision:
    id: str
    court_slug: str
    court_id: str
    year: int
    docket_no: str
    decision_no: str
    decision_date: date | None
    title: str
    body: str
    source_id: str
    content_hash: str
    provider_document_id: str
    raw_snapshot_uri: str | None
    chamber: str | None = None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_tr_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", value.strip())
    if not match:
        return None
    day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return date(year, month, day)
    except ValueError:
        return None


class BedestenClient:
    def __init__(self, *, http: CurlJson | None = None, archive_root: str | Path = "data/raw") -> None:
        self.http = http or CurlJson()
        self.archive_root = Path(archive_root)
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def search(self, *, court: str, phrase: str, page_size: int = 5, page_number: int = 1) -> list[dict[str, Any]]:
        item_type = COURT_TYPES[court]
        self._throttle()
        payload = {
            "data": {
                "pageSize": page_size,
                "pageNumber": page_number,
                "itemTypeList": [item_type],
                "phrase": phrase,
                "sortFields": ["KARAR_TARIHI"],
                "sortDirection": "desc",
            },
            "applicationName": "UyapMevzuat",
            "paging": True,
        }
        response = self.http.post_json(f"{BEDESTEN_BASE}{SEARCH_PATH}", payload)
        data = (response or {}).get("data") or {}
        return list(data.get("emsalKararList") or [])

    def fetch_document_html(self, document_id: str) -> tuple[str, str]:
        self._throttle()
        payload = {"data": {"documentId": document_id}, "applicationName": "UyapMevzuat"}
        response = self.http.post_json(f"{BEDESTEN_BASE}{DOC_PATH}", payload)
        data = (response or {}).get("data") or {}
        content = data.get("content") or ""
        mime = data.get("mimeType") or "text/html"
        if not content:
            return "", mime
        import base64

        raw = base64.b64decode(content)
        return raw.decode("utf-8", errors="replace"), mime

    def ingest_hits(
        self,
        *,
        court: str,
        phrase: str,
        limit: int = 5,
    ) -> list[ParsedDecision]:
        hits = self.search(court=court, phrase=phrase, page_size=limit)
        decisions: list[ParsedDecision] = []
        day = datetime.now(timezone.utc).date().isoformat()
        for hit in hits[:limit]:
            document_id = str(hit.get("documentId") or "")
            if not document_id:
                continue
            html, _mime = self.fetch_document_html(document_id)
            body = html_to_text(html)
            esas = str(hit.get("esasNo") or f"{hit.get('esasNoYil') or ''}/{hit.get('esasNoSira') or document_id}")
            karar = str(hit.get("kararNo") or f"{hit.get('kararNoYil') or ''}/{hit.get('kararNoSira') or '0'}")
            year = int(hit.get("kararNoYil") or hit.get("esasNoYil") or datetime.now().year)
            chamber = hit.get("birimAdi")
            title = " — ".join(part for part in [chamber, f"{esas} E.", f"{karar} K."] if part)
            content_hash = hashlib.sha256((html or body).encode("utf-8")).hexdigest()
            archive_dir = self.archive_root / court / document_id / day
            archive_dir.mkdir(parents=True, exist_ok=True)
            html_path = archive_dir / "content.html"
            meta_path = archive_dir / "metadata.json"
            html_path.write_text(html, encoding="utf-8")
            meta = {
                "provider": "bedesten.adalet.gov.tr",
                "court": court,
                "official": True,
                "document_id": document_id,
                "hit": hit,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "content_hash": content_hash,
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            decisions.append(
                ParsedDecision(
                    id=decision_id(court=court, year=year, docket=esas, decision_no=karar),
                    court_slug=court,
                    court_id=court_id(court),
                    year=year,
                    docket_no=esas,
                    decision_no=karar,
                    decision_date=parse_tr_date(hit.get("kararTarihiStr")),
                    title=title,
                    body=body,
                    source_id=SOURCE_IDS[court],
                    content_hash=content_hash,
                    provider_document_id=document_id,
                    raw_snapshot_uri=str(html_path),
                    chamber=chamber,
                )
            )
        return decisions
