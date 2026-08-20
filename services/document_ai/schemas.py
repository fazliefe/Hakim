from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TypeSchema:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()


# Resmî Yazışma Usulleri alanları + şartname yargı evrakı.
# Değerler extract.py anahtarlarıyla aynıdır.
TYPE_SCHEMAS: dict[str, TypeSchema] = {
    "ust_yazi": TypeSchema(("sayi", "konu"), ("ilgi", "kurum", "tarih", "ek", "dagitim")),
    "olur": TypeSchema(("konu",), ("sayi", "kurum", "tarih")),
    "genelge": TypeSchema(("sayi",), ("konu", "kurum", "tarih")),
    "tutanak": TypeSchema(("tarih",), ("kurum", "konu")),
    "rapor": TypeSchema(("konu",), ("sayi", "kurum", "tarih")),
    "cevap_yazisi": TypeSchema(("ilgi",), ("sayi", "konu", "kurum", "tarih")),
    "bilgi_yazisi": TypeSchema(("konu",), ("sayi", "kurum", "tarih")),
    "dilekce": TypeSchema(("muhatap",), ("konu", "tarih")),
    "tebligat": TypeSchema(("teblig",), ("muhatap", "tarih")),
    "iddianame": TypeSchema(("kurum",), ("sayi", "konu", "tarih")),
    "mahkeme_karari": TypeSchema(("karar",), ("teblig", "kurum")),
    "belirsiz": TypeSchema((), ("sayi", "konu", "tarih")),
}

FIELD_LABELS: dict[str, str] = {
    "sayi": "Sayı",
    "konu": "Konu",
    "ilgi": "İlgi",
    "kurum": "Kurum",
    "muhatap": "Muhatap",
    "tarih": "Tarih",
    "teblig": "Tebliğ tarihi",
    "karar": "Karar tarihi",
    "ek": "Ek",
    "dagitim": "Dağıtım",
}


def required_fields(document_type: str) -> tuple[str, ...]:
    spec = TYPE_SCHEMAS.get(document_type) or TYPE_SCHEMAS["belirsiz"]
    return spec.required
