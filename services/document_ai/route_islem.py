from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IslemRoute:
    action: str
    title: str
    reason: str
    evidence: str
    confidence: float


# Kullanıcı derdini anlatır; kalıp buradan seçilir. Eşitlikte daha özgül kazanır.
_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tahliye", ("tahliye", "tutukluyum", "tutukluluk halinin", "cezaevinden çıkmak")),
    (
        "adli_kontrol_itiraz",
        ("adli kontrol", "imza yükümlülüğü", "yurt dışı yasağı", "yurt dışına çıkış yasağı"),
    ),
    ("bireysel_basvuru", ("bireysel başvuru", "anayasa mahkemesi", "temel hak ihlali")),
    ("temyiz", ("temyiz", "yargıtay'a", "yargitaya")),
    ("istinaf", ("istinaf", "bölge adliye", "hükmü istinaf", "kanun yoluna", "hükme karşı")),
    ("katilma", ("davaya katılma", "katılma talebi", "katılan sıfatı")),
    ("idari_dava", ("idare mahkemesi", "iptal davası", "tam yargı", "idari işlem", "2577")),
    ("itiraz", ("itiraz dilekçesi", "hakimlik kararına itiraz", "sulh ceza hakimliği")),
    ("cevap", ("cevap dilekçesi", "iddianameye cevap", "savunma dilekçesi")),
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
        confidence = 0.4
    else:
        reason = f"Anlatıya göre uygun format: {title}."
        confidence = round(min(0.99, 0.45 + 0.08 * min(best, 6)), 2)
    return IslemRoute(
        action=winner,
        title=title,
        reason=reason,
        evidence=evidence,
        confidence=confidence,
    )
