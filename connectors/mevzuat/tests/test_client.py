from __future__ import annotations

import json
from pathlib import Path

from mevzuat.client import MevzuatClient


def test_discover_tck_via_datatable(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "data": [
            {
                "mevzuatNo": "5237",
                "mevzuatTur": 1,
                "mevzuatTertip": "5",
                "mevAdi": "Türk Ceza Kanunu",
            }
        ]
    }

    class FakeResponse:
        status_code = 200
        text = json.dumps(payload)
        headers = {"content-type": "application/json"}
        content = text.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    class FakeHttp:
        def post(self, *args, **kwargs):
            return FakeResponse()

        def get(self, *args, **kwargs):
            raise AssertionError("discover should use POST")

    client = MevzuatClient(http=FakeHttp(), archive_root=tmp_path)
    hits = client.discover(query="5237", mevzuat_tur=1)
    assert hits[0].mevzuat_no == "5237"
    assert hits[0].title == "Türk Ceza Kanunu"


def test_fetch_content_archives_raw_html(tmp_path: Path) -> None:
    html = "<html><body>TCK</body></html>"

    class FakeResponse:
        status_code = 200
        text = html
        content = html.encode("utf-8")
        headers = {"content-type": "text/html"}
        url = "https://www.mevzuat.gov.tr/anasayfa/MevzuatFihristDetayIframe?MevzuatNo=5237&MevzuatTur=1&MevzuatTertip=5"

        def raise_for_status(self) -> None:
            return None

    class FakeHttp:
        def get(self, *args, **kwargs):
            return FakeResponse()

        def post(self, *args, **kwargs):
            raise AssertionError("fetch_content should use GET")

    client = MevzuatClient(http=FakeHttp(), archive_root=tmp_path)
    snap = client.fetch_content(mevzuat_no="5237", mevzuat_tur=1, mevzuat_tertip=5)
    assert snap.html == html
    assert Path(snap.content_path).exists()
    assert Path(snap.headers_path).exists()
    assert Path(snap.metadata_path).exists()
    meta = json.loads(Path(snap.metadata_path).read_text(encoding="utf-8"))
    assert meta["mevzuat_no"] == "5237"
    assert meta["content_hash"]
