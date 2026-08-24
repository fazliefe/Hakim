from document_ai.gaps import apply_gap_placeholders, diagnose_islem_gaps, merge_placeholder_gaps


def test_short_complaint_lists_identity_and_fact_gaps() -> None:
    gaps = diagnose_islem_gaps("sikayet", "paramı aldılar şikayet etmek istiyorum", {}, {})
    ids = {item["id"] for item in gaps}
    assert "sikayetci" in ids
    assert "olay_tarihi" in ids
    assert "delil" in ids
    assert "adres" in ids
    assert "il" in ids
    assert all("hint" in item and "label" in item for item in gaps)


def test_filled_complaint_skips_known_slots() -> None:
    text = (
        "Ben Ali Deneme, 12.03.2025 tarihinde Ankara Çankaya Mahallesi Deneme Sokak "
        "No: 4'te banka hesabımdan Mehmet Ornek tarafından beş bin lira çekildi. "
        "Dekontlarım var. Şikayetçiyim."
    )
    ids = {item["id"] for item in diagnose_islem_gaps("sikayet", text, {}, {})}
    assert "sikayetci" not in ids
    assert "olay_tarihi" not in ids
    assert "olay_yeri" not in ids
    assert "il" not in ids
    assert "adres" not in ids
    assert "delil" not in ids
    assert "sikayet_edilen" not in ids


def test_institution_title_is_not_treated_as_complainant_name() -> None:
    text = "Cumhuriyet Başsavcılığına şikayet etmek istiyorum, paramı aldılar."
    ids = {item["id"] for item in diagnose_islem_gaps("sikayet", text, {}, {})}
    assert "sikayetci" in ids


def test_generic_court_word_still_asks_for_the_court() -> None:
    text = "Mahkeme kararına itiraz etmek istiyorum."
    ids = {item["id"] for item in diagnose_islem_gaps("itiraz", text, {}, {})}
    assert "mahkeme" in ids
    assert "teblig" in ids
    assert "ad_soyad" in ids
    assert "adres" in ids
    assert "il" in ids


def test_bare_date_is_not_teblig_for_istinaf() -> None:
    text = "12.03.2026 tarihli kararı istinaf etmek istiyorum."
    ids = {item["id"] for item in diagnose_islem_gaps("istinaf", text, {}, {})}
    assert "teblig" in ids


def test_cevap_lists_sheet_and_case_gaps() -> None:
    text = "İddianame tebliğ edildi. Cevap dilekçesi vermek istiyorum."
    ids = {item["id"] for item in diagnose_islem_gaps("cevap", text, {}, {})}
    assert "teblig" in ids
    assert "esas" in ids
    assert "adres" in ids
    assert "ad_soyad" in ids


def test_merge_placeholders_adds_visible_sheet_gaps() -> None:
    gaps = merge_placeholder_gaps([], "Adres: «[adres]»\n«[il]»\n«[ad soyad]»")
    ids = {item["id"] for item in gaps}
    assert ids >= {"adres", "il", "ad_soyad"}


def test_apply_placeholders_marks_missing_name() -> None:
    parsed = apply_gap_placeholders(
        {"sikayetci": "Şikayetçi", "olay": "paramı aldılar"},
        [{"id": "sikayetci", "label": "Şikayetçi adı-soyadı", "hint": "adınızı yazın"}],
        "paramı aldılar",
    )
    assert "«[" in parsed["sikayetci"]
    assert parsed["eksikler"]
