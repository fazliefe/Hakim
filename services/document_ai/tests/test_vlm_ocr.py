from __future__ import annotations

import json
from types import SimpleNamespace

# 1x1 PNG
ONE_PX_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def test_transcribe_images_batches_two_and_uses_vision_model(monkeypatch) -> None:
    from document_ai import vlm_ocr

    payloads: list[dict] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            n = len(payloads) - 1
            return json.dumps(
                {"choices": [{"message": {"content": f"sayfa-{n}"}}], "usage": {}}
            ).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        body = json.loads(request.data.decode("utf-8"))
        payloads.append(body)
        return _Resp()

    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    text = vlm_ocr.transcribe_images(
        [
            ("image/png", ONE_PX_PNG),
            ("image/png", ONE_PX_PNG),
            ("image/png", ONE_PX_PNG),
        ]
    )
    assert "sayfa-0" in text
    assert "sayfa-1" in text
    assert len(payloads) == 2
    first = payloads[0]
    assert first["model"] == "llm-fast"
    content = first["messages"][0]["content"]
    images = [part for part in content if part.get("type") == "image_url"]
    assert len(images) == 2
    assert images[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert first.get("response_format") is None


def test_transcribe_images_requires_api_key(monkeypatch) -> None:
    from document_ai import vlm_ocr
    from llm.client import OllamaError

    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    try:
        vlm_ocr.transcribe_images([("image/png", ONE_PX_PNG)])
    except OllamaError as exc:
        assert "HAKIM_LLM_API_KEY" in str(exc)
    else:
        raise AssertionError("expected OllamaError")
