from __future__ import annotations

from hakim_legal_schema.document import ExtractedField, StructuredWarning


def warning(code: str, message: str, *, field: str | None = None, page: int | None = None) -> StructuredWarning:
    return StructuredWarning(code=code, message=message, field=field, page=page)


def unread_fields(fields: list[ExtractedField]) -> list[ExtractedField]:
    return [item for item in fields if (item.value or "").strip() in {"", "[okunamadı]"}]
