from __future__ import annotations

from typing import Callable

from hakim_bench.schema import GoldQuestion, RetrievedHit

ChatFn = Callable[..., str]

_REWRITE_SYSTEM = (
    "Türk hukuk arama motoru için tek satırlık bir sorgu yaz. "
    "Kanun adı ve madde numarası varsa koru. Açıklama, tırnak veya madde imi yok."
)
_HYDE_SYSTEM = (
    "Türk kanun maddesi gibi hipotetik bir pasaj yaz. Soru sorma, başlık atma. "
    "3-6 cümle, resmi dil. Uydurma madde numarası yazma."
)
_PROMPTS = {
    "baseline": (
        "Sadece verilen context'e göre cevap ver. "
        "Context'te cevap yoksa 'Bu bilgi mevcut kaynaklarda bulunmuyor.' de. "
        "Tahminde bulunma."
    ),
    "strict": (
        "Yalnızca context'teki cümlelere dayan. Context yetmezse birebir şu cümleyi yaz: "
        "Bu bilgi mevcut kaynaklarda bulunmuyor. Madde numarası uydurma, tahmin yok."
    ),
    "cite": (
        "Sadece context'e göre cevap ver. Her hukuki iddiayı [kanun_no m.madde] biçiminde kaynakla, "
        "örnek: [5237 m.158]. Context'te yoksa 'Bu bilgi mevcut kaynaklarda bulunmuyor.' de."
    ),
}


def _clip(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0]
    return cut or compact[:limit]


def rewrite_query(question: str, *, chat: ChatFn) -> str:
    text = question.strip()
    if not text:
        return text
    raw = chat(
        [
            {"role": "system", "content": _REWRITE_SYSTEM},
            {"role": "user", "content": text},
        ],
        json_mode=False,
        temperature=0.0,
        timeout=90.0,
    )
    first = ((raw or "").strip().splitlines() or [""])[0].strip().strip('"').strip("'")
    return _clip(first, 180) or text


def hyde_document(question: str, *, chat: ChatFn) -> str:
    text = question.strip()
    if not text:
        return text
    raw = chat(
        [
            {"role": "system", "content": _HYDE_SYSTEM},
            {"role": "user", "content": text},
        ],
        json_mode=False,
        temperature=0.0,
        timeout=90.0,
    )
    passage = (raw or "").strip()
    return _clip(passage, 1200) or text


def lexical_and_dense_queries(question: str, strategy: str, *, chat: ChatFn) -> tuple[str, str]:
    if strategy == "rewrite":
        rewritten = rewrite_query(question, chat=chat)
        return rewritten, rewritten
    if strategy == "hyde":
        return question, hyde_document(question, chat=chat)
    return question, question


def prompt_messages(
    question: GoldQuestion,
    hits: list[RetrievedHit],
    prompt_version: str,
) -> list[dict[str, str]]:
    system = _PROMPTS.get(prompt_version) or _PROMPTS["baseline"]
    context = "\n\n".join(
        f"[{i}] {hit.law_no or ''} m.{hit.article_no or ''} {hit.content[:800]}"
        for i, hit in enumerate(hits, start=1)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Soru: {question.question}\n\nContext:\n{context}"},
    ]
