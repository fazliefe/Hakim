from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol

BASE_URL = "https://www.mevzuat.gov.tr"
DATATABLE_PATH = "/anasayfa/MevzuatDatatable"
CONTENT_PATH = "/anasayfa/MevzuatFihristDetayIframe"


@dataclass(frozen=True, slots=True)
class MevzuatHit:
    mevzuat_no: str
    mevzuat_tur: int
    mevzuat_tertip: str
    title: str


@dataclass(frozen=True, slots=True)
class RawSnapshot:
    mevzuat_no: str
    mevzuat_tur: int
    mevzuat_tertip: int | str
    html: str
    content_hash: str
    archive_dir: str
    content_path: str
    headers_path: str
    metadata_path: str
    retrieved_at: datetime


class HttpLike(Protocol):
    def get(self, *args: Any, **kwargs: Any) -> Any: ...
    def post(self, *args: Any, **kwargs: Any) -> Any: ...


class CurlHttp:
    """Uses curl.exe because some Windows Python SSL stacks fail on mevzuat.gov.tr."""

    def __init__(self, timeout: int = 90) -> None:
        self.timeout = timeout

    def get(self, url: str, *, params: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        from urllib.parse import urlencode

        full = url if not params else f"{url}?{urlencode(params)}"
        return self._run(["curl.exe", "-k", "-L", "--max-time", str(self.timeout), "-A", "Mozilla/5.0", full])

    def post(self, url: str, *, data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        from urllib.parse import urlencode

        body = urlencode(data or {})
        return self._run(
            [
                "curl.exe",
                "-k",
                "-L",
                "--max-time",
                str(self.timeout),
                "-A",
                "Mozilla/5.0",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
                "-H",
                "X-Requested-With: XMLHttpRequest",
                "--data",
                body,
                url,
            ]
        )

    def _run(self, cmd: list[str]) -> Any:
        completed = subprocess.run(cmd, capture_output=True, check=False)
        text = completed.stdout.decode("utf-8", errors="replace")
        if completed.returncode != 0 and not text:
            raise RuntimeError(completed.stderr.decode("utf-8", errors="replace") or "curl failed")

        class Response:
            def __init__(self) -> None:
                self.status_code = 200 if completed.returncode == 0 else 500
                self.headers = {"content-type": "text/html"}
                self.content = completed.stdout
                self.text = text
                self.url = cmd[-1]

            def raise_for_status(self) -> None:
                if completed.returncode != 0:
                    raise RuntimeError("curl request failed")

            def json(self) -> Any:
                return json.loads(self.text)

        return Response()


class MevzuatClient:
    def __init__(
        self,
        *,
        http: HttpLike | None = None,
        archive_root: str | Path = "data/raw",
        base_url: str = BASE_URL,
    ) -> None:
        self.http = http or CurlHttp()
        self.archive_root = Path(archive_root)
        self.base_url = base_url.rstrip("/")

    def discover(self, query: str, mevzuat_tur: int | None = None) -> list[MevzuatHit]:
        data = {
            "draw": "1",
            "start": "0",
            "length": "50",
            "search[value]": "",
            "search[regex]": "false",
            "AranacakIfade": query,
            "AranacakYer": "2",
            "TamCumle": "false",
            "MevzuatTur": str(mevzuat_tur) if mevzuat_tur is not None else "0",
            "GenelArama": "true",
        }
        response = self.http.post(f"{self.base_url}{DATATABLE_PATH}", data=data)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or payload.get("Data") or []
        hits: list[MevzuatHit] = []
        for row in rows:
            if isinstance(row, dict):
                hits.append(
                    MevzuatHit(
                        mevzuat_no=str(row.get("mevzuatNo") or row.get("MevzuatNo") or ""),
                        mevzuat_tur=int(row.get("mevzuatTur") or row.get("MevzuatTur") or 0),
                        mevzuat_tertip=str(row.get("mevzuatTertip") or row.get("MevzuatTertip") or ""),
                        title=str(row.get("mevAdi") or row.get("MevAdi") or row.get("title") or ""),
                    )
                )
        return [h for h in hits if h.mevzuat_no]

    def fetch_metadata(self, *, mevzuat_no: str, mevzuat_tur: int, mevzuat_tertip: int | str) -> dict[str, Any]:
        return {
            "mevzuat_no": str(mevzuat_no),
            "mevzuat_tur": int(mevzuat_tur),
            "mevzuat_tertip": str(mevzuat_tertip),
            "provider": "mevzuat.gov.tr",
            "official": True,
            "content_url": (
                f"{self.base_url}{CONTENT_PATH}"
                f"?MevzuatNo={mevzuat_no}&MevzuatTur={mevzuat_tur}&MevzuatTertip={mevzuat_tertip}"
            ),
        }

    def fetch_content(
        self,
        *,
        mevzuat_no: str,
        mevzuat_tur: int,
        mevzuat_tertip: int | str,
        retrieved_at: datetime | None = None,
    ) -> RawSnapshot:
        retrieved = retrieved_at or datetime.now(timezone.utc)
        meta = self.fetch_metadata(
            mevzuat_no=mevzuat_no,
            mevzuat_tur=mevzuat_tur,
            mevzuat_tertip=mevzuat_tertip,
        )
        response = self.http.get(
            f"{self.base_url}{CONTENT_PATH}",
            params={
                "MevzuatNo": mevzuat_no,
                "MevzuatTur": str(mevzuat_tur),
                "MevzuatTertip": str(mevzuat_tertip),
            },
        )
        response.raise_for_status()
        html = response.text
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        day = retrieved.date().isoformat()
        archive_dir = self.archive_root / "mevzuat" / str(mevzuat_no) / day
        archive_dir.mkdir(parents=True, exist_ok=True)
        content_path = archive_dir / "content.html"
        headers_path = archive_dir / "headers.json"
        metadata_path = archive_dir / "metadata.json"
        content_path.write_text(html, encoding="utf-8")
        headers = dict(getattr(response, "headers", {}) or {})
        headers_path.write_text(json.dumps(headers, ensure_ascii=False, indent=2), encoding="utf-8")
        meta_out = {
            **meta,
            "retrieved_at": retrieved.isoformat(),
            "content_hash": content_hash,
            "content_path": str(content_path),
        }
        metadata_path.write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")
        return RawSnapshot(
            mevzuat_no=str(mevzuat_no),
            mevzuat_tur=int(mevzuat_tur),
            mevzuat_tertip=mevzuat_tertip,
            html=html,
            content_hash=content_hash,
            archive_dir=str(archive_dir),
            content_path=str(content_path),
            headers_path=str(headers_path),
            metadata_path=str(metadata_path),
            retrieved_at=retrieved,
        )
