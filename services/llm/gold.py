"""Colab'dan gelen senaryo → dilekçe altını. Fine-tune değil; few-shot / eval.

Ticaret-hukuk ve AYM norm denetimi satırları tutulmaz. Dosya yoksa sessizce boş döner.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm.formats import load_belge, validate_belge

ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = ROOT / "data" / "gold" / "dilekce_ornekleri.jsonl"

SENARYO_CHARS = 700


def _court(row: dict[str, Any]) -> str:
    return str((row.get("emsal") or {}).get("court") or "").lower()


def _source(row: dict[str, Any]) -> str:
    return str((row.get("emsal") or {}).get("source") or "").lower()


def accept_row(row: dict[str, Any]) -> bool:
    action = str(row.get("action") or "")
    if not action:
        return False
    try:
        load_belge(action)
    except FileNotFoundError:
        return False
    if _source(row) == "aym_norm":
        return False
    court = _court(row)
    if "ticaret" in court:
        return False
    if "hukuk" in court and "ceza" not in court:
        return False
    body = row.get("dilekce")
    if not isinstance(body, dict):
        return False
    if validate_belge(action, body):
        return False
    emsal = row.get("emsal") or {}
    if not (emsal.get("esas_no") or emsal.get("atif")):
        return False
    return True


def load_gold(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or GOLD_PATH
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if accept_row(row):
            rows.append(row)
    return rows


def _compact_dilekce(action: str, body: dict[str, Any]) -> dict[str, Any]:
    required = list((load_belge(action).get("parsed") or {}).get("required") or [])
    out: dict[str, Any] = {}
    for key in required:
        if key in body:
            out[key] = body[key]
    if body.get("emsal_atif"):
        out["emsal_atif"] = body["emsal_atif"]
    mad = body.get("hukuki_nitelendirme")
    if isinstance(mad, list) and mad:
        out["hukuki_nitelendirme"] = mad[:4]
    return out


def fewshot_for(action: str, path: Path | None = None) -> dict[str, str] | None:
    for row in load_gold(path):
        if row.get("action") != action:
            continue
        emsal = row.get("emsal") or {}
        atif = str(emsal.get("atif") or "").strip()
        senaryo = " ".join(str(row.get("senaryo") or "").split())[:SENARYO_CHARS]
        user = (
            "Senaryo (bu olay için dilekçe yaz; emsal künyesini kullan, yeni madde uydurma):\n"
            f"{senaryo}\n\n"
            f"Emsal künye: {atif}"
        )
        assistant = json.dumps(_compact_dilekce(action, row["dilekce"]), ensure_ascii=False)
        return {"user": user, "assistant": assistant}
    return None
