from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hakim_legal_schema.enums import (
    AuthorityLevel,
    CalendarType,
    DocumentType,
    DurationUnit,
    ProvenanceKind,
)
from hakim_legal_schema.ids import article_id, article_version_id, law_id


class TemporalVersion(Protocol):
    valid_from: datetime
    valid_until: datetime | None

    def is_in_force_at(self, at: datetime) -> bool: ...


class Publication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    gazette_number: str | None = None
    gazette_page: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    official: bool
    retrieved_at: datetime
    content_hash: str
    authority: AuthorityLevel = AuthorityLevel.OFFICIAL
    url: str | None = None

    @model_validator(mode="after")
    def official_implies_official_authority(self) -> Source:
        if self.official and self.authority != AuthorityLevel.OFFICIAL:
            raise ValueError("official sources cannot have non-official authority")
        if not self.official and self.authority == AuthorityLevel.OFFICIAL:
            raise ValueError("non-official sources cannot claim official authority")
        return self


class LegalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: DocumentType
    title: str
    source: Source
    publication: Publication | None = None
    number: str | None = None


class Law(LegalDocument):
    type: DocumentType = DocumentType.LAW
    number: str
    publication: Publication

    @model_validator(mode="after")
    def id_matches_number(self) -> Law:
        expected = law_id(self.number)
        if self.id != expected:
            raise ValueError(f"law id must be {expected}")
        if self.type != DocumentType.LAW:
            raise ValueError("Law.type must be law")
        return self


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    law_id: str
    article_no: str

    @model_validator(mode="after")
    def id_matches_law_and_number(self) -> Article:
        number = self.law_id.removeprefix("law:")
        expected = article_id(number, self.article_no)
        if self.id != expected:
            raise ValueError(f"article id must be {expected}")
        return self


class ArticleVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    article_id: str
    law_id: str
    article_no: str
    text: str
    version: int = Field(ge=1)
    valid_from: datetime
    valid_until: datetime | None = None
    title: str | None = None
    document_version_id: str | None = None

    @model_validator(mode="after")
    def temporal_and_id_invariants(self) -> ArticleVersion:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        number = self.law_id.removeprefix("law:")
        expected = article_version_id(number, self.article_no, self.version)
        if self.id != expected:
            raise ValueError(f"article version id must be {expected}")
        expected_article = article_id(number, self.article_no)
        if self.article_id != expected_article:
            raise ValueError(f"article_id must be {expected_article}")
        return self

    def is_in_force_at(self, at: datetime) -> bool:
        if at < self.valid_from:
            return False
        if self.valid_until is None:
            return True
        return at < self.valid_until


class Paragraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    article_version_id: str
    paragraph_no: str
    text: str
    order_index: int = Field(ge=0)


class Court(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    slug: str
    name: str
    parent_id: str | None = None


class CourtDecision(LegalDocument):
    type: DocumentType = DocumentType.COURT_DECISION
    court_id: str
    year: int
    docket_no: str
    decision_no: str
    decision_date: date


class Institution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str | None = None


class LegalConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    domain: str | None = None


class Procedure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    domain: str | None = None


class Remedy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    procedure_id: str | None = None


class DeadlineRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    procedure: str
    trigger: str
    duration: int = Field(gt=0)
    unit: DurationUnit
    calendar_type: CalendarType
    legal_basis: list[str] = Field(min_length=1)
    provenance: ProvenanceKind = ProvenanceKind.OFFICIAL_TEXT


class DocumentVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    version: int = Field(ge=1)
    valid_from: datetime
    valid_until: datetime | None = None
    content_hash: str
    raw_snapshot_uri: str | None = None

    @model_validator(mode="after")
    def temporal_order(self) -> DocumentVersion:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class UserDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    owner_user_id: str
    filename: str
    content_type: str
    storage_uri: str
    sha256: str


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    title: str
    status: str = "open"
