from __future__ import annotations

import re
from dataclasses import dataclass

from hakim_legal_schema.enums import ProvenanceKind, RelationType
from hakim_legal_schema.ids import article_id
from hakim_legal_schema.relations import LegalRelation

# Turkish ordinal / article citation patterns inside statute text.
ARTICLE_REF_PATTERNS = [
    # "Madde 158" / "madde 13"
    re.compile(r"\b[Mm]adde\s+([0-9]+(?:/[A-Z])?)\b"),
    # "13 üncü madde" / "5 inci maddesi" / "12 nci maddelerde"
    re.compile(
        r"\b([0-9]+(?:/[A-Z])?)\s*(?:inci|ıncı|uncu|üncü|nci|ncı)\s+madd",
        re.IGNORECASE,
    ),
    # "11 ve 12 nci maddelerde"
    re.compile(
        r"\b([0-9]+(?:/[A-Z])?)\s+ve\s+([0-9]+(?:/[A-Z])?)\s*(?:inci|ıncı|uncu|üncü|nci|ncı)?\s+madd",
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True, slots=True)
class ExtractedCitation:
    from_article_no: str
    to_article_no: str
    span: str


def extract_article_citations(text: str, *, from_article_no: str) -> list[ExtractedCitation]:
    """Extract intra-law article references from official text."""
    found: list[ExtractedCitation] = []
    seen: set[str] = set()
    for pattern in ARTICLE_REF_PATTERNS:
        for match in pattern.finditer(text):
            numbers = [g for g in match.groups() if g]
            for num in numbers:
                if num == from_article_no:
                    continue
                key = f"{from_article_no}->{num}"
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    ExtractedCitation(
                        from_article_no=from_article_no,
                        to_article_no=num,
                        span=match.group(0),
                    )
                )
    return found


def citations_to_relations(
    citations: list[ExtractedCitation],
    *,
    law_number: str,
) -> list[LegalRelation]:
    relations: list[LegalRelation] = []
    for cite in citations:
        relations.append(
            LegalRelation(
                from_id=article_id(law_number, cite.from_article_no),
                from_type="article",
                to_id=article_id(law_number, cite.to_article_no),
                to_type="article",
                relation_type=RelationType.REFERENCES,
                provenance=ProvenanceKind.OFFICIAL_TEXT,
                confidence=1.0,
            )
        )
    return relations
