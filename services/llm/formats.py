from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FORMATS_DIR = ROOT / "data" / "formats"

REQUIRED_PARSED_KEYS = {
    "arastirma": ("ozet", "ana_kaynak_n", "gerekce", "kaynak_uyari"),
    "evrak": ("baslik", "tur_cumlesi", "tespitler", "ozet"),
    "surec": ("asama_cumlesi", "kanun_yollari", "sureler", "uyari"),
    "islem": ("makam", "konu", "aciklama", "tespitler", "talep", "onay_notu"),
}


def formats_index() -> dict[str, Any]:
    return json.loads((FORMATS_DIR / "index.json").read_text(encoding="utf-8"))


def load_format(module_id: str) -> dict[str, Any]:
    path = FORMATS_DIR / f"{module_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"yazım formatı yok: {module_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_parsed(module_id: str, payload: dict[str, Any]) -> list[str]:
    missing = [key for key in REQUIRED_PARSED_KEYS[module_id] if key not in payload]
    return [f"eksik alan: {key}" for key in missing]


BELGELER_DIR = FORMATS_DIR / "belgeler"


def belgeler_index() -> dict[str, Any]:
    return json.loads((BELGELER_DIR / "index.json").read_text(encoding="utf-8"))


def load_belge(belge_id: str) -> dict[str, Any]:
    path = BELGELER_DIR / f"{belge_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"belge kalıbı yok: {belge_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_belge(belge_id: str, payload: dict[str, Any]) -> list[str]:
    spec = load_belge(belge_id)
    required = list((spec.get("parsed") or {}).get("required") or [])
    return [f"eksik alan: {key}" for key in required if key not in payload]


def belge_system_prompt(belge_id: str) -> str:
    from llm.prompt import belge_system_prompt as build

    return build(belge_id)


def system_prompt(module_id: str) -> str:
    from llm.prompt import system_prompt as build

    return build(module_id)
