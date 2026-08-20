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


def test_api_payload_url() -> None:
    assert api_payload_url("https://api.groq.com/openai/v1") == "https://api.groq.com/openai/v1/chat/completions"


def test_api_configured_reads_env(monkeypatch) -> None:
    monkeypatch.delenv("HAKIM_LLM_API_KEY", raising=False)
    assert api_configured() is False
    monkeypatch.setenv("HAKIM_LLM_API_KEY", "sk-test")
    assert api_configured() is True
