from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Classification:
    document_type: str
    legal_nature: str
    unit: str
    stage: str
    remedies: tuple[str, ...]
    confidence: float
    evidence_span: str
    label: str


# Şartname (yargı) + Resmî Yazışma Usulleri / EBYS kamu evrakı.
# Sıra: eşit skorda daha özgül tür kazanır.
_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tebligat", ("tebliğ mazbatası", "tebligat kanunu", "7201 sayılı", "muhataba tebliğ")),
    ("olur", ("olura arz", "olur'a arz", "makamın oluruna", "olur'unuz", "olurunuz")),
    ("genelge", ("genelge", "genelgenin")),
    ("tutanak", ("tutanaktır", "işbu tutanak", "tutanak")),
    ("rapor", ("faaliyet raporu", "inceleme raporu", "işbu rapor", "raporudur")),
    ("cevap_yazisi", ("cevap yazısı", "yazınıza cevaben", "ilgi yazıya cevaben", "cevaben")),
    ("bilgi_yazisi", ("bilgi yazısı", "bilgilerine arz", "bilgi için")),
    ("ust_yazi", ("üst yazı", "havale olunur", "ek listesi", "dağıtım listesi")),
    ("iddianame", ("iddianame", "kamu davası açılmış", "kamu davası açılmıştır")),
    ("mahkeme_karari", ("gerekçeli karar", "mahkûmiyetine", "beraatine", "hükmün", "karar verildi")),
    ("dilekce", ("dilekçe", "şikayetçidir", "müvekkilim adına", "arz olunur")),
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
    return _finalize(
        raw,
        blob,
        document_type,
        legal_nature,
        type_span=type_span,
        type_score=type_score,
        nature_score=nature_score,
    )


# Kural motoru belirsiz/düşük güvenli kaldığında LLM'in seçebileceği kapalı liste.
_NATURE_CHOICES = ("ceza", "idare", "anayasa", "kamu", "belirsiz")


def _finalize(
    raw: str,
    blob: str,
    document_type: str,
    legal_nature: str,
    *,
    type_span: str = "",
    type_score: int = 0,
    nature_score: int = 0,
    confidence_override: float | None = None,
) -> Classification:
    """document_type/legal_nature'dan stage, remedies, unit, confidence türetir.

    Hem kural motoru hem LLM yedeği (classify_document_llm_assist) bu tek fonksiyonu
    kullanır: LLM sadece hangi kategori olduğuna karar verir, gerisi (birim, aşama,
    kanun yolu, süre) her zaman aynı deterministik tablolardan gelir — LLM'e madde
    veya süre uydurma yetkisi verilmez.
    """
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

    remedies: list[str] = []
    if legal_nature == "ceza" and document_type in {"mahkeme_karari", "tebligat"}:
        remedies.extend(["itiraz", "istinaf", "temyiz"])
    if document_type not in KAMU_TYPES:
        if legal_nature == "ceza":
            # Nature'a bağlı: "istinaf"/"temyiz" idare metninde geçerse CMK süresine sızmasın.
            if "istinaf" in blob:
                remedies.append("istinaf")
            if "temyiz" in blob:
                remedies.append("temyiz")
        if legal_nature == "idare":
            remedies.append("idari_dava")
            if "istinaf" in blob:
                remedies.append("istinaf_idari")
            if "temyiz" in blob or "danıştay" in blob or "danistay" in blob:
                remedies.append("temyiz_idari")
        if legal_nature == "anayasa":
            remedies.append("bireysel_basvuru")
        if "şikayet" in blob or "sikayet" in blob:
            remedies.append("sikayet")
    unique = tuple(dict.fromkeys(remedies))

    unit = _TYPE_UNIT.get(document_type) or _NATURE_UNIT.get(legal_nature, "Evrak kayıt / ilgili birim")
    if document_type in {"mahkeme_karari", "tebligat", "iddianame"} and (
        "yargıtay" in blob or "yargitay" in blob
    ):
        unit = "Yargıtay ilgili ceza dairesi"

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
    if confidence_override is None:
        confidence = round(min(0.99, 0.32 + 0.11 * hits), 2)
    else:
        confidence = round(min(0.99, max(0.0, confidence_override)), 2)
    return Classification(
        document_type=document_type,
        legal_nature=legal_nature,
        unit=unit,
        stage=stage,
        remedies=unique,
        confidence=confidence,
        evidence_span=type_span or raw[:180],
        label=TYPE_LABELS.get(document_type, document_type),
    )


def _llm_prompt(raw: str) -> list[dict[str, str]]:
    types = ", ".join(key for key in TYPE_LABELS if key != "belirsiz")
    natures = ", ".join(_NATURE_CHOICES)
    system = (
        "Sen bir evrak türü sınıflandırıcısısın. Kural motoru bu metnin türünü kesin "
        "olarak belirleyemedi; sana yalnızca kapalı bir liste içinden seçim yapman için "
        "danışılıyor.\n"
        f"document_type YALNIZCA şu listeden seçilir: {types}, belirsiz\n"
        f"legal_nature YALNIZCA şu listeden seçilir: {natures}\n"
        "Listede olmayan bir değer, yeni bir tür veya madde numarası UYDURMA. Emin "
        'değilsen ilgili alan için "belirsiz" döndür.\n'
        "evidence alanı metinden BİREBİR alıntı olmalı (en fazla 160 karakter); metinde "
        "yoksa boş bırak.\n"
        "Yalnızca şu JSON şemasıyla cevap ver: "
        '{"document_type": "...", "legal_nature": "...", "evidence": "..."}'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": raw[:1500]},
    ]


def classify_document_llm_assist(
    text: str,
    base: Classification,
    *,
    chat_fn: Callable[[list[dict[str, str]]], str],
) -> Classification | None:
    """Kural motoru "belirsiz" veya düşük güvenle kaldığında tek seferlik LLM yedeği.

    LLM yalnızca document_type/legal_nature için kapalı listeden seçim yapar; stage,
    remedies, unit, süre kuralları her zaman _finalize() üzerinden aynı deterministik
    tablolardan türetilir — LLM'e yeni madde veya süre uydurma yetkisi verilmez.
    JSON bozuksa, liste dışı bir değer dönerse veya kural motorundan farklı bir sonuç
    çıkmazsa None döner; çağıran taraf kural motorunun sonucunu aynen korur.
    """
    raw = text.strip()
    if not raw:
        return None
    try:
        from llm.client import parse_json_content

        payload = parse_json_content(chat_fn(_llm_prompt(raw)))
    except Exception:
        return None

    llm_type = str(payload.get("document_type") or "").strip().lower()
    llm_nature = str(payload.get("legal_nature") or "").strip().lower()
    if llm_type not in TYPE_LABELS or llm_nature not in _NATURE_CHOICES:
        return None

    document_type = llm_type if llm_type != "belirsiz" else base.document_type
    legal_nature = llm_nature if llm_nature != "belirsiz" else base.legal_nature
    if document_type == base.document_type and legal_nature == base.legal_nature:
        return None  # LLM de kural motorundan farklı bir şey söylemedi

    evidence = str(payload.get("evidence") or "").strip()
    span = evidence if evidence and evidence.lower() in raw.lower() else ""
    blob = _norm(raw)
    return _finalize(
        raw,
        blob,
        document_type,
        legal_nature,
        type_span=span,
        confidence_override=0.6,
    )
