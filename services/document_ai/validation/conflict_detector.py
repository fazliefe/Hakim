"""Cross-document field conflicts. Never picks a 'correct' value."""

from __future__ import annotations

import re
from collections import defaultdict

from hakim_legal_schema.bundle import FieldConflict
from hakim_legal_schema.document import StructuredDocument

COMPARE_FIELDS = frozenset(
    {
        "case_no",
        "decision_no",
        "document_no",
        "notification_date",
        "date",
        "person_name",
    }
)


def _norm(value: str) -> str:
    return re.sub(r"[\s./-]+", "", (value or "").casefold())


def detect_conflicts(documents: list[StructuredDocument]) -> list[FieldConflict]:
    by_field: dict[str, list[dict[str, str]]] = defaultdict(list)
    for doc in documents:
        for field in doc.fields:
            if field.name not in COMPARE_FIELDS:
                continue
            if not field.value or field.value == "[okunamadı]":
                continue
            by_field[field.name].append(
                {
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "value": field.value,
                }
            )
    conflicts: list[FieldConflict] = []
    for name, rows in by_field.items():
        unique = {_norm(row["value"]) for row in rows if _norm(row["value"])}
        if len(unique) < 2:
            continue
        conflicts.append(FieldConflict(field=name, values=rows))
    return conflicts
