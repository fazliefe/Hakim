from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Classification:
    document_type: str
    legal_nature: str
    unit: str
    stage: str
    remedies: tuple[str, ...]
    # Kaç bağımsız kural-sinyalinin (bkz. `_confidence_from_hits`) tutarlı
    # sonuç verdiğinin ölçeklenmiş oranı — istatistiksel olarak KALİBRE
    # EDİLMİŞ bir olasılık DEĞİLDİR (etiketli bir eval seti yok, bkz.
    # eval/gold). "Kurallar ne kadar hemfikir" olarak okunmalı, "P(doğru
    # sınıflandırma)" olarak değil.
    confidence: float
    evidence_span: str
    label: str


# confidence, `hits` bağımsız sinyalin (bkz. classify_document) kaçının
# tuttuğuna göre bu aralığa doğrusal ölçeklenir. Alt sınır 0'a yakın ama
# sıfır değil (hiç sinyal tutmasa bile "belirsiz" etiketi zaten kendini
# açıklıyor); üst sınır 1'e yakın ama %100 iddia etmiyor — kural motoru
# yine de yanılabilir.
_CONFIDENCE_SIGNALS = 6
_CONFIDENCE_FLOOR = 0.15
_CONFIDENCE_CEILING = 0.95


def _confidence_from_hits(hits: int) -> float:
    span = _CONFIDENCE_CEILING - _CONFIDENCE_FLOOR
    return round(_CONFIDENCE_FLOOR + span * hits / _CONFIDENCE_SIGNALS, 2)


# Şartname (yargı) + Resmî Yazışma Usulleri / EBYS kamu evrakı.
# Sıra: eşit skorda daha özgül tür kazanır.
_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tebligat", ("tebliğ mazbatası", "tebligat kanunu", "7201 sayılı", "muhataba tebliğ")),
    ("olur", ("olura arz", "olur'a arz", "makamın oluruna", "olur'unuz", "olurunuz")),
    ("genelge", ("genelge", "genelgenin")),
    # Bare "tutanak" needle kaldırıldı — canlı bir istinaf kararında "duruşma
    # tutanaklarının yeterince irdelenmediği" gibi, belgenin KENDİSİNİ değil,
    # dosyadaki BAŞKA bir belgeyi anan bir cümlede geçtiği için yanlışlıkla
    # eşleşip (üstelik ilk 420 karakterlik "header" bonusunu da alıp) gerçek
    # "mahkeme_karari" eşleşmesini (karar verildi) puanla geçmişti.
    ("tutanak", ("tutanaktır", "işbu tutanak")),
    ("rapor", ("faaliyet raporu", "inceleme raporu", "işbu rapor", "raporudur")),
    ("cevap_yazisi", ("cevap yazısı", "yazınıza cevaben", "ilgi yazıya cevaben", "cevaben")),
    ("bilgi_yazisi", ("bilgi yazısı", "bilgilerine arz", "bilgi için")),
    ("ust_yazi", ("üst yazı", "havale olunur", "ek listesi", "dağıtım listesi")),
    ("iddianame", ("iddianame", "kamu davası açılmış", "kamu davası açılmıştır")),
    ("mahkeme_karari", ("gerekçeli karar", "mahkûmiyetine", "beraatine", "hükmün", "karar verildi")),
    # Bare "dilekçe" needle kaldırıldı — aynı sınıf hata (bkz. "tutanak" notu):
    # bir mahkeme kararı, "istinaf başvuru dilekçesinde özetle..." diyerek
    # TARAFIN dilekçesinden alıntı yapar; bu, KARARIN KENDİSİNİN bir dilekçe
    # olduğu anlamına gelmez. Canlı doğrulandı.
    ("dilekce", ("şikayetçidir", "müvekkilim adına", "arz olunur")),
]

KAMU_TYPES = frozenset(
    {"olur", "genelge", "tutanak", "rapor", "cevap_yazisi", "bilgi_yazisi", "ust_yazi"}
)

TYPE_LABELS: dict[str, str] = {
    "tebligat": "Tebligat",
    "iddianame": "İddianame",
    "mahkeme_karari": "Mahkeme kararı",
    "dilekce": "Dilekçe",
    "ust_yazi": "Üst yazı",
    "olur": "Olur",
    "genelge": "Genelge",
    "tutanak": "Tutanak",
    "rapor": "Rapor",
    "cevap_yazisi": "Cevap yazısı",
    "bilgi_yazisi": "Bilgi yazısı",
    "belirsiz": "Tür belirsiz",
}

_NATURE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("ceza", ("tck", "ceza mahkemesi", "ağır ceza", "asliye ceza", "savcılık", "sanık", "mahkûmiyet", "iddianame")),
    ("anayasa", ("bireysel başvuru", "anayasa mahkemesi", "aym")),
    ("idare", ("danıştay", "idare mahkemesi", "iptal davası", "2577")),
    (
        "hukuk",
        (
            "hmk",
            "hukuk muhakemeleri kanunu",
            "6100 sayılı",
            "hukuk mahkemesi",
            "asliye hukuk",
            "sulh hukuk",
            "hukuk dairesi",
            "tazminat davası",
            "maddi tazminat",
            "alacak davası",
            "boşanma davası",
            "kira tespiti",
            "tapu iptal",
            "aile mahkemesi",
            "iş mahkemesi",
            "ticaret mahkemesi",
            "tüketici mahkemesi",
            "davacı vekili",
            "davalı vekili",
        ),
    ),
    ("kamu", ("bakanlık", "valilik", "kaymakamlık", "genel müdürlük", "daire başkanlığı", "ebys")),
]

_STAGE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("bireysel_basvuru", ("bireysel başvuru",)),
    ("temyiz", ("temyiz",)),
    ("istinaf", ("istinaf",)),
    ("kovusturma", ("ağır ceza", "asliye ceza", "mahkûmiyet", "kovuşturma", "duruşma")),
    ("sorusturma", ("soruşturma", "savcılık", "iddianame")),
]

_TYPE_UNIT: dict[str, str] = {
    "iddianame": "Görevli ceza mahkemesi (kovuşturma)",
    "ust_yazi": "Evrak kayıt ve havale",
    "olur": "Makam / ilgili birim amiri",
    "genelge": "Tüm birimler (tebliğ)",
    "tutanak": "İlgili birim",
    "rapor": "Makam / ilgili birim",
    "cevap_yazisi": "Gelen yazının muhatabı / ilgili birim",
    "bilgi_yazisi": "Bilgi için ilgili birimler",
    "dilekce": "Evrak kayıt / ilgili birim",
}

_NATURE_UNIT: dict[str, str] = {
    "ceza": "İlgili Cumhuriyet savcılığı / ceza mahkemesi",
    "idare": "İlgili idare mahkemesi / Danıştay",
    "anayasa": "Anayasa Mahkemesi",
    "hukuk": "İlgili hukuk mahkemesi / Yargıtay hukuk dairesi",
    "kamu": "Evrak kayıt ve havale",
}


def _norm(text: str) -> str:
    folded = (
        text.replace("İ", "i")
        .replace("I", "i")
        .replace("ı", "i")
        .replace("Û", "u")
        .replace("û", "u")
    )
    return " ".join(folded.lower().split())


def _first_span(text: str, needles: tuple[str, ...]) -> str:
    lowered = text.lower()
    for needle in needles:
        idx = lowered.find(needle)
        if idx >= 0:
            start = max(0, idx - 24)
            end = min(len(text), idx + len(needle) + 48)
            return " ".join(text[start:end].split())
    return ""


def _best_label(blob: str, header: str, raw: str, rules: list[tuple[str, tuple[str, ...]]]) -> tuple[str, str, int]:
    winner = "belirsiz"
    span = ""
    best = 0
    for label, needles in rules:
        score = 0
        matched: list[str] = []
        for needle in needles:
            token = _norm(needle)
            if not token or token not in blob:
                continue
            score += 2
            if token in header:
                score += 3
            matched.append(needle)
        if score > best:
            best = score
            winner = label
            span = _first_span(raw, tuple(matched)) if matched else ""
    return winner, span, best


def classify_document(text: str) -> Classification:
    raw = text.strip()
    blob = _norm(raw)
    header = blob[:420]
    document_type, type_span, type_score = _best_label(blob, header, raw, _TYPE_RULES)
    legal_nature, _, nature_score = _best_label(blob, header, raw, _NATURE_RULES)
    if document_type == "belirsiz":
        from document_ai.extract import looks_like_resmi_yazi

        if looks_like_resmi_yazi(raw):
            document_type = "ust_yazi"
            type_span = type_span or "Sayı / Konu"
    if document_type in KAMU_TYPES and legal_nature == "belirsiz":
        legal_nature = "kamu"

    stage = "belirsiz"
    if document_type not in KAMU_TYPES:
        for label, needles in _STAGE_RULES:
            if any(_norm(n) in blob for n in needles):
                stage = label
                break
    if document_type == "iddianame" and stage in {"belirsiz", "istinaf", "temyiz"}:
        stage = "sorusturma"
    if document_type == "mahkeme_karari":
        if "yargıtay" in blob or "yargitay" in blob:
            stage = "temyiz"
        elif "istinaf mahkemesi" in blob or "bölge adliye" in blob or "bolge adliye" in blob:
            stage = "istinaf"
        else:
            stage = "kovusturma"

    # "istinaf"/"temyiz" nitelik-bazlı (ceza→CMK, hukuk→HMK) etiketlere
    # ayrıldı — aksi halde ikisi de aynı "istinaf"/"temyiz" etiketini
    # paylaşıp, deadline/catalog.py'de CMK kuralları hukuk davalarına da
    # (yanlışlıkla) uygulanıyordu — canlı bir BAM/istinaf tazminat kararıyla
    # doğrulandı.
    remedies: list[str] = []
    if legal_nature == "ceza" and document_type in {"mahkeme_karari", "tebligat"}:
        remedies.extend(["itiraz", "istinaf_ceza", "temyiz_ceza"])
    if legal_nature == "hukuk" and document_type in {"mahkeme_karari", "tebligat"}:
        remedies.extend(["istinaf_hukuk", "temyiz_hukuk"])
    if document_type not in KAMU_TYPES:
        if "istinaf" in blob:
            if legal_nature == "ceza":
                remedies.append("istinaf_ceza")
            elif legal_nature == "hukuk":
                remedies.append("istinaf_hukuk")
            elif legal_nature == "idare":
                remedies.append("istinaf_idari")
        if "temyiz" in blob:
            if legal_nature == "ceza":
                remedies.append("temyiz_ceza")
            elif legal_nature == "hukuk":
                remedies.append("temyiz_hukuk")
        if legal_nature == "anayasa":
            remedies.append("bireysel_basvuru")
        if legal_nature == "idare":
            # "istinaf_idari" hiçbir deadline kuralına bağlı değil (dead tag,
            # idari yargıda istinaf ayrı bir süre kuralı gerektirir — henüz
            # eklenmedi). "idari_dava" — route_islem.py/ACTION_TO_BELGE/
            # idari_dava.json'ın zaten kullandığı isim — İYUK m.7 dava açma
            # süresine bağlanıyor.
            remedies.append("istinaf_idari")
            remedies.append("idari_dava")
        # "şikayet" (TCK m.73, 6 aylık şikayet süresi) ceza-özgü bir
        # kurum — hukuk davalarında (tazminat vb.) kavram olarak yok.
        # Canlı doğrulandı: bir hukuk kararı, dosyada anılan paralel ceza
        # yargılaması nedeniyle "şikayetçi" kelimesini içeriyordu ve
        # yanlışlıkla TCK m.73 süresi almıştı.
        if legal_nature != "hukuk" and ("şikayet" in blob or "sikayet" in blob):
            remedies.append("sikayet")
    unique = tuple(dict.fromkeys(remedies))

    unit = _TYPE_UNIT.get(document_type) or _NATURE_UNIT.get(legal_nature, "Evrak kayıt / ilgili birim")
    if document_type in {"mahkeme_karari", "tebligat", "iddianame"} and (
        "yargıtay" in blob or "yargitay" in blob
    ):
        unit = "Yargıtay ilgili hukuk dairesi" if legal_nature == "hukuk" else "Yargıtay ilgili ceza dairesi"

    hits = sum(
        [
            document_type != "belirsiz",
            legal_nature != "belirsiz",
            stage != "belirsiz" or document_type in KAMU_TYPES,
            bool(unique) or document_type in KAMU_TYPES,
            type_score >= 5,
            nature_score >= 5 or document_type in KAMU_TYPES,
        ]
    )
    return Classification(
        document_type=document_type,
        legal_nature=legal_nature,
        unit=unit,
        stage=stage,
        remedies=unique,
        confidence=_confidence_from_hits(hits),
        evidence_span=type_span or raw[:180],
        label=TYPE_LABELS.get(document_type, document_type),
    )
