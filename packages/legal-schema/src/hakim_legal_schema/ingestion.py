from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from hakim_legal_schema.enums import IngestionStatus

__all__ = ["IngestionReport", "IngestionStatus"]


class IngestionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    document_id: str
    status: IngestionStatus
    articles_found: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    content_changed: bool = False
    parser_version: str | None = None
    raw_snapshot_uri: str | None = None
