from __future__ import annotations

import re

_WORD_RE = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşü]+", re.UNICODE)

_STOP = {
    "hangi",
    "maddede",
    "maddeleriyle",
    "maddelerinin",
    "düzenlenir",
    "nedir",
    "nelerdir",
    "hangileridir",
    "ile",
    "ve",
    "veya",
    "bir",
    "bu",
    "şu",
    "mi",
    "mı",
    "mu",
    "mü",
    "nasıl",
    "neden",
    "için",
    "olan",
    "olarak",
    "sonra",
    "kadar",
}

GROUP_EXPAND: dict[str, list[str]] = {
    "öldürme suçları": ["kasten öldürme", "nitelikli kasten öldürme", "taksirle öldürme"],
    "yaralama suçları": ["kasten yaralama", "neticesi sebebiyle ağırlaşmış yaralama", "taksirle yaralama"],
    "malvarlığına karşı zorla alma": ["hırsızlık", "nitelikli hırsızlık", "yağma", "nitelikli yağma"],
    "dolandırıcılık türleri": ["dolandırıcılık", "nitelikli dolandırıcılık"],
    "özgürlüğü kısıtlayan koruma tedbirleri": ["yakalama", "gözaltı", "tutuklama"],
    "ceza kanun yolları": ["istinaf", "temyiz"],
    "manevi unsur": ["kast", "taksir"],
    "iştirak şekilleri": ["faillik", "azmettirme", "yardım etme"],
    "trafik güvenliği": ["trafik güvenliğini tehlikeye sokma", "taksirle trafik"],
    "idari yargı başvurusu": ["iptal davası", "yürütmenin durdurulması"],
}

SYNONYMS: dict[str, list[str]] = {
    "öldürme": ["kasten öldürme", "taksirle öldürme", "cinayet"],
    "yaralama": ["kasten yaralama", "taksirle yaralama"],
    "dolandırıcılık": ["nitelikli dolandırıcılık", "hile"],
    "hırsızlık": ["nitelikli hırsızlık", "yağma"],
    "tutuklama": ["gözaltı", "yakalama", "koruma tedbiri"],
}

_MULTI_MARK = (
    "hangileri",
    "hangileridir",
    "listesini",
    "listesi",
    "türleri",
    "şekilleri",
    "toplanır",
    "toplanir",
)


def _tokens(text: str) -> list[str]:
    return [tok.lower() for tok in _WORD_RE.findall(text or "")]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = " ".join(item.split()).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def query_needs_multi(query: str) -> bool:
    """Liste/aggregation soruları — tek madde araması BM25'i erken kesiyor."""
    blob = (query or "").casefold()
    if any(mark in blob for mark in _MULTI_MARK):
        return True
    return any(label in blob for label in GROUP_EXPAND)


def expand_queries(question: str, strategy: str) -> list[str]:
    text = (question or "").strip()
    if not text:
        return [""]
    if strategy not in {"multi_query", "expand"}:
        return [text]
    variants = [text]
    lowered = text.casefold()
    if strategy == "multi_query":
        variants.append(f"{text} hangi maddede düzenlenir")
        keep = [tok for tok in _tokens(text) if tok not in _STOP and len(tok) > 2]
        if keep:
            variants.append(" ".join(keep[:10]))
        for label, members in GROUP_EXPAND.items():
            if label in lowered:
                variants.extend(members)
    else:
        extra: list[str] = []
        for key, syns in SYNONYMS.items():
            if key in lowered:
                extra.extend(syns)
        if extra:
            variants.append(text + " " + " ".join(extra[:4]))
            variants.extend(extra[:3])
    return _dedupe(variants)[:6]
