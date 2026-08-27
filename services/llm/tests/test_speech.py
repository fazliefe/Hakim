from __future__ import annotations

import io
import json
import urllib.error

from llm.client import OllamaError
from llm.speech import transcribe_audio, whisper_configured


def test_whisper_configured_false_without_any_key(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_WHISPER_API_KEY", raising=False)
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    assert whisper_configured() is False


def test_whisper_configured_true_with_dedicated_key(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_WHISPER_API_KEY", "sk-whisper-test")
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    assert whisper_configured() is True


def test_whisper_configured_falls_back_to_llm_key(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_WHISPER_API_KEY", raising=False)
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-llm-test")
    assert whisper_configured() is True


def test_transcribe_audio_rejects_empty_bytes(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    try:
        transcribe_audio(b"")
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "boş" in str(exc).lower()


def test_transcribe_audio_without_key_raises_immediately(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_WHISPER_API_KEY", raising=False)
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    try:
        transcribe_audio(b"fake-audio-bytes")
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "HAKIM_WHISPER_API_KEY" in str(exc)


def test_transcribe_audio_sends_multipart_and_returns_text(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    captured: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"text": "şikayet süresi nedir"}).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = request.data
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = transcribe_audio(b"\x00\x01fake-audio", filename="kayit.webm", content_type="audio/webm")

    assert text == "şikayet süresi nedir"
    assert captured["url"].endswith("/audio/transcriptions")
    # Header adı urllib tarafından title-case'e çevriliyor (Content-type).
    assert "multipart/form-data; boundary=" in captured["headers"]["Content-type"]
    assert b'name="model"' in captured["body"]
    assert b'name="file"; filename="kayit.webm"' in captured["body"]
    assert b"\x00\x01fake-audio" in captured["body"]


def test_transcribe_audio_recovers_after_transient_5xx(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"text": "tekrar denendi"}).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise urllib.error.HTTPError(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                503,
                "Service Unavailable",
                hdrs=None,
                fp=io.BytesIO(b'{"error": "server busy"}'),
            )
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = transcribe_audio(b"fake-audio")
    assert text == "tekrar denendi"
    assert attempts["n"] == 2


def test_transcribe_audio_400_raises_with_detail_no_retry(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    attempts = {"n": 0}

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        raise urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error": "invalid audio"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    try:
        transcribe_audio(b"fake-audio")
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "400" in str(exc)
    assert attempts["n"] == 1


def test_transcribe_audio_empty_text_response_raises(monkeypatch) -> None:
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"text": "   "}).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=None: _Resp())
    try:
        transcribe_audio(b"fake-audio")
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "boş" in str(exc).lower()
