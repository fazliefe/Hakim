from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hakim_legal_schema.enums import ProvenanceKind, RelationType


class LegalRelation(BaseModel):
    """A typed edge between legal entities. Official and LLM edges are not equal."""

    model_config = ConfigDict(extra="forbid")

    from_id: str
    from_type: str
    to_id: str
    to_type: str
    relation_type: RelationType
    provenance: ProvenanceKind
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def provenance_confidence_contract(self) -> LegalRelation:
        if self.provenance == ProvenanceKind.OFFICIAL_TEXT and self.confidence != 1.0:
            raise ValueError("official_text relations must have confidence 1.0")
        if self.provenance == ProvenanceKind.LLM_EXTRACTED and self.confidence >= 1.0:
            raise ValueError("llm_extracted relations cannot claim full confidence")
        return self
