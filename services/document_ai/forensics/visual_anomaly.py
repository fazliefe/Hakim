"""Quality-only visual notes. Never claims a document is fake or authentic."""

from __future__ import annotations

from hakim_legal_schema.document import QualityStatus, StructuredDocument, StructuredWarning, SuspiciousRegion


def anomaly_notes(doc: StructuredDocument) -> tuple[list[StructuredWarning], list[SuspiciousRegion]]:
    issues = list(doc.quality.issues)
    for page in doc.pages:
        if page.quality:
            issues.extend(page.quality.issues)
    high = [item for item in issues if item.severity == "high"]
    if not high and doc.quality.status == QualityStatus.GOOD:
        return [], []
    warnings = [
        StructuredWarning(
            code="visual_quality_not_authenticity",
            message="Görüntü kalitesi zayıf (bulanıklık, ışık veya çözünürlük). Bu, belgenin sahte olduğu anlamına gelmez.",
            severity="info",
        )
    ]
    regions: list[SuspiciousRegion] = []
    for item in high:
        if item.bbox and len(item.bbox) == 4:
            regions.append(
                SuspiciousRegion(
                    type="quality",
                    page=item.page,
                    bbox=list(item.bbox),
                    reason=item.message,
                    confidence=0.4,
                )
            )
    return warnings, regions
