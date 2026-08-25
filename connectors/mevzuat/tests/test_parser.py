from __future__ import annotations

from datetime import date
from pathlib import Path

from mevzuat.parser import CHARSET_META_RE, _strip_footnotes, parse_mevzuat_html

FIXTURE = Path(__file__).parent / "fixtures" / "tck_snippet.html"


def test_strip_footnotes_removes_single_marker() -> None:
    assert _strip_footnotes("Trafik güvenliğini tehlikeye sokma [77]") == "Trafik güvenliğini tehlikeye sokma"


def test_strip_footnotes_removes_stacked_markers() -> None:
    """mevzuat.gov.tr birden fazla değişiklik dipnotunu art arda ekleyebilir
    (örn. CMK m.173 başlığı '... itiraz [67] [68]') — tek regex.sub ile
    yalnızca sonuncusu silinip biri kalıyordu; hepsi temizlenmeli."""
    assert (
        _strip_footnotes("Cumhuriyet savcısının kararına itiraz [67] [68]")
        == "Cumhuriyet savcısının kararına itiraz"
    )


def test_strip_footnotes_no_marker_is_noop() -> None:
    assert _strip_footnotes("Hırsızlık") == "Hırsızlık"


def test_charset_meta_stripped_before_lxml_parses() -> None:
    """mevzuat.gov.tr HTML'i genelde yanlış 'charset=Windows-1254' bildirir
    (gövde zaten UTF-8'dir). lxml bu etikete bakıp bazı paragrafları yeniden
    (yanlış) kodlayarak mojibake üretebiliyor — CMK'da bu, madde 281'den
    sonrasının (m.291 dâhil, 285→356 madde) hiç ayrıştırılmamasına yol açtı.
    Ayrıştırmadan önce etiketi silmek bunu önler."""
    html = (
        '<html><head><meta http-equiv="Content-Type" '
        'content="text/html; charset=Windows-1254"></head>'
        "<body><p>Madde 1</p></body></html>"
    )
    assert CHARSET_META_RE.search(html) is not None
    assert CHARSET_META_RE.sub("", html).find("charset") == -1


def test_parse_extracts_law_metadata() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    assert result.number == "5237"
    assert "Türk Ceza Kanunu" in result.title or "TÜRK CEZA KANUNU" in result.title.upper()
    assert result.publication_date == date(2004, 10, 12)
    assert result.gazette_number == "25611"


def test_parse_extracts_article_1_and_158() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    by_no = {a.article_no: a for a in result.articles}
    assert "1" in by_no
    assert "158" in by_no
    assert "Nitelikli" in (by_no["158"].title or "")
    assert "Dolandırıcılık" in by_no["158"].text or "dolandırıcılık" in by_no["158"].text.lower()
    assert by_no["1"].text.startswith("Madde 1")


def test_article_ids_are_canonical() -> None:
    result = parse_mevzuat_html(FIXTURE.read_text(encoding="utf-8"), law_number="5237")
    a158 = next(a for a in result.articles if a.article_no == "158")
    assert a158.id == "law:5237:article:158"
    assert a158.version_id == "law:5237:article:158:v1"


def test_gecici_madde_does_not_collide_with_regular_madde() -> None:
    """İYUK'ta gerçek 'Madde 7' (dava açma süresi) ile 'Geçici Madde 7' aynı
    numarayı taşıyor. Postgres'te articles tablosu UNIQUE(document_id,
    article_no) zorunlu kılıyor — ikisi de düz "7" taşırsa ya id çakışması
    (sessiz üzerine yazma) ya da constraint ihlali olur (gerçekte olan buydu:
    İYUK'ta dava açma süresi maddesi kayboldu). "Geçici"/"Ek" önekli
    maddelerde article_no'nun kendisi ayrışmalı."""
    html = (
        "<html><body>"
        "<p>Madde 7 – Dava açma süresi altmış gündür.</p>"
        "<p>Diğer bir madde</p>"
        "<p>Geçici Madde 7 – Bu madde yürürlük tarihinde derdest davalarda uygulanır.</p>"
        "</body></html>"
    )
    result = parse_mevzuat_html(html, law_number="2577")
    assert len(result.articles) == 2
    ids = {a.id for a in result.articles}
    article_nos = {a.article_no for a in result.articles}
    assert len(ids) == 2, f"id çakışması: {ids}"
    assert len(article_nos) == 2, f"article_no çakışması: {article_nos}"
    real = next(a for a in result.articles if "altmış" in a.text)
    gecici = next(a for a in result.articles if "derdest" in a.text)
    assert real.id == "law:2577:article:7"
    assert real.article_no == "7"
    assert gecici.id == "law:2577:article:gecici-7"
    assert gecici.article_no == "gecici-7"
