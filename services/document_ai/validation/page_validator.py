"""Detect missing page numbers from the transcribed text. No legal conclusion."""

from __future__ import annotations

import re

from hakim_legal_schema.document import StructuredWarning

_PAGE_FRAC = re.compile(
    r"(?:sayfa\s+|s\.\s*)(\d{1,3})\s*/\s*(\d{1,3})"
    r"|(\d{1,3})\s*/\s*(\d{1,3})\s*(?:sayfa|\.?\s*s\.)",
    re.I,
)


def page_warnings(text: str) -> list[StructuredWarning]:
    found: list[tuple[int, int]] = []
    for match in _PAGE_FRAC.finditer(text or ""):
        if match.group(1):
            current, total = int(match.group(1)), int(match.group(2))
        else:
            current, total = int(match.group(3)), int(match.group(4))
        if total < 2 or current < 1 or current > total or total > 80:
            continue
        found.append((current, total))
    if not found:
        return []
    totals = {item[1] for item in found}
    if len(totals) != 1:
        return [
            StructuredWarning(
                code="page_total_mismatch",
                message="Belgede birden fazla toplam sayfa sayısı geçiyor. Hangisinin doğru olduğu söylenmez.",
                severity="warning",
            )
        ]
    total = next(iter(totals))
    seen = {item[0] for item in found}
    missing = [str(n) for n in range(1, total + 1) if n not in seen]
    if not missing:
        return []
    return [
        StructuredWarning(
            code="missing_page",
            message=f"Sayfa numaralarına göre eksik görünen sayfa: {', '.join(missing)} / {total}.",
            severity="warning",
        )
    ]
