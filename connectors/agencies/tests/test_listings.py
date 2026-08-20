from __future__ import annotations

from agencies.listings import (
    parse_kvkk_listing,
    parse_rekabet_listing,
    parse_resmi_gazete_listing,
    parse_tbmm_son_tutanak,
    parse_uyusmazlik_listing,
)

REKABET_HTML = """
<div id="kararList">
  <table class="equalDivide">
    <tr><td>01.02.2025</td><td>25-01/1-1</td><td><a href="/KararlaIlgiliDavalar?kararId=abc-1">davalar</a></td></tr>
    <tr><td>15.01.2025</td><td>Birleşme</td></tr>
    <tr><td colspan="5"><a href="/Karar?kararId=abc-1">Örnek Rekabet Kurulu kararı</a></td></tr>
  </table>
</div>
"""

KVKK_HTML = """
<a href="https://www.kvkk.gov.tr/Icerik/8896/kisisel-verileri-koruma-kurulunun-yeni-yayinlanan-karar-ozetleri">
  Kişisel Verileri Koruma Kurulu'nun Yeni Yayınlanan Karar Özetleri
</a>
<a href="https://www.kvkk.gov.tr/Icerik/5419/kurul-kararlari">Kurul Kararları</a>
"""

UYUSMAZLIK_HTML = """
<table id="GridView1">
  <tr><th>Esas</th><th>Karar</th><th>Tarih</th><th>İşlem</th></tr>
  <tr>
    <td>2025/10</td><td>2026/2</td><td>12.01.2026</td>
    <td><a href="Uploads/2026-366.pdf">Görüntüle</a></td>
  </tr>
</table>
"""

RG_HTML = """
<a href="/eskiler/2026/08/20260815-1.htm">Motorlu Kara Taşıtlarının Kiralanması Hakkında Yönetmelik</a>
<a href="/eskiler/2026/08/20260815.pdf">PDF Görüntüle</a>
"""

TBMM_HTML = """
<title>TBMM - SON TUTANAK</title>
<embed src="https://cdn.tbmm.gov.tr/TbmmWeb/Tutanak/28/4/125/Ham/ec703c53-e6fb-4166-9f7d-0f9ae756a010.pdf#toolbar=1" />
"""


def test_parse_rekabet_listing() -> None:
    hits = parse_rekabet_listing(REKABET_HTML, fallback_year=2026)
    assert hits[0].key == "abc-1"
    assert hits[0].decision_no == "25-01/1-1"
    assert hits[0].title.startswith("Örnek")


def test_parse_kvkk_skips_index_and_keeps_summaries() -> None:
    hits = parse_kvkk_listing(KVKK_HTML, fallback_year=2026)
    assert len(hits) == 1
    assert "8896" in hits[0].key


def test_parse_uyusmazlik_grid() -> None:
    hits = parse_uyusmazlik_listing(UYUSMAZLIK_HTML, fallback_year=2026)
    assert hits[0].docket_no == "2025/10"
    assert hits[0].url.endswith("2026-366.pdf")


def test_parse_resmi_gazete_prefers_htm() -> None:
    hits = parse_resmi_gazete_listing(RG_HTML, fallback_year=2026)
    assert len(hits) == 1
    assert hits[0].key == "20260815-1"
    assert hits[0].year == 2026


def test_parse_tbmm_embed() -> None:
    hits = parse_tbmm_son_tutanak(TBMM_HTML, fallback_year=2026)
    assert hits[0].court == "tbmm"
    assert hits[0].url.endswith(".pdf")
