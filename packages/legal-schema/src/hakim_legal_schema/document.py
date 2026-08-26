from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

KNOWN_FIELDS: tuple[str, ...] = (
    "date",
    "document_no",
    "case_no",
    "decision_no",
    "notification_date",
    "sender",
    "recipient",
    "person_name",
    "institution",
    "subject",
    "signature",
    "stamp",
    "page_number",
    "attachment_section",
    "distribution_section",
    "reference_section",
)

FIELD_LABELS: dict[str, str] = {
    "date": "Tarih",
    "document_no": "Sayı",
    "case_no": "Dosya No",
    "decision_no": "Karar No",
    "notification_date": "Tebliğ Tarihi",
    "sender": "Gönderen",
    "recipient": "Muhatap",
    "person_name": "Ad Soyad",
    "institution": "Kurum",
    "subject": "Konu",
    "signature": "İmza",
    "stamp": "Mühür / Kaşe",
    "page_number": "Sayfa No",
    "attachment_section": "Ekler",
    "distribution_section": "Dağıtım",
    "reference_section": "İlgi",
}

ConfidenceBand = Literal["trusted", "review", "uncertain"]


class QualityStatus(StrEnum):
    GOOD = "good"
    WARNING = "warning"
    UNUSABLE = "unusable"


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["low", "medium", "high"] = "medium"
    page: int = 1
    message: str = ""
    bbox: list[float] | None = None


class QualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quality_score: float = Field(ge=0, le=1, default=1.0)
    status: QualityStatus = QualityStatus.GOOD
    issues: list[QualityIssue] = Field(default_factory=list)


class BBox(BaseModel):
    """Normalized page box: [x0, y0, x1, y1] in 0–1."""

    model_config = ConfigDict(extra="forbid")

    x0: float
    y0: float
    x1: float
    y1: float

    @classmethod
    def from_list(cls, values: list[float] | tuple[float, ...]) -> "BBox":
        if len(values) != 4:
            raise ValueError("bbox dört sayı olmalı: [x0, y0, x1, y1]")
        nums = [_clamp01(float(v)) for v in values]
        x0, y0, x1, y1 = nums
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        return cls(x0=x0, y0=y0, x1=x1, y1=y1)

    def as_list(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str = ""
    value: str
    normalized_value: str | None = None
    page: int = Field(ge=1, default=1)
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    confidence: float = Field(ge=0, le=1, default=0.0)
    source: str = "vlm"
    band: ConfidenceBand = "uncertain"

    @field_validator("bbox")
    @classmethod
    def _bbox_ok(cls, value: list[float]) -> list[float]:
        return BBox.from_list(value).as_list()

    @model_validator(mode="after")
    def _label_default(self) -> "ExtractedField":
        if not self.label:
            self.label = FIELD_LABELS.get(self.name, self.name)
        return self


class DocumentSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    text: str = ""
    page: int = Field(ge=1, default=1)
    bbox: list[float] | None = None


class DocumentPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    width: int | None = None
    height: int | None = None
    text: str = ""
    quality: QualityReport | None = None
    preview_jpeg: str | None = None


class VisualEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    page: int = Field(ge=1, default=1)
    bbox: list[float]
    caption: str = ""
    confidence: float = Field(ge=0, le=1, default=0.0)


class SensitiveRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    page: int = Field(ge=1, default=1)
    bbox: list[float]
    confidence: float = Field(ge=0, le=1, default=0.0)


class SuspiciousRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "visual_anomaly"
    page: int = Field(ge=1, default=1)
    bbox: list[float]
    reason: str = ""
    confidence: float = Field(ge=0, le=1, default=0.0)


class StructuredWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"
    field: str | None = None
    page: int | None = None


class StructuredDocument(BaseModel):
    """VLM ve kural motorlarının ortak evrak modeli. Hukuki hüküm içermez."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_type: str = "belirsiz"
    document_type_confidence: float = Field(ge=0, le=1, default=0.0)
    filename: str = ""
    pages: list[DocumentPage] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)
    sections: list[DocumentSection] = Field(default_factory=list)
    quality: QualityReport = Field(default_factory=QualityReport)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    visual_evidence: list[VisualEvidence] = Field(default_factory=list)
    sensitive_regions: list[SensitiveRegion] = Field(default_factory=list)
    suspicious_regions: list[SuspiciousRegion] = Field(default_factory=list)
    warnings: list[StructuredWarning] = Field(default_factory=list)
    raw_text: str = ""
