"""Build a DocumentBundle from already-analyzed documents. Additive; no VLM."""

from __future__ import annotations

import uuid

from document_ai.validation.conflict_detector import detect_conflicts
from hakim_legal_schema.bundle import BundleRelation, DocumentBundle
from hakim_legal_schema.document import StructuredDocument

_HINTS: dict[str, tuple[str, ...]] = {
    "tebligat": ("tebligat", "tebliğ evrak", "tebliğ mazbata"),
    "mahkeme_karari": ("mahkeme kararı", "gerekçeli karar", "kısa karar"),
    "vekaletname": ("vekaletname", "vekâletname"),
}

_TYPE_LABEL = {
    "tebligat": "tebligat",
    "mahkeme_karari": "mahkeme kararı",
    "vekaletname": "vekaletname",
}


def _blob(documents: list[StructuredDocument]) -> str:
    return "\n".join((doc.raw_text or "") for doc in documents).casefold()


def _missing_documents(documents: list[StructuredDocument]) -> list[str]:
    present = {doc.document_type for doc in documents}
    text = _blob(documents)
    missing: list[str] = []
    for dtype, words in _HINTS.items():
        if dtype in present:
            continue
        if any(word in text for word in words):
            missing.append(_TYPE_LABEL.get(dtype, dtype))
    return missing


def _relations(documents: list[StructuredDocument]) -> list[BundleRelation]:
    relations: list[BundleRelation] = []
    by_type: dict[str, list[StructuredDocument]] = {}
    for doc in documents:
        by_type.setdefault(doc.document_type, []).append(doc)
    for source in by_type.get("dilekce", []) + by_type.get("belirsiz", []):
        for target_type in ("tebligat", "mahkeme_karari"):
            for target in by_type.get(target_type, []):
                relations.append(
                    BundleRelation(
                        source=source.document_id,
                        target=target.document_id,
                        type="cites",
                    )
                )
    return relations


def analyze_bundle(documents: list[StructuredDocument]) -> DocumentBundle:
    return DocumentBundle(
        bundle_id=f"bundle-{uuid.uuid4().hex[:8]}",
        documents=documents,
        relations=_relations(documents),
        missing_documents=_missing_documents(documents),
        conflicts=detect_conflicts(documents),
    )
