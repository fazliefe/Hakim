from __future__ import annotations

import pytest
from pydantic import ValidationError

from hakim_legal_schema.enums import ProvenanceKind, RelationType
from hakim_legal_schema.relations import LegalRelation


def test_official_text_relation_has_full_confidence() -> None:
    rel = LegalRelation(
        from_id="law:5237",
        from_type="law",
        to_id="law:5237:article:158",
        to_type="article",
        relation_type=RelationType.HAS_ARTICLE,
        provenance=ProvenanceKind.OFFICIAL_TEXT,
        confidence=1.0,
    )
    assert rel.confidence == 1.0


def test_llm_extracted_relation_cannot_claim_full_confidence() -> None:
    with pytest.raises(ValidationError):
        LegalRelation(
            from_id="law:5237:article:158",
            from_type="article",
            to_id="decision:yargitay:2021:2019/1:2021/2",
            to_type="decision",
            relation_type=RelationType.INTERPRETED_BY,
            provenance=ProvenanceKind.LLM_EXTRACTED,
            confidence=1.0,
        )


def test_llm_extracted_relation_keeps_model_confidence() -> None:
    rel = LegalRelation(
        from_id="law:5237:article:158",
        from_type="article",
        to_id="decision:yargitay:2021:2019/1:2021/2",
        to_type="decision",
        relation_type=RelationType.INTERPRETED_BY,
        provenance=ProvenanceKind.LLM_EXTRACTED,
        confidence=0.89,
    )
    assert rel.confidence == 0.89
    assert rel.provenance != ProvenanceKind.OFFICIAL_TEXT
