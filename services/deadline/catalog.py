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
        "nature": "ceza",
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
        "nature": "ceza",
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
        # "istinaf_ceza" — hukuk davaları için ayrı "istinaf_hukuk"/HMK m.345
        # kuralı eklendiğinde (bkz. aşağı), aynı bare "istinaf" etiketi
        # paylaşılırsa hukuk davalarına da bu CMK kuralı uygulanıyordu (canlı
        # bir BAM/istinaf tazminat kararıyla doğrulandı) — nitelik-bazlı ayrıldı.
        "remedy": "istinaf_ceza",
        "nature": "ceza",
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
        "remedy": "temyiz_ceza",
        "nature": "ceza",
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
        "nature": "anayasa",
        "trigger": "teblig",
        "duration": 30,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CIVIL,
        "legal_basis": ("law:6216:article:47",),
        "legal_basis_label": "6216 s.K. m.47",
    },
    {
        "id": "deadline:istinaf_hukuk:hmk345",
        "name": "İstinaf (hukuk)",
        "procedure": "hukuk_ilk_derece",
        "remedy": "istinaf_hukuk",
        "nature": "hukuk",
        "trigger": "teblig",
        # HMK m.345/1: "İstinaf yoluna başvuru süresi, ilamın... tebliğiyle
        # işlemeye başlar... aksine kanun hükmü bulunmadıkça iki haftadır."
        # 6100 sayılı Kanun artık arşivde (bkz. scripts/ingest_law.py
        # --mevzuat-no 6100 + scripts/index_legal_chunks.py) — canonical id
        # kullanılabilir; "İlgili kaynak" retrieval'i (step_mevzuat) artık
        # gerçek HMK madde metnini bulup gösterebiliyor.
        # CalendarType.CIVIL kullanıldı (AYM m.47 kuralıyla aynı grup); HMK
        # m.93 (resmi tatil erteleme) ve m.102/104 (adli tatil + 7 gün uzama)
        # CIVIL takvimi için deadline/engine.py::compute_last_day() içinde
        # genelleştirildi — bkz. o dosyanın başındaki not.
        "duration": 14,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CIVIL,
        "legal_basis": ("law:6100:article:345",),
        "legal_basis_label": "HMK m.345",
    },
    {
        "id": "deadline:temyiz_hukuk:hmk361",
        "name": "Temyiz (hukuk)",
        "procedure": "hukuk_istinaf",
        "remedy": "temyiz_hukuk",
        "nature": "hukuk",
        "trigger": "teblig",
        # HMK m.361/1: "Temyiz süresi, ilamın... tebliğiyle işlemeye başlar ve
        # iki haftadır."
        "duration": 14,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.CIVIL,
        "legal_basis": ("law:6100:article:361",),
        "legal_basis_label": "HMK m.361",
    },
    {
        "id": "deadline:idari_dava:iyuk7",
        "name": "İdari dava açma süresi",
        "procedure": "idari_dava",
        "remedy": "idari_dava",
        "nature": "idare",
        "trigger": "teblig",
        # İYUK m.7/1: "...Danıştayda ve idare mahkemelerinde altmış... gündür."
        # (vergi mahkemesinde otuz gün — ayrı, daha dar bir durum; genel kural
        # burada uygulanıyor). İYUK m.8/2 (resmi tatil erteleme) ve m.8/3 +
        # m.61 (çalışmaya ara verme: 20 Temmuz-31 Ağustos + 7 gün uzama)
        # ADMINISTRATIVE takvimi için deadline/engine.py::compute_last_day()
        # içinde genelleştirildi — önceki sürümdeki "ceza takviminin hafta
        # sonu erteleme kuralı burada yok" notu YANLIŞTI, düzeltildi.
        "duration": 60,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.ADMINISTRATIVE,
        "legal_basis": ("law:2577:article:7",),
        "legal_basis_label": "İYUK m.7",
    },
    {
        "id": "deadline:istinaf_idari:iyuk45",
        "name": "İdari istinaf",
        "procedure": "idari_istinaf",
        "remedy": "istinaf_idari",
        "nature": "idare",
        "trigger": "teblig",
        "duration": 30,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.ADMINISTRATIVE,
        "legal_basis": ("law:2577:article:45",),
        "legal_basis_label": "İYUK m.45",
    },
    {
        "id": "deadline:temyiz_idari:iyuk46",
        "name": "İdari temyiz",
        "procedure": "idari_temyiz",
        "remedy": "temyiz_idari",
        "nature": "idare",
        "trigger": "teblig",
        "duration": 30,
        "unit": DurationUnit.DAY,
        "calendar": CalendarType.ADMINISTRATIVE,
        "legal_basis": ("law:2577:article:46",),
        "legal_basis_label": "İYUK m.46",
    },
]
