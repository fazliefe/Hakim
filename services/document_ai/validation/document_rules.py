from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from hakim_config import repo_root


@lru_cache(maxsize=1)
def load_document_rules() -> dict[str, Any]:
    path = repo_root() / "config" / "document_rules.yaml"
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def rules_for(document_type: str) -> dict[str, Any]:
    rules = load_document_rules()
    spec = rules.get(document_type) or rules.get("belirsiz") or {}
    return spec if isinstance(spec, dict) else {}
