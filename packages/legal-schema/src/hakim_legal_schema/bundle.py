from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hakim_legal_schema.document import StructuredDocument


class BundleRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    type: str


class FieldConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cross_document_conflict"] = "cross_document_conflict"
    field: str
    values: list[dict[str, str]] = Field(default_factory=list)


class DocumentBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    documents: list[StructuredDocument] = Field(default_factory=list)
    relations: list[BundleRelation] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    conflicts: list[FieldConflict] = Field(default_factory=list)
