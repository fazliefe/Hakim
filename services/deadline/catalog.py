from __future__ import annotations

from deadline.engine import CalendarType, DurationUnit

# legal_basis uses canonical ids when the article is in the archive,
# otherwise a human-readable official citation until that law is ingested.
DEFAULT_RULES: list[dict[str, object]] = [
    {
        "id": "deadline:sikayet:tck73",
        "name": "Şikayet süresi",
        "procedure": "ceza_sorusturma",
        "remedy": "sikayet",
        "trigger": "teblig",
        "duration": 6,
        "unit": DurationUnit.MONTH,
        "calendar": CalendarType.CRIMINAL,
        "legal_basis": ("law:5237:article:73",),
        "legal_basis_label": "TCK m.73",
    },
    {
        "id": "deadline:itiraz:cmk268",
        "name": "İtiraz",
        "procedure": "ceza_kovusturma",
        "remedy": "itiraz",
        "trigger": "teblig",
        # CMK m.268/1: "...kararı öğrendiği günden itibaren iki hafta içinde..."
        # — 7 gün değil, 14 gün.
        "duration": 14,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CRIMINAL,
        "legal_basis": ("law:5271:article:268",),
        "legal_basis_label": "CMK m.268",
    },
    {
        "id": "deadline:istinaf:cmk273",
        "name": "İstinaf",
        "procedure": "ceza_kovusturma",
        "remedy": "istinaf",
        "trigger": "teblig",
        # CMK m.273/1: "...tebliğ edildiği tarihten itibaren iki hafta içinde..."
        # — 7 gün değil, 14 gün. (Yazım modülünün ürettiği taslak metni zaten
        # doğru şekilde "iki hafta" diyordu; süre motoru bununla çelişiyordu.)
        "duration": 14,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CRIMINAL,
        "legal_basis": ("law:5271:article:273",),
        "legal_basis_label": "CMK m.273",
    },
    {
        "id": "deadline:temyiz:cmk291",
        "name": "Temyiz",
        "procedure": "ceza_istinaf",
        "remedy": "temyiz",
        "trigger": "teblig",
        # CMK m.291/1: "...tebliğ edildiği tarihten itibaren iki hafta içinde..."
        # — 15 gün değil, 14 gün.
        "duration": 14,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CRIMINAL,
        "legal_basis": ("law:5271:article:291",),
        "legal_basis_label": "CMK m.291",
    },
    {
        "id": "deadline:aym:30gun",
        "name": "Bireysel başvuru",
        "procedure": "anayasa_bireysel",
        "remedy": "bireysel_basvuru",
        "trigger": "teblig",
        "duration": 30,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CIVIL,
        "legal_basis": ("law:6216:article:47",),
        "legal_basis_label": "6216 s.K. m.47",
    },
    {
        "id": "deadline:idari_dava:iyuk7",
        "name": "İdari dava açma süresi",
        "procedure": "idare_dava",
        "remedy": "idari_dava",
        "trigger": "teblig",
        # İYUK m.7/1: "...Danıştayda ve idare mahkemelerinde altmış... gündür."
        # (vergi mahkemesinde otuz gün — ayrı, daha dar bir durum; genel kural
        # burada uygulanıyor). Süreler idari takvimde hesaplanır, ceza
        # takviminin hafta sonu erteleme kuralı burada yok.
        "duration": 60,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.ADMINISTRATIVE,
        "legal_basis": ("law:2577:article:7",),
        "legal_basis_label": "İYUK m.7",
    },
]
