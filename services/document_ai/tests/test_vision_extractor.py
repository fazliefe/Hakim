from __future__ import annotations

from document_ai.vision.extractor import fields_from_payload, normalize_date, sections_from_payload


def test_normalize_date_dd_mm_yyyy() -> None:
    assert normalize_date("14.08.2026") == "2026-08-14"
    assert normalize_date("4/6/2026") == "2026-06-04"
    assert normalize_date("okunamadı") is None


def test_fields_from_payload_allowlist_and_bands() -> None:
    fields = fields_from_payload(
        {
            "fields": [
                {
                    "name": "notification_date",
                    "value": "14.08.2026",
                    "page": 1,
                    "bbox": [0.62, 0.41, 0.82, 0.47],
                    "confidence": 0.91,
                },
                {
                    "name": "invented_field",
                    "value": "ignore",
                    "confidence": 0.99,
                },
                {
                    "name": "case_no",
                    "value": "2026/481",
                    "confidence": 0.99,
                },
            ]
        }
    )
    names = [item.name for item in fields]
    assert names == ["notification_date", "case_no"]
    date_field = fields[0]
    assert date_field.label == "Tebliğ Tarihi"
    assert date_field.normalized_value == "2026-08-14"
    assert date_field.band == "review"
    assert fields[1].band == "trusted"


def test_unknown_document_type_becomes_belirsiz(monkeypatch) -> None:
    from document_ai.vision import extractor

    monkeypatch.setattr(
        extractor,
        "vision_chat",
        lambda images, prompt, json_mode=False, model=None: (
            '{"document_type":"sahte_karar","document_type_confidence":0.9,"fields":[],"sections":[]}'
        ),
    )
    result = extractor.extract_from_images([("image/png", b"not-an-image")])
    assert result["document_type"] == "belirsiz"
    assert result["fields"] == []
    assert result["full_text"] == ""


def test_extract_keeps_full_text(monkeypatch) -> None:
    from document_ai.vision import extractor

    monkeypatch.setattr(
        extractor,
        "vision_chat",
        lambda images, prompt, json_mode=False, model=None: (
            '{"document_type":"tebligat","document_type_confidence":0.9,'
            '"full_text":"Tebliğ tarihi 14.08.2026","fields":[],"sections":[]}'
        ),
    )
    result = extractor.extract_from_images([("image/png", b"not-an-image")])
    assert result["full_text"] == "Tebliğ tarihi 14.08.2026"


def test_sections_from_payload() -> None:
    sections = sections_from_payload({"sections": [{"name": "body", "text": "tebliğ", "page": 1}]})
    assert sections[0].name == "body"
    assert sections[0].text == "tebliğ"


def test_parse_json_repairs_raw_newlines_in_full_text() -> None:
    from document_ai.vision.extractor import parse_vlm_json

    raw = """{
  "document_type": "dilekce",
  "document_type_confidence": 0.88,
  "full_text": "T.C.
ANKARA 4. SULH HUKUK MAHKEMESİNE
Davacı: Mehmet Yılmaz
",
  "fields": [{"name": "recipient", "value": "ANKARA 4. SULH HUKUK MAHKEMESİNE", "bbox": [0.2, 0.1, 0.8, 0.16], "confidence": 0.9}],
  "sections": []
}"""
    payload = parse_vlm_json(raw)
    assert payload["document_type"] == "dilekce"
    assert "Mehmet Yılmaz" in payload["full_text"]
    assert "\n" in payload["full_text"]


def test_parse_json_repairs_truncated_string() -> None:
    from document_ai.vision.extractor import parse_vlm_json

    raw = '{"document_type":"dilekce","document_type_confidence":0.9,"full_text":"T.C. ANKARA SULH'
    payload = parse_vlm_json(raw)
    assert payload["document_type"] == "dilekce"
    assert "ANKARA" in payload["full_text"]


def test_extract_joins_full_text_lines(monkeypatch) -> None:
    from document_ai.vision import extractor

    monkeypatch.setattr(
        extractor,
        "vision_chat",
        lambda images, prompt, json_mode=False, model=None: (
            '{"document_type":"dilekce","document_type_confidence":0.9,'
            '"full_text":["T.C.","Temyiz dilekçesidir."],"fields":[],"sections":[]}'
        ),
    )
    result = extractor.extract_from_images([("image/png", b"not-an-image")])
    assert result["full_text"] == "T.C.\nTemyiz dilekçesidir."
