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
    spec = load_belge(belge_id)
    writing = spec.get("writing") or {}
    sections = spec.get("sections") or []
    order = "\n".join(f"- {row['id']}: {row['label']}" for row in sections)
    must = "\n".join(f"- {item}" for item in writing.get("must") or [])
    must_not = "\n".join(f"- {item}" for item in writing.get("must_not") or [])
    required = (spec.get("parsed") or {}).get("required") or []
    example = json.dumps(spec.get("example") or {}, ensure_ascii=False)
    return (
        f"Belge: {spec['title']}\n"
        f"Makam: {spec.get('makam', '')}\n"
        f"Dayanak: {', '.join(spec.get('legal_basis') or [])}\n"
        f"Üslup: {writing.get('tone', '')}\n\n"
        f"Bölüm sırası:\n{order}\n\n"
        f"Zorunlu:\n{must}\n\n"
        f"Yasak:\n{must_not}\n\n"
        "Yalnızca JSON döndür. Zorunlu anahtarlar: "
        + ", ".join(required)
        + "\n\nÖrnek JSON:\n"
        + example
    )


def system_prompt(module_id: str) -> str:
    spec = load_format(module_id)
    writing = spec.get("writing") or {}
    parsed = spec.get("parsed") or {}
    must = "\n".join(f"- {item}" for item in writing.get("must") or [])
    must_not = "\n".join(f"- {item}" for item in writing.get("must_not") or [])
    return (
        f"Modül: {spec['title']}\n"
        f"Dil: {spec.get('language', 'tr')}\n"
        f"Üslup: {writing.get('tone', '')}\n"
        f"Atıf: {writing.get('citations', '')}\n\n"
        f"Zorunlu:\n{must}\n\n"
        f"Yasak:\n{must_not}\n\n"
        "Yalnızca JSON döndür. Şema alanları:\n"
        f"{json.dumps(parsed.get('properties'), ensure_ascii=False)}\n"
        "Zorunlu anahtarlar: "
        + ", ".join(parsed.get("required") or [])
        + "\n\nÖrnek JSON:\n"
        + json.dumps(spec.get("example") or {}, ensure_ascii=False)
    )
