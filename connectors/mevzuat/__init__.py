"""mevzuat.gov.tr connector — discover / fetch_metadata / fetch_content + HTML parser."""

from mevzuat.client import MevzuatClient, MevzuatHit, RawSnapshot
from mevzuat.parser import ParsedArticle, ParsedLaw, parse_mevzuat_html

__all__ = [
    "MevzuatClient",
    "MevzuatHit",
    "ParsedArticle",
    "ParsedLaw",
    "RawSnapshot",
    "parse_mevzuat_html",
]
