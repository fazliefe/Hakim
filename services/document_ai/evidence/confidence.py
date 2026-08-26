from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from hakim_config import repo_root
from hakim_legal_schema.document import ConfidenceBand, ExtractedField

CRITICAL_FIELDS = frozenset({"notification_date", "case_no", "decision_no", "document_no"})


@lru_cache(maxsize=1)
def _rules() -> dict[str, Any]:
    path = repo_root() / "config" / "confidence_rules.yaml"
    if not path.is_file():
        return {"default": {"trusted": 0.90, "review": 0.70}}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {"default": {"trusted": 0.90, "review": 0.70}}


def band_for(name: str, confidence: float) -> ConfidenceBand:
    rules = _rules()
    spec = rules.get(name) if isinstance(rules.get(name), dict) else None
    default = rules.get("default") if isinstance(rules.get("default"), dict) else {}
    trusted = float((spec or default).get("trusted") or default.get("trusted") or 0.90)
    review = float((spec or default).get("review") or default.get("review") or 0.70)
    if confidence >= trusted:
        return "trusted"
    if confidence >= review:
        return "review"
    return "uncertain"


def apply_bands(fields: list[ExtractedField]) -> list[ExtractedField]:
    out: list[ExtractedField] = []
    for field in fields:
        out.append(field.model_copy(update={"band": band_for(field.name, field.confidence)}))
    return out
