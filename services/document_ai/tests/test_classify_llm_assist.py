from __future__ import annotations

import json

from document_ai.classify import classify_document, classify_document_llm_assist


def _chat(reply: str):
    def fn(messages: list[dict[str, str]]) -> str:
        return reply

    return fn


def test_llm_assist_resolves_belirsiz_with_allowed_label() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)
    assert base.document_type == "belirsiz"

    reply = json.dumps(
        {
            "document_type": "ust_yazi",
            "legal_nature": "kamu",
            "evidence": "kurumumuza ulaşmış olup incelenmesi",
        }
    )
    assisted = classify_document_llm_assist(text, base, chat_fn=_chat(reply))
    assert assisted is not None
    assert assisted.document_type == "ust_yazi"
    assert assisted.legal_nature == "kamu"
    # unit/stage/remedies hâlâ deterministik tablolardan geliyor, LLM'den değil.
    assert assisted.unit == "Evrak kayıt ve havale"
    assert assisted.confidence == 0.6
    assert "kurumumuza ulaşmış olup incelenmesi" in assisted.evidence_span


def test_llm_assist_rejects_label_outside_closed_list() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)
    reply = json.dumps({"document_type": "faks", "legal_nature": "kamu", "evidence": ""})
    assert classify_document_llm_assist(text, base, chat_fn=_chat(reply)) is None


def test_llm_assist_no_op_when_llm_also_unsure() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)
    reply = json.dumps({"document_type": "belirsiz", "legal_nature": "belirsiz", "evidence": ""})
    assert classify_document_llm_assist(text, base, chat_fn=_chat(reply)) is None


def test_llm_assist_no_op_when_llm_repeats_rule_engine_result() -> None:
    text = (
        "T.C. ANKARA 4. AĞIR CEZA MAHKEMESİ GEREKÇELİ KARAR "
        "Sanığın nitelikli dolandırıcılık suçundan mahkûmiyetine karar verildi. "
        "Tebliğ tarihi: 14.08.2026"
    )
    base = classify_document(text)
    assert base.document_type == "mahkeme_karari"
    reply = json.dumps(
        {"document_type": "mahkeme_karari", "legal_nature": "ceza", "evidence": "GEREKÇELİ KARAR"}
    )
    assert classify_document_llm_assist(text, base, chat_fn=_chat(reply)) is None


def test_llm_assist_drops_evidence_not_found_in_text_but_keeps_label() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)
    reply = json.dumps(
        {"document_type": "ust_yazi", "legal_nature": "kamu", "evidence": "metinde hiç geçmeyen bir alıntı"}
    )
    assisted = classify_document_llm_assist(text, base, chat_fn=_chat(reply))
    assert assisted is not None
    assert assisted.document_type == "ust_yazi"
    assert "metinde hiç geçmeyen" not in assisted.evidence_span


def test_llm_assist_ignores_malformed_json() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)
    assert classify_document_llm_assist(text, base, chat_fn=_chat("bunlar JSON değil")) is None


def test_llm_assist_ignores_chat_fn_exception() -> None:
    text = "Bu evrak kurumumuza ulaşmış olup incelenmesi gerekmektedir."
    base = classify_document(text)

    def boom(messages: list[dict[str, str]]) -> str:
        raise RuntimeError("ağ hatası")

    assert classify_document_llm_assist(text, base, chat_fn=boom) is None
