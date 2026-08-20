from __future__ import annotations

from dataclasses import dataclass


class CanonicalIdError(ValueError):
    """Raised when a canonical legal identifier is malformed."""


@dataclass(frozen=True, slots=True)
class ParsedCanonicalId:
    kind: str
    raw: str
    law_number: str | None = None
    article_no: str | None = None
    version: int | None = None
    court: str | None = None
    year: int | None = None
    docket_no: str | None = None
    decision_no: str | None = None
    slug: str | None = None


def _require_token(value: str, name: str) -> str:
    token = value.strip()
    if not token:
        raise CanonicalIdError(f"{name} must not be empty")
    return token


def law_id(number: str) -> str:
    return f"law:{_require_token(number, 'law number')}"


def article_id(law_number: str, article_no: str) -> str:
    return f"{law_id(law_number)}:article:{_require_token(article_no, 'article_no')}"


def article_version_id(law_number: str, article_no: str, version: int) -> str:
    if version < 1:
        raise CanonicalIdError("version must be >= 1")
    return f"{article_id(law_number, article_no)}:v{version}"


def court_id(slug: str) -> str:
    return f"court:{_require_token(slug, 'court slug')}"


def decision_id(*, court: str, year: int, docket: str, decision_no: str) -> str:
    if year < 1000:
        raise CanonicalIdError("decision year is invalid")
    return (
        f"decision:{_require_token(court, 'court')}:"
        f"{year}:{_require_token(docket, 'docket')}:"
        f"{_require_token(decision_no, 'decision_no')}"
    )


def parse_canonical_id(value: str) -> ParsedCanonicalId:
    raw = (value or "").strip()
    if not raw or ":" not in raw:
        raise CanonicalIdError(f"invalid canonical id: {value!r}")

    if raw.startswith("law:"):
        rest = raw[len("law:") :]
        if not rest or rest.endswith(":") or rest.startswith(":"):
            raise CanonicalIdError(f"invalid canonical id: {value!r}")
        if ":article:" in rest:
            law_number, article_part = rest.split(":article:", 1)
            if not law_number or not article_part:
                raise CanonicalIdError(f"invalid canonical id: {value!r}")
            if ":v" in article_part:
                article_no, version_token = article_part.rsplit(":v", 1)
                if not article_no or not version_token.isdigit():
                    raise CanonicalIdError(f"invalid canonical id: {value!r}")
                return ParsedCanonicalId(
                    kind="article_version",
                    raw=raw,
                    law_number=law_number,
                    article_no=article_no,
                    version=int(version_token),
                )
            return ParsedCanonicalId(
                kind="article",
                raw=raw,
                law_number=law_number,
                article_no=article_part,
            )
        if ":" in rest:
            raise CanonicalIdError(f"invalid canonical id: {value!r}")
        return ParsedCanonicalId(kind="law", raw=raw, law_number=rest)

    if raw.startswith("court:"):
        slug = raw[len("court:") :]
        if not slug or ":" in slug:
            raise CanonicalIdError(f"invalid canonical id: {value!r}")
        return ParsedCanonicalId(kind="court", raw=raw, slug=slug, court=slug)

    if raw.startswith("decision:"):
        parts = raw.split(":")
        if len(parts) != 5:
            raise CanonicalIdError(f"invalid canonical id: {value!r}")
        _, court, year_token, docket_no, decision_no = parts
        if not year_token.isdigit():
            raise CanonicalIdError(f"invalid canonical id: {value!r}")
        return ParsedCanonicalId(
            kind="decision",
            raw=raw,
            court=court,
            year=int(year_token),
            docket_no=docket_no,
            decision_no=decision_no,
        )

    raise CanonicalIdError(f"invalid canonical id: {value!r}")
