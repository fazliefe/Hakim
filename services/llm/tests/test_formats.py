from __future__ import annotations

from llm.formats import formats_index, load_format, system_prompt, validate_parsed


def test_index_lists_four_modules() -> None:
    ids = {item["id"] for item in formats_index()["modules"]}
    assert ids == {"arastirma", "evrak", "surec", "islem"}


def test_each_format_example_matches_parsed_required() -> None:
    for module_id in ("arastirma", "evrak", "surec", "islem"):
        spec = load_format(module_id)
        errors = validate_parsed(module_id, spec["example"])
        assert errors == [], (module_id, errors)


def test_system_prompt_is_turkish_and_forbids_invention() -> None:
    text = system_prompt("arastirma")
    assert "JSON" in text
    assert "uydurma" in text.lower() or "Yasak" in text
    assert "ozet" in text


def test_belge_catalog_lists_ceza_and_idare_templates() -> None:
    from llm.formats import belgeler_index

    ids = {item["id"] for item in belgeler_index()["documents"]}
    assert {
        "sikayet",
        "suc_duyurusu",
        "cevap",
        "itiraz",
        "istinaf",
        "temyiz",
        "katilma",
        "bireysel_basvuru",
        "idari_dava",
        "tahliye",
        "adli_kontrol_itiraz",
    } <= ids


def test_each_belge_example_fills_required_fields() -> None:
    from llm.formats import belgeler_index, load_belge, validate_belge

    for item in belgeler_index()["documents"]:
        spec = load_belge(item["id"])
        errors = validate_belge(item["id"], spec["example"])
        assert errors == [], (item["id"], errors)
        assert spec["sections"], item["id"]


def test_sikayet_is_not_an_indictment() -> None:
    from llm.formats import belge_system_prompt, load_belge

    spec = load_belge("sikayet")
    banned = " ".join(spec["writing"]["must_not"])
    assert "İddianame" in banned or "iddianame" in banned.lower()
    prompt = belge_system_prompt("sikayet")
    assert "Şikayet dilekçesi" in prompt
    assert "TCK m.73" in prompt
