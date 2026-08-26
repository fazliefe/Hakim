from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IslemRoute:
    action: str
    title: str
    reason: str
    evidence: str
    # Kazanan kalıbın needle-eşleşme skoruna göre ölçeklenmiş bir değer —
    # istatistiksel kalibrasyon değil (bkz. classify.py::_confidence_from_hits
    # ile aynı ilke). "Kalıp ne kadar net eşleşti" olarak okunmalı.
    confidence: float


# Kullanıcı derdini anlatır; kalıp buradan seçilir. Eşitlikte daha özgül kazanır.
_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "ihtiyac_tahliye",
        (
            "ihtiyaç sebebiyle tahliye",
            "ihtiyac sebebiyle tahliye",
            "kira tahliye",
            "kiracıyı tahliye",
            "kiraciyi tahliye",
            "sulh hukuk tahliye",
        ),
    ),
    ("tahliye", ("tahliye", "tutukluyum", "tutukluluk halinin", "cezaevinden çıkmak", "cezaevindeyim", "tutuklu kaldım")),
    (
        "adli_kontrol_itiraz",
        ("adli kontrol", "imza yükümlülüğü", "yurt dışı yasağı", "yurt dışına çıkış yasağı"),
    ),
    ("bireysel_basvuru", ("bireysel başvuru", "anayasa mahkemesi", "temel hak ihlali")),
    (
        "temyiz_cevap",
        ("temyize cevap", "temyizine cevap", "karşı temyiz", "karsi temyiz", "temyize cevap ve karşı"),
    ),
    ("temyiz", ("temyiz", "yargıtay'a", "yargitaya", "yargıtaya")),
    (
        "sure_uzatim",
        ("süre uzatım", "sure uzatim", "süre uzatımı", "cevap süresi uzat", "cevap suresi uzat"),
    ),
    (
        "icra_borca_itiraz",
        ("borca itiraz", "ilamsız icra", "ilamsiz icra", "icra müdürlüğü", "icra mudurlugu"),
    ),
    (
        "istinaf",
        (
            "istinaf etmek",
            "istinaf dilek",
            "istinaf yoluna",
            "hükmü istinaf",
            "kanun yoluna",
            "hükme karşı",
            "üst mahkeme",
            "ust mahkeme",
            "mahkumiyet kararı",
        ),
    ),
    ("katilma", ("davaya katılma", "katılma talebi", "katılan sıfatı")),
    ("idari_dava", ("idare mahkemesi", "iptal davası", "tam yargı", "idari işlem", "2577")),
    ("itiraz", ("itiraz dilekçesi", "hakimlik kararına itiraz", "sulh ceza hakimliği")),
    ("cevap", ("cevap dilekçesi", "iddianameye cevap", "savunma dilekçesi", "iddianame tebliğ")),
    ("suc_duyurusu", ("suç duyurusu", "ihbar etmek", "ihbarda bulun")),
    (
        "sikayet",
        (
            "şikayet",
            "sikayet",
            "dolandırıldım",
            "paramı aldılar",
            "paramı çaldı",
            "şikayetçiyim",
            "savcılığa başvur",
            "savcıya gitmek",
            "hakaret",
            "darp edildi",
        ),
    ),
]

ACTION_TITLES: dict[str, str] = {
    "sikayet": "Şikayet dilekçesi",
    "suc_duyurusu": "Suç duyurusu",
    "cevap": "Cevap dilekçesi",
    "itiraz": "İtiraz dilekçesi",
    "istinaf": "İstinaf dilekçesi",
    "temyiz": "Temyiz dilekçesi",
    "katilma": "Davaya katılma talebi",
    "bireysel_basvuru": "Bireysel başvuru",
    "idari_dava": "İdari dava dilekçesi",
    "tahliye": "Tahliye talebi",
    "adli_kontrol_itiraz": "Adli kontrol itirazı",
    "temyiz_cevap": "Temyize cevap dilekçesi",
    "sure_uzatim": "Süre uzatım talebi",
    "icra_borca_itiraz": "İcra takibine (ödeme emrine) itiraz",
    "ihtiyac_tahliye": "İhtiyaç sebebiyle tahliye",
}


def _norm(text: str) -> str:
    folded = (
        text.replace("İ", "i")
        .replace("I", "i")
        .replace("ı", "i")
        .replace("ş", "s")
        .replace("Ş", "s")
        .replace("ğ", "g")
        .replace("Ğ", "g")
        .replace("ü", "u")
        .replace("Ü", "u")
        .replace("ö", "o")
        .replace("Ö", "o")
        .replace("ç", "c")
        .replace("Ç", "c")
        .replace("â", "a")
        .replace("Â", "a")
    )
    return " ".join(folded.lower().split())


_ROUTE_CONFIDENCE_FLOOR = 0.15
_ROUTE_CONFIDENCE_CEILING = 0.95
# `best` (kazanan kalıbın needle skor toplamı) bu değerde doyar — tek bir
# başlık-içi eşleşme (2+3) zaten neredeyse tavana yaklaşır.
_ROUTE_CONFIDENCE_CAP = 6


def _route_confidence(best: int) -> float:
    """`best == 0` (hiçbir kalıp işareti yok) en düşük banda düşer — eski
    kod bu durumu sabit 0.4'e bağlıyordu, bu da hiç eşleşmeyen bir metni
    zayıf-ama-gerçek bir eşleşmeden (ör. best=2 → eski formülde 0.61) daha
    "güvenilir" gösteriyordu. İstatistiksel kalibrasyon değil, bkz.
    classify.py::_confidence_from_hits ile aynı ilke."""
    span = _ROUTE_CONFIDENCE_CEILING - _ROUTE_CONFIDENCE_FLOOR
    ratio = min(best, _ROUTE_CONFIDENCE_CAP) / _ROUTE_CONFIDENCE_CAP
    return round(_ROUTE_CONFIDENCE_FLOOR + span * ratio, 2)


_TEMYIZ_ASK = ("temyiz", "yargitay'a", "yargitaya", "yargıtaya")
_TEMYIZ_CEVAP_ASK = ("temyize cevap", "temyizine cevap", "karsi temyiz", "karşı temyiz")
_ISTINAF_ASK = ("istinaf etmek", "istinaf dilek", "istinaf yoluna basvur", "hükmü istinaf")


def _prefers_temyiz(blob: str) -> bool:
    """BAM başlığı / 'istinaf incelemesi onandı' geçmiş anlatıdır; talep temyizse temyiz kazanır."""
    if any(_norm(token) in blob for token in _TEMYIZ_CEVAP_ASK):
        return False
    if not any(_norm(token) in blob for token in _TEMYIZ_ASK):
        return False
    if any(_norm(token) in blob for token in _ISTINAF_ASK):
        return False
    return True


def _span(text: str, needle: str) -> str:
    folded = _norm(text)
    token = _norm(needle)
    idx = folded.find(token)
    if idx < 0:
        return needle
    start = max(0, idx - 20)
    end = min(len(text), idx + len(needle) + 36)
    return " ".join(text[start:end].split())


def route_islem(text: str) -> IslemRoute:
    raw = text.strip()
    blob = _norm(raw)
    header = blob[:420]
    winner = "sikayet"
    best = 0
    evidence = raw[:160]
    for action, needles in _INTENT_RULES:
        score = 0
        hit = ""
        for needle in needles:
            token = _norm(needle)
            if not token or token not in blob:
                continue
            score += 2
            if token in header:
                score += 3
            if not hit:
                hit = _span(raw, needle)
        if score > best:
            best = score
            winner = action
            evidence = hit or evidence
    if any(_norm(token) in blob for token in _TEMYIZ_CEVAP_ASK):
        winner = "temyiz_cevap"
        evidence = _span(raw, "temyiz")
        best = max(best, 8)
    elif _prefers_temyiz(blob):
        winner = "temyiz"
        evidence = _span(raw, "temyiz")
        best = max(best, 8)
    title = ACTION_TITLES[winner]
    if best == 0:
        reason = (
            f"Dert metninde açık kalıp işareti yok; varsayılan {title}. "
            "Soldan başka kalıp seçebilirsiniz."
        )
        confidence = _route_confidence(0)
    else:
        reason = f"Anlatıya göre uygun format: {title}."
        confidence = _route_confidence(best)
    return IslemRoute(
        action=winner,
        title=title,
        reason=reason,
        evidence=evidence,
        confidence=confidence,
    )
