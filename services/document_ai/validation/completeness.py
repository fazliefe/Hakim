from __future__ import annotations

from hakim_legal_schema.document import FIELD_LABELS, StructuredDocument, StructuredWarning

from document_ai.validation.document_rules import rules_for


def completeness_warnings(doc: StructuredDocument) -> list[StructuredWarning]:
    spec = rules_for(doc.document_type)
    required = list(spec.get("required") or [])
    present = {field.name for field in doc.fields if field.value and field.value != "[okunamadı]"}
    warnings: list[StructuredWarning] = []
    for name in required:
        if name not in present:
            label = FIELD_LABELS.get(name, name)
            warnings.append(
                StructuredWarning(
                    code="missing_field",
                    message=f"✗ {label} alanı bekleniyor ama okunamadı.",
                    field=name,
                )
            )
    return warnings
