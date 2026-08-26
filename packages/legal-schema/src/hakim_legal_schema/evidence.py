from __future__ import annotations

from hakim_legal_schema.document import ExtractedField, VisualEvidence


def evidence_from_fields(fields: list[ExtractedField]) -> list[VisualEvidence]:
    out: list[VisualEvidence] = []
    for field in fields:
        if not field.value or field.value == "[okunamadı]":
            continue
        bbox = list(field.bbox)
        if len(bbox) != 4:
            continue
        area = abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1])
        if area < 0.0008 or area > 0.22:
            continue
        out.append(
            VisualEvidence(
                field_name=field.name,
                page=field.page,
                bbox=bbox,
                caption=f"{field.label}: {field.value}",
                confidence=field.confidence,
            )
        )
    return out
