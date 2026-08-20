from llm.client import chat_payload


def test_chat_payload_keeps_model_warm_without_token_cap() -> None:
    body = chat_payload([{"role": "user", "content": "test"}])
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["keep_alive"] == "30m"
    assert "num_predict" not in body.get("options", {})
    assert "num_ctx" not in body.get("options", {})
