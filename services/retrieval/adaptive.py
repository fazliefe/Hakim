from __future__ import annotations

import re

from retrieval.bm25 import SearchHit, parse_law_hint
from retrieval.hybrid import _is_exact_citation_query

_OFF_TOPIC = (
    "fenerbahce",
    "galatasaray",
    "besiktas",
    "hava durumu",
    "hava tahmini",
    "mac sonucu",
    "mac olur",
)

_LEGAL_MARK = (
    "suc",
    "ceza",
    "madde",
    "tck",
    "cmk",
    "kanun",
    "hakaret",
    "dolandir",
    "hirsiz",
    "teblig",
    "dava",
    "savci",
    "mahkeme",
    "istinaf",
    "temyiz",
)

_FOLD = str.maketrans("çğıöşüâÇĞİÖŞÜIı", "cgiosuaCGIOSUIi")


def _fold(text: str) -> str:
    return (text or "").translate(_FOLD).lower()


def _tokens(query: str, *, min_len: int = 4) -> list[str]:
    return [tok for tok in re.findall(r"\w+", _fold(query), flags=re.UNICODE) if len(tok) >= min_len]


def query_is_off_topic(query: str) -> bool:
    blob = _fold(query)
    if _is_exact_citation_query(query) or parse_law_hint(query):
        return False
    if any(mark in blob for mark in _LEGAL_MARK):
        return False
    if re.search(r"\bmac(?:i|u)?\b", blob) and "mahkeme" not in blob:
        return True
    return any(mark in blob for mark in _OFF_TOPIC)


def bm25_is_enough(query: str, hits: list[SearchHit]) -> bool:
    if _is_exact_citation_query(query):
        return True
    if not hits:
        return False
    tokens = _tokens(query)
    if len(tokens) >= 5:
        return False
    top = hits[0]
    blob = _fold(f"{top.title or ''} {top.content or ''} {top.article_no or ''}")
    if not tokens:
        return False
    return any(tok in blob for tok in tokens[:3])
