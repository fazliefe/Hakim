"""İşlem taslağına emsal künyesi: canlı related/evidence.

Madde numarası uydurulmaz; ticaret-hukuk kararı tutulmaz. En fazla üç künye.
Temyiz/istinaf için yalnızca Yargıtay / ceza dairesi / CGK / İBK.
Konu (suç/TCK başlığı) ilamda yoksa künye basılmaz.
"""

from __future__ import annotations

import re
from typing import Any

EMSAL_LIMIT = 3
SPAN_CHARS = 280
ESAS_RE = re.compile(r"\d{4}/\d+")
CEZA_YOL = {
    "temyiz",
    "istinaf",
    "itiraz",
    "adli_kontrol_itiraz",
    "tahliye",
    "sikayet",
    "suc_duyurusu",
    "katilma",
}
_CEZA_BENCH = re.compile(
    r"yargitay|ceza daire|ceza genel|\bcgk\b|\bibk\b|ictihadi birlestir",
    re.I,
)
_IBK_RE = re.compile(r"\bibk\b|ictihadi birlestir", re.I)
_STOP = frozenset(
    {
        "mahkeme",
        "karar",
        "karari",
        "kararin",
        "temyiz",
        "istinaf",
        "dilekce",
        "tarih",
        "tarihi",
        "teblig",
        "hukum",
        "aleyhine",
        "basvuru",
        "nedeniyle",
        "hukuka",
        "aykirilik",
        "aykiriligi",
        "sonucunda",
        "incelenmesi",
        "incelemesi",
        "derece",
        "bolge",
        "adliye",
        "yoluna",
        "basvurmak",
        "istiyorum",
        "ilam",
        "ilami",
        "daire",
        "kurulu",
        "yargitay",
        "mahkumiyet",
        "mahkum",
        "hukmun",
        "bozulmasina",
        "verilmistir",
        "sucundan",
        "sanigin",
        "onama",
        "onanmasina",
        "onamasina",
        "bam",
        "dairesi",
        "mahkemesi",
        "mahkemesinin",
        "gerekceli",
        "onanmistir",
        "kurulugu",
        "ankara",
        "istanbul",
    }
)


def _span(text: Any, limit: int = SPAN_CHARS) -> str:
    return " ".join(str(text or "").split())[:limit]


def _fold(text: Any) -> str:
    raw = str(text or "").replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    return (
        raw.replace("ş", "s")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ö", "o")
        .replace("ç", "c")
        .replace("â", "a")
        .replace("î", "i")
        .replace("û", "u")
    )


def court_ok(court: Any) -> bool:
    c = _fold(court)
    if any(bad in c for bad in ("ticaret", "rekabet", "kvkk", "resmi_gazete")):
        return False
    if "hukuk" in c and "ceza" not in c:
        return False
    return True


def _hit_blob(hit: dict[str, Any]) -> str:
    return " ".join(
        str(hit.get(key) or "")
        for key in ("document_type", "court", "title", "document_id", "chunk_id")
    )


def _name_only_title(hit: dict[str, Any]) -> bool:
    title = str(hit.get("title") or "").strip()
    if not title or ESAS_RE.search(title) or re.search(r"\d", title):
        return False
    if re.search(r"daire|mahkeme|kurul|yargıtay|yargitay|danıştay|danistay|anayasa", title, re.I):
        return False
    words = [w for w in re.split(r"\s+", title) if w]
    if len(words) < 2 or len(words) > 4:
        return False
    return all(w[:1].isupper() for w in words)


def _is_ibk(blob: str) -> bool:
    return bool(_IBK_RE.search(_fold(blob)))


def bench_ok(hit: dict[str, Any], *, action: str = "") -> bool:
    blob = _hit_blob(hit)
    if not court_ok(blob):
        return False
    kind = (action or "").strip().lower()
    folded = _fold(blob)
    if kind in CEZA_YOL:
        if _name_only_title(hit):
            return False
        return bool(_CEZA_BENCH.search(folded))
    if kind == "idari_dava":
        return bool(re.search(r"danistay|idare", folded))
    if kind == "bireysel_basvuru":
        return bool(re.search(r"anayasa|\baym\b", folded))
    if _name_only_title(hit):
        return False
    return True


def is_court_hit(hit: Any) -> bool:
    if not isinstance(hit, dict):
        return False
    dtype = str(hit.get("document_type") or "").lower()
    if dtype == "court_decision":
        return True
    if hit.get("esas_no") or hit.get("atif"):
        return True
    if hit.get("court") and dtype != "law":
        return True
    doc_id = str(hit.get("document_id") or hit.get("chunk_id") or "")
    if doc_id.startswith("decision:"):
        return True
    title = str(hit.get("title") or "")
    if ESAS_RE.search(title) and re.search(
        r"ceza daire|ceza genel|yargıtay|yargitay|danıştay|danistay", title, re.I
    ):
        return True
    return False


def atif_line(hit: dict[str, Any]) -> str:
    ready = str(hit.get("atif") or "").strip()
    if ready:
        return ready
    title = str(hit.get("title") or "").strip()
    if title and ESAS_RE.search(title) and not hit.get("esas_no"):
        return title
    court = str(hit.get("court") or title or "ilgili mahkeme").strip()
    esas = str(hit.get("esas_no") or "").strip()
    karar = str(hit.get("karar_no") or hit.get("article_no") or "").strip()
    if karar in {"-", "None"}:
        karar = ""
    tarih = str(hit.get("karar_tarihi") or hit.get("valid_from") or "").strip()[:10]
    bits = [court]
    if esas:
        bits.append(f"{esas} esas")
    if karar:
        bits.append(f"{karar} karar")
    if tarih:
        bits.append(f"{tarih} tarihli")
    if len(bits) == 1:
        return court
    return ", ".join(bits) + " ilam"


def _tokens(text: Any) -> set[str]:
    return {w for w in re.findall(r"[a-z]{5,}", _fold(text)) if w not in _STOP}


def overlap_score(topic: set[str], hit: dict[str, Any]) -> int:
    hit_text = " ".join(
        str(hit.get(key) or "") for key in ("title", "court", "content", "span", "istisna")
    )
    return len(topic & _tokens(hit_text))


def topic_blob(engine: dict[str, Any]) -> str:
    parts = [str(engine.get("user_text") or "")]
    for hit in list(engine.get("related") or []) + list(engine.get("evidence") or []):
        if not isinstance(hit, dict) or is_court_hit(hit):
            continue
        parts.append(str(hit.get("title") or ""))
    return " ".join(parts)


def topic_terms(engine: dict[str, Any]) -> set[str]:
    return _tokens(topic_blob(engine))


def emsal_search_query(engine: dict[str, Any], *, action: str = "") -> str:
    """Mahkeme kararı araması: TCK başlığı / suç adı + daire, tam evrak metni değil."""
    titles: list[str] = []
    for hit in list(engine.get("related") or []) + list(engine.get("evidence") or []):
        if not isinstance(hit, dict) or is_court_hit(hit):
            continue
        title = str(hit.get("title") or "").strip()
        if title and not ESAS_RE.search(title):
            titles.append(title)
    if titles:
        head = titles[0]
    else:
        terms = sorted(topic_terms(engine), key=len, reverse=True)[:4]
        head = " ".join(terms)
    if not head.strip():
        return ""
    kind = (action or str(engine.get("action") or "")).strip().lower()
    if kind == "idari_dava":
        bench = "Danıştay"
    elif kind == "bireysel_basvuru":
        bench = "Anayasa Mahkemesi"
    else:
        bench = "Yargıtay ceza"
    return f"{head} {bench}".strip()


def merge_emsal_hits(related: list[Any], extra: list[Any], *, limit: int = EMSAL_LIMIT) -> list[Any]:
    out = list(related or [])
    seen: set[str] = set()
    for hit in out:
        if not isinstance(hit, dict):
            continue
        seen.add(str(hit.get("document_id") or hit.get("chunk_id") or hit.get("atif") or ""))
    added = 0
    for hit in extra or []:
        if not isinstance(hit, dict) or not is_court_hit(hit):
            continue
        key = str(hit.get("document_id") or hit.get("chunk_id") or atif_line(hit))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(hit)
        added += 1
        if added >= limit:
            break
    # `extra`, kendi retrieve() çağrısından n=1,2,3... diye numaralanmış
    # gelir — `related`'e olduğu gibi eklenirse aynı sıra no'lar iki kez
    # görünür (canlı doğrulandı: Kaynak grafiğinde iki ayrı karar "[1]"
    # rozetiyle listeleniyordu, atıf tıklaması yanlış maddeyi açıyordu).
    # Birleşmiş listeyi tek, sıralı bir numaralamaya geçiriyoruz (yeni
    # dict'ler — çağıranın elindeki orijinal nesneleri mutasyona uğratmadan).
    return [{**hit, "n": index} if isinstance(hit, dict) else hit for index, hit in enumerate(out, start=1)]


def attach_emsal_hits(
    related: list[Any],
    retrieve: Any,
    user_text: str,
    *,
    at: Any = None,
    action: str = "",
) -> list[Any]:
    if retrieve is None:
        return list(related or [])
    engine = {"user_text": user_text, "related": related, "action": action}
    query = emsal_search_query(engine, action=action)
    if not query:
        return list(related or [])
    try:
        extra = retrieve(query, at) or []
    except Exception:
        return list(related or [])
    return merge_emsal_hits(related, extra)


def honesty_line(atif: str, uyum: bool) -> str:
    if uyum:
        return (
            f"Arşivdeki {atif} metni bu başvurudaki kavramlarla örtüşmektedir; "
            "somut olay benzerliği mahkemece ayrıca değerlendirilir."
        )
    return f"Arşivde {atif} ilamı bulundu; somut uyum bu taslakta doğrulanmadı."


def _from_hits(
    hits: list[Any],
    *,
    limit: int,
    engine: dict[str, Any],
    action: str = "",
) -> list[dict[str, Any]]:
    topic = topic_terms(engine)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        if not is_court_hit(hit):
            continue
        if not bench_ok(hit, action=action):
            continue
        span = _span(hit.get("content") or hit.get("span") or hit.get("istisna"))
        blob = f"{_hit_blob(hit)} {span}"
        atif = atif_line(hit)
        ibk = _is_ibk(blob)
        if ibk and "İBK" not in atif and "ibk" not in _fold(atif):
            atif = f"İBK — {atif}"
        if not atif or atif in seen:
            continue
        score = overlap_score(topic, {**hit, "span": span})
        if not topic or score < 1:
            continue
        seen.add(atif)
        rows.append(
            {
                "n": hit.get("n") or len(rows) + 1,
                "court": hit.get("court") or None,
                "esas_no": hit.get("esas_no"),
                "karar_no": hit.get("karar_no") or hit.get("article_no"),
                "atif": atif,
                "span": span,
                "kind": "ibk" if ibk else "karar",
                "score": score,
                "uyum": True,
                "cumle": honesty_line(atif, True),
            }
        )
    rows.sort(key=lambda row: -int(row.get("score") or 0))
    return rows[:limit]


def _from_gold(action: str) -> list[dict[str, Any]]:
    from llm.gold import load_gold

    for row in load_gold():
        if row.get("action") != action:
            continue
        emsal = row.get("emsal") or {}
        if not court_ok(emsal.get("court")):
            continue
        atif = str(emsal.get("atif") or "").strip()
        if not atif:
            continue
        return [
            {
                "n": 1,
                "court": emsal.get("court"),
                "esas_no": emsal.get("esas_no"),
                "karar_no": emsal.get("karar_no"),
                "atif": atif,
                "span": _span(row.get("istisna") or row.get("senaryo")),
                "source": "gold",
            }
        ]
    return []


def pick_emsal(engine: dict[str, Any], *, action: str = "", limit: int = EMSAL_LIMIT) -> list[dict[str, Any]]:
    """Yalnızca canlı related/evidence. Konu kesişmeyen ilam dilekçeye girmez."""
    kind = action or str(engine.get("action") or "")
    return _from_hits(
        list(engine.get("emsal") or []) + list(engine.get("related") or []) + list(engine.get("evidence") or []),
        limit=limit,
        engine=engine,
        action=kind,
    )


def allowed_kuyne(emsal: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for item in emsal:
        blob = " ".join(str(item.get(key) or "") for key in ("esas_no", "karar_no", "atif"))
        tokens.update(ESAS_RE.findall(blob))
    return tokens


def emsal_atif_or_drop(value: Any, emsal: list[dict[str, Any]]) -> str:
    """Listede olmayan esas/karar varsa ilk izinli künyeyi yaz."""
    if not emsal:
        return ""
    first = str(emsal[0].get("atif") or "").strip()
    raw = str(value or "").strip()
    if not raw:
        return first
    allowed = allowed_kuyne(emsal)
    found = set(ESAS_RE.findall(raw))
    if found and allowed and not found <= allowed:
        return first
    return raw
