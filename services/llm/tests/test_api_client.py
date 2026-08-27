from llm.api_client import api_configured, api_payload_url, _headers


def test_api_payload_url() -> None:
    assert api_payload_url("https://api.groq.com/openai/v1") == "https://api.groq.com/openai/v1/chat/completions"


def test_api_configured_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    assert api_configured() is False
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    assert api_configured() is True


def test_headers_are_not_python_urllib() -> None:
    headers = _headers("sk-test")
    assert "Python-urllib" not in headers["User-Agent"]
    assert headers["User-Agent"].startswith("HAKIM/")
    assert headers["Authorization"] == "Bearer sk-test"


def test_http_error_records_usage_then_raises(monkeypatch) -> None:
    import io
    import json
    import urllib.error

    from llm.api_client import _api_chat_body
    from llm.client import OllamaError
    from llm.usage import peek_usage, reset_usage

    reset_usage()
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    err = {
        "error": {"message": "Failed to validate JSON", "code": "json_validate_failed"},
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        "model": "openai/gpt-oss-20b",
    }

    def boom(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "https://api.groq.com/openai/v1/chat/completions",
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(json.dumps(err).encode("utf-8")),
        )

    monkeypatch.setattr("urllib.request.urlopen", boom)
    try:
        _api_chat_body([{"role": "user", "content": "hi"}], json_mode=True)
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "400" in str(exc)
    usage = peek_usage()
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 20


def test_json_validate_retry_drops_json_mode(monkeypatch) -> None:
    import io
    import json
    import urllib.error
    from types import SimpleNamespace

    from llm.api_client import api_chat
    from llm.usage import peek_usage, reset_usage

    reset_usage()
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    payloads: list[dict] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": '{"ok": true}'}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                    "model": "openai/gpt-oss-20b",
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        payloads.append(json.loads(request.data.decode("utf-8")))
        if len(payloads) == 1:
            raise urllib.error.HTTPError(
                "https://api.groq.com/openai/v1/chat/completions",
                400,
                "Bad Request",
                hdrs=None,
                fp=io.BytesIO(
                    json.dumps(
                        {
                            "error": {
                                "message": "Failed to validate JSON",
                                "code": "json_validate_failed",
                            }
                        }
                    ).encode("utf-8")
                ),
            )
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "llm.api_client.get_models",
        lambda: SimpleNamespace(
            llm_url="https://api.groq.com/openai/v1",
            llm_model="openai/gpt-oss-20b",
            llm_temperature=0.2,
            llm_max_tokens=900,
            llm_timeout=25,
            llm_disable_reasoning=False,
        ),
    )
    text = api_chat([{"role": "user", "content": "hi"}], json_mode=True)
    assert '{"ok": true}' in text
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]
    usage = peek_usage()
    assert usage.prompt_tokens == 12
    assert usage.completion_tokens == 4


def test_transient_503_recovers_via_retry(monkeypatch) -> None:
    """services/llm/retry.py::call_with_retry ile _api_chat_body artık tek bir
    5xx'te pes etmiyor — bkz. o modül."""
    import io
    import json
    import urllib.error
    from types import SimpleNamespace

    from llm.api_client import _api_chat_body

    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "llm.api_client.get_models",
        lambda: SimpleNamespace(
            llm_url="https://evren-llmapi.ssyz.org.tr/v1",
            llm_model="llm-fast",
            llm_temperature=0.2,
            llm_max_tokens=3072,
            llm_timeout=120,
            llm_disable_reasoning=False,
        ),
    )
    attempts = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "merhaba"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise urllib.error.HTTPError(
                "https://evren-llmapi.ssyz.org.tr/v1/chat/completions",
                503,
                "Service Unavailable",
                hdrs=None,
                fp=io.BytesIO(b'{"error": "server busy"}'),
            )
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    text = _api_chat_body([{"role": "user", "content": "hi"}], json_mode=False)
    assert text == "merhaba"
    assert attempts["n"] == 2


def test_disable_reasoning_sends_chat_template_kwargs(monkeypatch) -> None:
    """evren (vLLM/Qwen3) thinking modu açık geldiği için karmaşık promptlarda
    reasoning izi max_tokens'ı tüketip boş içerik döndürüyordu — canlıda
    doğrulandı. `disable_reasoning: true` bunu istek gövdesinde kapatmalı."""
    import io
    import json
    from types import SimpleNamespace

    from llm.api_client import _api_chat_body

    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    payloads: list[dict] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "llm.api_client.get_models",
        lambda: SimpleNamespace(
            llm_url="https://evren-llmapi.ssyz.org.tr/v1",
            llm_model="llm-fast",
            llm_temperature=0.2,
            llm_max_tokens=3072,
            llm_timeout=120,
            llm_disable_reasoning=True,
        ),
    )
    _api_chat_body([{"role": "user", "content": "hi"}], json_mode=True)
    assert payloads[0]["chat_template_kwargs"] == {"enable_thinking": False}
