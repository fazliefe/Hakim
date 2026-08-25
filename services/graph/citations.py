from __future__ import annotations

import re
from dataclasses import dataclass

from hakim_legal_schema.enums import ProvenanceKind, RelationType
from hakim_legal_schema.ids import article_id
from hakim_legal_schema.relations import LegalRelation

from retrieval.bm25 import LAW_HINTS

# "5237 sayılı Kanunun/Kanunu/Kanunda ... maddesi" gibi kısaltmasız atıflar.
LAW_NUMBER_CONTEXT_RE = re.compile(
    r"\b(5237|5271|2577|6216)\s*(?:say[ıi]l[ıi])?\s*[Kk]anun\w*"
)

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


def _normalize_for_law_hint(text: str) -> str:
    return text.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()


def _laws_in_window(window: str) -> set[str]:
    """Bir bağlam penceresinde (madde referansının etrafındaki metin) hangi
    kanun(lar)ın kısaltması veya numarası geçiyor, tespit eder."""
    found: set[str] = set()
    normalized = _normalize_for_law_hint(window)
    for abbr, law_no in LAW_HINTS.items():
        if re.search(rf"\b{re.escape(_normalize_for_law_hint(abbr))}\b", normalized):
            found.add(law_no)
    for match in LAW_NUMBER_CONTEXT_RE.finditer(window):
        found.add(match.group(1))
    return found


@dataclass(frozen=True, slots=True)
class ExtractedLawCitation:
    from_article_no: str
    to_article_no: str
    law_no: str
    span: str


def extract_law_article_citations(
    text: str, *, from_article_no: str, window: int = 60
) -> list[ExtractedLawCitation]:
    """Çok-kanunlu metinlerde (örn. mahkeme kararları) madde referanslarını
    yakın bağlamdaki kanun kısaltmasıyla (TCK/CMK/İYUK, "5237 sayılı Kanun"
    vb.) eşleştirip doğru kanuna atfeder. Bağlamda kanun hiç bulunamazsa ya da
    birden fazla farklı kanun aynı anda geçiyorsa (belirsiz) hiç kayıt
    üretmez — yanlış kanuna eşlemek, hiç eşlememekten kötüdür."""
    found: list[ExtractedLawCitation] = []
    seen: set[str] = set()
    for pattern in ARTICLE_REF_PATTERNS:
        for match in pattern.finditer(text):
            numbers = [g for g in match.groups() if g]
            if not numbers:
                continue
            window_text = text[max(0, match.start() - window) : match.end() + window]
            laws = _laws_in_window(window_text)
            if len(laws) != 1:
                continue
            (law_no,) = laws
            for num in numbers:
                if num == from_article_no:
                    continue
                key = f"{law_no}:{from_article_no}->{num}"
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    ExtractedLawCitation(
                        from_article_no=from_article_no,
                        to_article_no=num,
                        law_no=law_no,
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
