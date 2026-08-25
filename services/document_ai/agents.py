from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from document_ai.classify import Classification, KAMU_TYPES

# skip = iş bu türde yok (zinciri bozmaz). warn/error sonraki adımlara yayılır.
PROPAGATE_STATES = frozenset({"warn", "error"})


@dataclass
class AgentStep:
    id: str
    title: str
    state: str
    ms: int
    summary: str
    confidence: float | None = None
    depends_on: str | None = None
    note: str | None = None
    answer: str | None = None


def now() -> float:
    return perf_counter()


def elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def step(
    agent_id: str,
    title: str,
    *,
    state: str,
    ms: int,
    summary: str,
    confidence: float | None = None,
    note: str | None = None,
    answer: str | None = None,
) -> dict[str, Any]:
    return asdict(
        AgentStep(
            id=agent_id,
            title=title,
            state=state,
            ms=ms,
            summary=summary,
            confidence=confidence,
            note=note,
            answer=answer or summary,
        )
    )


def diagnose_chain(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Omanic: bilgi tabanı zayıfsa CoT yetmez; hata sonraki adımlara yayılır."""
    origin_id: str | None = None
    origin_title: str | None = None
    for item in agents:
        if origin_id:
            item["depends_on"] = origin_id
            if item.get("state") == "done":
                item["state"] = "warn"
            dep = f"Önceki adım ({origin_title}) emin değil; bu çıktı ona bağlı."
            existing = str(item.get("note") or "").strip()
            if dep not in existing:
                item["note"] = f"{existing} {dep}".strip() if existing else dep
        if origin_id is None and item.get("state") in PROPAGATE_STATES:
            origin_id = str(item.get("id") or "")
            origin_title = str(item.get("title") or origin_id)
    return agents


def chain_status(agents: list[dict[str, Any]]) -> str:
    states = {str(item.get("state") or "") for item in agents}
    if "error" in states:
        return "broken"
    if "warn" in states:
        return "fragile"
    return "solid"


HOP_QUESTIONS = {
    "okuyucu": "Evrak okundu mu, metin yeterli mi?",
    "sinif": "Bu evrak hangi türde ve hangi hukuki nitelikte?",
    "mevzuat": "Hangi mevzuat veya yazışma kuralı geçerli?",
    "sure": "İşleyen bir süre var mı, son gün nedir?",
    "taslak": "Hangi resmi yazı yazılmalı?",
    "havale": "Evrak hangi birime gitmeli?",
}


def build_reasoning(
    agents: list[dict[str, Any]],
    *,
    verdict: str = "",
    route_reason: str = "",
) -> dict[str, Any]:
    """Omanic tarzı adım adım zincir: soru → cevap → neden. Uydurma yok."""
    hops: list[dict[str, Any]] = []
    for index, item in enumerate(agents, start=1):
        agent_id = str(item.get("id") or "")
        why = str(item.get("note") or "").strip()
        if agent_id == "taslak" and route_reason:
            why = f"{why} {route_reason}".strip() if why else route_reason
        if agent_id == "havale" and not why:
            why = "Sınıflandırıcının birim önerisi. EBYS/UYAP gönderimi yoktur."
        hops.append(
            {
                "n": index,
                "id": agent_id,
                "title": item.get("title"),
                "question": HOP_QUESTIONS.get(agent_id, item.get("title")),
                "answer": item.get("answer") or item.get("summary"),
                "why": why or None,
                "state": item.get("state"),
                "depends_on": item.get("depends_on"),
            }
        )
    status = chain_status(agents)
    if status == "solid":
        closer = "Zincir kapandı: her adım kendi bilgisine dayanıyor."
    elif status == "broken":
        closer = "Zincir kırık: bir adım hata verdi; sonraki sonuçlara güvenme."
    else:
        closer = "Zincir kırılgan: en az bir adımda bilgi eksik. Sonraki cevaplar ona bağlı."
    return {
        "status": status,
        "hops": hops,
        "conclusion": " ".join(part for part in (verdict.strip(), closer) if part),
    }


def route_yazisma(classification: Classification) -> tuple[str, str]:
    """Görev 2: evrak türünden resmi yazı / dilekçe kalıbı."""
    kind = classification.document_type
    nature = classification.legal_nature
    if kind == "mahkeme_karari" and nature == "ceza":
        return "istinaf", "İlk derece ceza hükmü → istinaf dilekçesi (CMK m.273)."
    if kind == "mahkeme_karari" and nature == "hukuk":
        if classification.stage == "temyiz":
            return "temyiz_hukuk", "Bölge Adliye Mahkemesi (istinaf) kararı → temyiz dilekçesi (HMK m.361)."
        return "istinaf_hukuk", "İlk derece hukuk hükmü → istinaf dilekçesi (HMK m.345)."
    if kind == "iddianame":
        return "cevap", "İddianame → cevap dilekçesi."
    if kind == "tebligat":
        return "cevap", "Tebligat → cevap / beyan yazısı."
    if kind == "dilekce":
        return "cevap", "Gelen dilekçe → cevap yazısı."
    if kind == "olur":
        return "olur", "Olur evrakı → Yönetmelik Ek Örnek 17 düzeni."
    if kind in {"ust_yazi", "rapor"}:
        return "ust_yazi", "Kamu evrakı → üst yazı / havale (Örnek 3/8)."
    if kind in {"genelge", "tutanak", "bilgi_yazisi"}:
        return "bilgi_yazisi", "Duyuru / tutanak → bilgi yazısı (Örnek 14-16)."
    if kind == "cevap_yazisi":
        return "cevap_yazisi", "Cevap yazısı → ilgi + cevaben metin (Örnek 7)."
    if kind in KAMU_TYPES:
        return "ust_yazi", "Kamu yazışması → üst yazı."
    return "ust_yazi", "Varsayılan resmi yazışma: üst yazı."


def pick_yazisma_action(classification: Classification, text: str) -> tuple[str, str]:
    """Bilinen tür → tür kalıbı; belirsiz anlatı → kullanıcının derdine göre kalıp."""
    if classification.document_type != "belirsiz":
        return route_yazisma(classification)
    from document_ai.route_islem import route_islem

    routed = route_islem(text)
    return routed.action, routed.reason


def mark_writer(agents: list[dict[str, Any]], *, writer: str, ms: int, error: str | None = None) -> None:
    for item in agents:
        if item.get("id") != "taslak":
            continue
        item["ms"] = int(item.get("ms") or 0) + ms
        if error:
            item["state"] = "error"
            item["summary"] = f"Yazıcı hata: {error[:160]}"
        else:
            base = str(item.get("summary") or "Kalıp")
            if "Yazıcı:" not in base:
                item["summary"] = f"{base} · Yazıcı: {writer}"
            if item.get("state") != "warn":
                item["state"] = "done"
        break
    diagnose_chain(agents)
