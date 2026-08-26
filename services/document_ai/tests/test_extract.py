from __future__ import annotations

from document_ai.extract import extract_dates, extract_fields


def test_extract_dates_reads_labeled_teblig() -> None:
    text = "Karar tarihi: 01.08.2026\nTebliğ tarihi: 14.08.2026"
    dates = extract_dates(text)
    assert dates["teblig"].isoformat() == "2026-08-14"
    assert dates["karar"].isoformat() == "2026-08-01"


def test_extract_dates_does_not_guess_from_unrelated_bare_date() -> None:
    """Regresyon: canlı bir Yargıtay kararıyla doğrulandı — "Tebliğ tarihi"/
    "Karar tarihi" etiketi yoksa, metindeki ilgisiz bir tarihi (örn. eski bir
    kanun atfı, önceki bir usul işleminin tarihi) "tebliğ tarihi" sayıp süre
    motoruna vermek, yıllar öncesine düşen sahte bir son gün hesaplatıyordu."""
    text = (
        "Ceza Genel Kurulu 2004/1-219 E., 2005/35 K.\n"
        "Sanığın 25.02.2003 tarihli önceki celsede verdiği ifade ile "
        "765 sayılı Kanunun 448 inci maddesi uyarınca değerlendirilmiştir."
    )
    assert extract_dates(text) == {}


def test_extract_fields_tarih_does_not_guess_from_unrelated_bare_date() -> None:
    text = "Ceza Genel Kurulu 2004/1-219 E. 25.02.2003 tarihli ifadeye göre..."
    fields = extract_fields(text)
    assert "tarih" not in fields


def test_extract_fields_tarih_still_populated_from_labeled_date() -> None:
    text = "Tebliğ tarihi: 14.08.2026"
    fields = extract_fields(text)
    assert fields["tarih"] == "2026-08-14"


def test_extract_dates_reads_karar_verildi_closing_phrase() -> None:
    """Gerçek bir BAM/istinaf kararıyla doğrulandı — 'Karar tarihi:' etiketi
    hiç geçmiyor ama karar, standart kapanış cümlesiyle bitiyor: 'oy birliği
    ile karar verildi.04/07/2024'. Bu, gerçek karar tarihini kaçırmamak için
    'karar tarihi' kadar güvenilir bir işaret — rastgele bir tarih değil."""
    text = "...oy birliği ile karar verildi.04/07/2024"
    dates = extract_dates(text)
    assert dates["karar"].isoformat() == "2024-07-04"


def test_extract_dates_karar_verildi_with_space_and_dots() -> None:
    text = "Karar verildi. 01.03.2026"
    dates = extract_dates(text)
    assert dates["karar"].isoformat() == "2026-03-01"
