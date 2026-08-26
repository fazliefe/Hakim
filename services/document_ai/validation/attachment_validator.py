"""Declared attachments vs numbered Ek sequence. Does not judge the file."""

from __future__ import annotations

import re

from hakim_legal_schema.document import StructuredWarning

_EK_NUM = re.compile(r"\[?\s*ek\.?\s*(\d+)\b", re.I)


def attachment_warnings(text: str, declared: list[str] | None = None) -> list[StructuredWarning]:
    warnings: list[StructuredWarning] = []
    numbers = {int(match.group(1)) for match in _EK_NUM.finditer(text or "") if 1 <= int(match.group(1)) <= 40}
    if numbers:
        missing = [n for n in range(1, max(numbers) + 1) if n not in numbers]
        if missing:
            labels = ", ".join(f"Ek-{n}" for n in missing)
            warnings.append(
                StructuredWarning(
                    code="missing_attachment_number",
                    message=f"Numaralı ek sırası kopuk görünüyor: {labels} anılmıyor.",
                    severity="warning",
                )
            )
    names = [item.strip() for item in (declared or []) if item and item.strip()]
    if names:
        preview = "; ".join(names[:6])
        extra = f" (+{len(names) - 6})" if len(names) > 6 else ""
        warnings.append(
            StructuredWarning(
                code="declared_attachments",
                message=f"Metinde {len(names)} ek anılıyor: {preview}{extra}. Paket henüz ayrı dosya olarak yüklenmedi.",
                severity="info",
            )
        )
    return warnings
