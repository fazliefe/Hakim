from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    LAW = "law"
    DECREE_LAW = "decree_law"
    PRESIDENTIAL_DECREE = "presidential_decree"
    PRESIDENTIAL_DECISION = "presidential_decision"
    PRESIDENTIAL_REGULATION = "presidential_regulation"
    REGULATION = "regulation"
    BYLAW = "bylaw"
    CIRCULAR = "circular"
    COMMUNIQUE = "communique"
    COURT_DECISION = "court_decision"
    OTHER = "other"


class AuthorityLevel(StrEnum):
    OFFICIAL = "official"
    SECONDARY = "secondary"
    USER = "user"


class ProvenanceKind(StrEnum):
    OFFICIAL_TEXT = "official_text"
    LLM_EXTRACTED = "llm_extracted"
    HUMAN_ANNOTATED = "human_annotated"
    INFERRED = "inferred"


class RelationType(StrEnum):
    HAS_ARTICLE = "HAS_ARTICLE"
    HAS_PARAGRAPH = "HAS_PARAGRAPH"
    REFERENCES = "REFERENCES"
    AMENDED_BY = "AMENDED_BY"
    REPEALED_BY = "REPEALED_BY"
    INTERPRETED_BY = "INTERPRETED_BY"
    CITES = "CITES"
    ISSUED_BY = "ISSUED_BY"
    DISCUSSES = "DISCUSSES"
    BASED_ON = "BASED_ON"
    HAS_REMEDY = "HAS_REMEDY"
    HAS_DEADLINE = "HAS_DEADLINE"


class DurationUnit(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class CalendarType(StrEnum):
    CIVIL = "civil"
    ADMINISTRATIVE = "administrative"
    CRIMINAL = "criminal"


class IngestionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class MevzuatTur(StrEnum):
    """mevzuat.gov.tr MevzuatTur codes used by the official search API."""

    KANUN = "1"
    KHK = "2"
    YONETMELIK = "3"
    TUZUK = "4"
    TEBLIG = "9"
    CB_KARARNAMESI = "19"
    CB_KARARI = "20"
    CB_YONETMELIGI = "21"


MEVZUAT_TUR_TO_DOCUMENT_TYPE: dict[MevzuatTur, DocumentType] = {
    MevzuatTur.KANUN: DocumentType.LAW,
    MevzuatTur.KHK: DocumentType.DECREE_LAW,
    MevzuatTur.YONETMELIK: DocumentType.REGULATION,
    MevzuatTur.TUZUK: DocumentType.BYLAW,
    MevzuatTur.TEBLIG: DocumentType.COMMUNIQUE,
    MevzuatTur.CB_KARARNAMESI: DocumentType.PRESIDENTIAL_DECREE,
    MevzuatTur.CB_KARARI: DocumentType.PRESIDENTIAL_DECISION,
    MevzuatTur.CB_YONETMELIGI: DocumentType.PRESIDENTIAL_REGULATION,
}
