from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


class CurlJson:
    """Windows-safe curl client for JSON court APIs."""

    def __init__(self, timeout: int = 90, default_headers: dict[str, str] | None = None) -> None:
        self.timeout = timeout
        self.default_headers = default_headers or {}

    def _headers(self, extra: dict[str, str] | None) -> dict[str, str]:
        merged = dict(self.default_headers)
        if extra:
            merged.update(extra)
        return merged

    def _header_args(self, extra: dict[str, str] | None) -> list[str]:
        args: list[str] = []
        for key, value in self._headers(extra).items():
            args.extend(["-H", f"{key}: {value}"])
        return args

    def get(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any] | str:
        full = url if not params else f"{url}?{urlencode(params, doseq=True)}"
        cmd = ["curl.exe", "-k", "-L", "-s", "--max-time", str(self.timeout), "-A", "Mozilla/5.0"]
        cmd.extend(self._header_args(headers))
        cmd.append(full)
        return self._run(cmd, json_mode=False)

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        full = url if not params else f"{url}?{urlencode(params, doseq=True)}"
        cmd = ["curl.exe", "-k", "-L", "-s", "--max-time", str(self.timeout), "-A", "Mozilla/5.0"]
        cmd.extend(self._header_args(headers))
        cmd.append(full)
        return self._run(cmd, json_mode=True)

    def get_bytes(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> bytes:
        full = url if not params else f"{url}?{urlencode(params, doseq=True)}"
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as handle:
            path = handle.name
        try:
            cmd = [
                "curl.exe",
                "-k",
                "-L",
                "-s",
                "--max-time",
                str(self.timeout),
                "-A",
                "Mozilla/5.0",
                "-o",
                path,
            ]
            cmd.extend(self._header_args(headers))
            cmd.append(full)
            completed = subprocess.run(cmd, capture_output=True, check=False)
            data = Path(path).read_bytes()
            if completed.returncode != 0 and not data:
                raise RuntimeError(completed.stderr.decode("utf-8", errors="replace") or "curl failed")
            return data
        finally:
            Path(path).unlink(missing_ok=True)

    def post_json(self, url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> Any:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            path = handle.name
        try:
            cmd = [
                "curl.exe",
                "-k",
                "-L",
                "-s",
                "--max-time",
                str(self.timeout),
                "-A",
                "Mozilla/5.0",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json; charset=UTF-8",
                "-H",
                "Accept: application/json",
            ]
            cmd.extend(self._header_args(headers))
            cmd.extend(["--data-binary", f"@{path}", url])
            return self._run(cmd, json_mode=True)
        finally:
            Path(path).unlink(missing_ok=True)

    def _run(self, cmd: list[str], *, json_mode: bool) -> Any:
        completed = subprocess.run(cmd, capture_output=True, check=False)
        text = completed.stdout.decode("utf-8", errors="replace")
        if completed.returncode != 0 and not text:
            raise RuntimeError(completed.stderr.decode("utf-8", errors="replace") or "curl failed")
        if json_mode:
            text = text.strip()
            if not text.startswith("{") and not text.startswith("["):
                raise RuntimeError(f"expected JSON, got: {text[:180]}")
            return json.loads(text) if text else {}
        return text
