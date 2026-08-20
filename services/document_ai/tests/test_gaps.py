from document_ai.gaps import apply_gap_placeholders, diagnose_islem_gaps


def test_short_complaint_lists_identity_and_fact_gaps() -> None:
    gaps = diagnose_islem_gaps("sikayet", "paramı aldılar şikayet etmek istiyorum", {}, {})
    ids = {item["id"] for item in gaps}
    assert "sikayetci" in ids
    assert "olay_tarihi" in ids
    assert "delil" in ids
    assert all("hint" in item and "label" in item for item in gaps)


def test_filled_complaint_skips_known_slots() -> None:
    text = (
        "Ben Ali Deneme, 12.03.2025 tarihinde Ankara'da banka hesabımdan "
        "Mehmet Ornek tarafından beş bin lira çekildi. Dekontlarım var. Şikayetçiyim."
    )
    ids = {item["id"] for item in diagnose_islem_gaps("sikayet", text, {}, {})}
    assert "sikayetci" not in ids
    assert "olay_tarihi" not in ids
    assert "olay_yeri" not in ids
    assert "delil" not in ids
    assert "sikayet_edilen" not in ids


def test_apply_placeholders_marks_missing_name() -> None:
    parsed = apply_gap_placeholders(
        {"sikayetci": "Şikayetçi", "olay": "paramı aldılar"},
        [{"id": "sikayetci", "label": "Şikayetçi adı-soyadı", "hint": "adınızı yazın"}],
        "paramı aldılar",
    )
    assert "«[" in parsed["sikayetci"]
    assert parsed["eksikler"]
