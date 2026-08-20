from __future__ import annotations

import io
import zipfile

from courts.aym import attachment_parts, udf_to_text
from courts.bedesten import COURT_TYPES, html_to_text


def test_html_to_text_strips_tags() -> None:
    html = "<html><body><b>7. Ceza Dairesi</b><p>Madde 158 dolandırıcılık</p></body></html>"
    text = html_to_text(html)
    assert "7. Ceza Dairesi" in text
    assert "Madde 158" in text
    assert "<p>" not in text


def test_bedesten_includes_uyap_emsal_types() -> None:
    assert COURT_TYPES["yerelhukuk"] == "YERELHUKUK"
    assert COURT_TYPES["istinafhukuk"] == "ISTINAFHUKUK"
    assert COURT_TYPES["kyb"] == "KYB"


def test_attachment_parts_from_kbb_url() -> None:
    folder, filename = attachment_parts(
        "/files/bireysel-basvuru/8f86e49f-3301-4b56-b27f-e27752ac5e7f_2023-73303.udf"
    )
    assert folder == "bireysel-basvuru"
    assert filename.endswith(".udf")


def test_udf_to_text_reads_cdata() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        '<template format_id="1.7"><content><![CDATA['
        "TÜRKİYE CUMHURİYETİ\nANAYASA MAHKEMESİ\nMadde 158 dolandırıcılık"
        "]]></content></template>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("content.xml", xml)
    text = udf_to_text(buffer.getvalue())
    assert "ANAYASA MAHKEMESİ" in text
    assert "Madde 158" in text
