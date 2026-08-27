from __future__ import annotations

import io
import urllib.error

from llm.retry import call_with_retry


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://example.test/x", code, "err", hdrs=None, fp=io.BytesIO(b"{}")
    )


def test_recovers_after_one_transient_5xx(monkeypatch) -> None:
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(503)
        return "ok"

    assert call_with_retry(fn) == "ok"
    assert calls["n"] == 2


def test_recovers_after_connection_error(monkeypatch) -> None:
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("connection reset")
        return "ok"

    assert call_with_retry(fn) == "ok"
    assert calls["n"] == 2


def test_does_not_retry_on_4xx(monkeypatch) -> None:
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("sleep çağrılmamalıydı")))
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _http_error(401)

    try:
        call_with_retry(fn)
        raise AssertionError("expected HTTPError")
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    assert calls["n"] == 1


def test_gives_up_after_all_attempts_exhausted(monkeypatch) -> None:
    monkeypatch.setattr("llm.retry.time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _http_error(503)

    try:
        call_with_retry(fn, attempts=3)
        raise AssertionError("expected HTTPError")
    except urllib.error.HTTPError as exc:
        assert exc.code == 503
    assert calls["n"] == 3


def test_backoff_delay_grows_exponentially(monkeypatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr("llm.retry.time.sleep", delays.append)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise _http_error(503)

    try:
        call_with_retry(fn, attempts=3, base_delay=0.5, max_delay=4.0)
    except urllib.error.HTTPError:
        pass
    assert delays == [0.5, 1.0]  # attempts arasında 2 kez bekleniyor, son denemede beklenmiyor
