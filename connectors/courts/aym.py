from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from hakim_legal_schema.ids import court_id, decision_id

from courts.bedesten import ParsedDecision, html_to_text, parse_tr_date
from courts.http import CurlJson

AYM_BASE = "https://kararlarbilgibankasi.anayasa.gov.tr"
AYM_SEARCH = f"{AYM_BASE}/api/core/public/search"
AYM_FILES = f"{AYM_BASE}/api/core/public/kararlar"
AYM_ATTACHMENT = f"{AYM_BASE}/api/core/public/files/download-attachment"
AYM_BROWSER_HEADERS = {
    "Origin": AYM_BASE,
    "Referer": f"{AYM_BASE}/kbb/",
    "Accept": "application/json, */*",
}


def udf_to_text(data: bytes) -> str:
    """Extract judgment text from an AYM UDF (ZIP + content.xml CDATA) file."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        xml_name = "content.xml" if "content.xml" in names else next(
            (name for name in names if name.lower().endswith(".xml")),
            "",
        )
        if not xml_name:
            raise ValueError("UDF archive has no XML content")
        xml = archive.read(xml_name)
    decoded = xml.decode("utf-8", errors="replace")
    match = re.search(r"<!\[CDATA\[(.*?)\]\]>", decoded, re.DOTALL)
    if match:
        body = match.group(1)
    else:
        root = ElementTree.fromstring(xml)
        body = "\n".join(part.strip() for part in root.itertext() if part.strip())
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def attachment_parts(file_url: str) -> tuple[str, str]:
    """Split `/files/<folder>/<filename>` into folder and filename."""
    parts = [part for part in file_url.replace("\\", "/").split("/") if part]
    if "files" in parts:
        idx = parts.index("files")
        parts = parts[idx + 1 :]
    if len(parts) < 2:
        raise ValueError(f"unrecognized AYM file url: {file_url!r}")
    return parts[0], parts[-1]


def _hit_year(hit: dict[str, Any]) -> int:
    for key in ("kararTarihi", "basvuruTarihi", "yayinTarihi", "basvuruNo"):
        match = re.search(r"(20\d{2})", str(hit.get(key) or ""))
        if match:
            return int(match.group(1))
    return datetime.now().year


def _hit_date(hit: dict[str, Any]) -> date | None:
    raw = str(hit.get("kararTarihi") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return parse_tr_date(raw)


def _hit_body_fallback(hit: dict[str, Any]) -> str:
    parts = [
        str(hit.get("basvuruAdi") or "").strip(),
        html_to_text(str(hit.get("kararKonusu") or "")),
        str(hit.get("kararTuruBasvuruSonucuLabel") or "").strip(),
    ]
    return "\n\n".join(part for part in parts if part)


class AymClient:
    def __init__(self, *, http: CurlJson | None = None, archive_root: str | Path = "data/raw") -> None:
        self.http = http or CurlJson(default_headers=AYM_BROWSER_HEADERS)
        self.archive_root = Path(archive_root)

    def search(self, phrase: str, *, limit: int = 5) -> list[dict[str, Any]]:
        payload = {
            "query": phrase,
            "karar_tipi": "BireyselBasvuru",
            "page": 0,
            "size": limit,
        }
        response = self.http.post_json(AYM_SEARCH, payload)
        if not isinstance(response, dict):
            return []
        items = response.get("data") or []
        return [item for item in items if isinstance(item, dict)][:limit]

    def _download_udf(self, hit: dict[str, Any]) -> bytes | None:
        karar_id = str(hit.get("id") or "")
        karar_tipi = str(hit.get("kararTipi") or "BireyselBasvuru")
        if not karar_id:
            return None
        listing = self.http.get_json(f"{AYM_FILES}/{karar_id}/dosyalar", params={"kararTipi": karar_tipi})
        files = (listing or {}).get("data") if isinstance(listing, dict) else listing
        if not isinstance(files, list):
            return None
        chosen: dict[str, Any] | None = None
        for item in files:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            label = str(item.get("dosyaTipiIsim") or "")
            if url.lower().endswith(".udf") or "UDF" in label:
                chosen = item
                break
        if chosen is None and files and isinstance(files[0], dict):
            chosen = files[0]
        if not chosen or not chosen.get("url"):
            return None
        folder, filename = attachment_parts(str(chosen["url"]))
        data = self.http.get_bytes(f"{AYM_ATTACHMENT}/{folder}/{filename}")
        if data[:2] != b"PK":
            return None
        return data

    def ingest(self, phrase: str, *, limit: int = 5) -> list[ParsedDecision]:
        hits = self.search(phrase, limit=limit)
        decisions: list[ParsedDecision] = []
        day = datetime.now(timezone.utc).date().isoformat()
        for hit in hits:
            esas = str(hit.get("basvuruNo") or "").strip()
            if not esas or "/" not in esas:
                continue
            year = _hit_year(hit)
            chamber = str(hit.get("kararVerenBirimLabel") or "Anayasa Mahkemesi")
            applicant = str(hit.get("basvuruAdi") or "").strip()
            title = " — ".join(part for part in [chamber, esas, applicant] if part)
            udf_bytes: bytes | None = None
            body = ""
            try:
                udf_bytes = self._download_udf(hit)
                if udf_bytes:
                    body = udf_to_text(udf_bytes)
            except Exception:
                body = ""
            if not body.strip():
                body = _hit_body_fallback(hit)
            if not body.strip():
                continue
            content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            key = re.sub(r"[^0-9A-Za-z]+", "-", esas)[:80] or content_hash[:12]
            archive_dir = self.archive_root / "aym" / key / day
            archive_dir.mkdir(parents=True, exist_ok=True)
            if udf_bytes:
                (archive_dir / "content.udf").write_bytes(udf_bytes)
            html_path = archive_dir / "content.html"
            html_path.write_text(f"<pre>{body}</pre>", encoding="utf-8")
            (archive_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "provider": "kararlarbilgibankasi.anayasa.gov.tr",
                        "official": True,
                        "hit": hit,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "content_hash": content_hash,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            decisions.append(
                ParsedDecision(
                    id=decision_id(court="aym", year=year, docket=esas, decision_no=esas),
                    court_slug="aym",
                    court_id=court_id("aym"),
                    year=year,
                    docket_no=esas,
                    decision_no=esas,
                    decision_date=_hit_date(hit),
                    title=title,
                    body=body,
                    source_id="source:anayasa.gov.tr",
                    content_hash=content_hash,
                    provider_document_id=str(hit.get("id") or esas),
                    raw_snapshot_uri=str(html_path),
                    chamber=chamber,
                )
            )
        return decisions
