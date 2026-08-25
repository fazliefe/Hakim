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
    ("tahliye", ("tahliye", "tutukluyum", "tutukluluk halinin", "cezaevinden çıkmak", "cezaevindeyim", "tutuklu kaldım")),
    (
        "adli_kontrol_itiraz",
        ("adli kontrol", "imza yükümlülüğü", "yurt dışı yasağı", "yurt dışına çıkış yasağı"),
    ),
    ("bireysel_basvuru", ("bireysel başvuru", "anayasa mahkemesi", "temel hak ihlali")),
    ("temyiz", ("temyiz", "yargıtay'a", "yargitaya", "yargıtaya")),
    (
        "istinaf",
        (
            "istinaf",
            "bölge adliye",
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
}


def _norm(text: str) -> str:
    folded = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
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
