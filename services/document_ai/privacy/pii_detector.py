"""Regex PII hints for sharing. Does not locate boxes on the page image."""

from __future__ import annotations

import re

from hakim_legal_schema.document import SensitiveRegion

_TCKN = re.compile(r"(?<!\d)([1-9]\d{10})(?!\d)")
_IBAN = re.compile(r"\bTR\s*\d{2}(?:\s*\d{4}){5}\s*\d{2}\b", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\d)(0?5\d{2})[\s./-]?(\d{3})[\s./-]?(\d{2})[\s./-]?(\d{2})(?!\d)")

_PII_LABEL = {
    "tckn": "[TCKN gizli]",
    "iban": "[IBAN gizli]",
    "email": "[e-posta gizli]",
    "phone": "[telefon gizli]",
}


def _tckn_ok(digits: str) -> bool:
    if len(digits) != 11 or digits[0] == "0" or len(set(digits)) == 1:
        return False
    nums = [int(ch) for ch in digits]
    odd = nums[0] + nums[2] + nums[4] + nums[6] + nums[8]
    even = nums[1] + nums[3] + nums[5] + nums[7]
    if nums[9] != (odd * 7 - even) % 10:
        return False
    return nums[10] == sum(nums[:10]) % 10


def _overlaps(start: int, end: int, taken: list[tuple[int, int]]) -> bool:
    return any(not (end <= left or start >= right) for left, right in taken)


def detect_pii(text: str, *, page: int = 1) -> list[SensitiveRegion]:
    blob = text or ""
    taken: list[tuple[int, int]] = []
    regions: list[SensitiveRegion] = []

    def add(kind: str, start: int, end: int, confidence: float) -> None:
        if _overlaps(start, end, taken):
            return
        taken.append((start, end))
        regions.append(
            SensitiveRegion(
                type=kind,
                page=page,
                bbox=[0.0, 0.0, 0.0, 0.0],
                confidence=confidence,
            )
        )

    for match in _TCKN.finditer(blob):
        if _tckn_ok(match.group(1)):
            add("tckn", match.start(), match.end(), 0.92)
    for match in _IBAN.finditer(blob):
        add("iban", match.start(), match.end(), 0.9)
    for match in _EMAIL.finditer(blob):
        add("email", match.start(), match.end(), 0.88)
    for match in _PHONE.finditer(blob):
        add("phone", match.start(), match.end(), 0.86)
    return regions


def redact_text(text: str) -> str:
    blob = text or ""
    replacements: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []

    def take(kind: str, start: int, end: int) -> None:
        if _overlaps(start, end, taken):
            return
        taken.append((start, end))
        replacements.append((start, end, _PII_LABEL[kind]))

    for match in _TCKN.finditer(blob):
        if _tckn_ok(match.group(1)):
            take("tckn", match.start(), match.end())
    for match in _IBAN.finditer(blob):
        take("iban", match.start(), match.end())
    for match in _EMAIL.finditer(blob):
        take("email", match.start(), match.end())
    for match in _PHONE.finditer(blob):
        take("phone", match.start(), match.end())
    out = blob
    for start, end, label in sorted(replacements, key=lambda item: item[0], reverse=True):
        out = out[:start] + label + out[end:]
    return out
