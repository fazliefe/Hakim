from __future__ import annotations

import time
from typing import Any

from hakim_bench.llm_queries import lexical_and_dense_queries, prompt_messages
from hakim_bench.queries import expand_queries
from hakim_bench.schema import GoldQuestion, RetrievedHit


def passes_dense_gate(hits: list[RetrievedHit], threshold: float | None) -> bool:
    """Dense cosine gate. RRF scores are ~0.03 and must not be compared to 0.70."""
    if threshold is None:
        return True
    return bool(hits) and hits[0].score >= threshold


def forward_api_chat(messages: list[dict[str, str]], **kwargs: Any) -> str:
    from llm.api_client import api_chat

    kwargs.setdefault("json_mode", False)
    return api_chat(messages, **kwargs)


def resolve_law_no(
    question: GoldQuestion,
    *,
    strategy: str,
    fallback: str | None = None,
) -> str | None:
    """Faz 9: filter ES by kanun when the query (or gold oracle) names one law."""
    if fallback:
        return fallback
    if strategy == "law_hint":
        from retrieval.bm25 import parse_law_hint

        return parse_law_hint(question.question)
    if strategy == "oracle_law":
        laws = {str(item.get("law_no") or "") for item in question.relevant_articles if item.get("law_no")}
        if len(laws) == 1:
            return next(iter(laws))
    return None


def _hit_from_search(hit: Any, rank: int) -> RetrievedHit:
    return RetrievedHit(
        chunk_id=str(getattr(hit, "chunk_id", "") or ""),
        document_id=getattr(hit, "document_id", None),
        law_no=getattr(hit, "law_no", None),
        article_no=getattr(hit, "article_no", None),
        score=float(getattr(hit, "score", 0.0) or 0.0),
        rank=rank,
        content=str(getattr(hit, "content", "") or ""),
        title=getattr(hit, "title", None),
    )


def _hit_from_fused(hit: Any, rank: int) -> RetrievedHit:
    inner = hit.hit
    return RetrievedHit(
        chunk_id=str(hit.chunk_id),
        document_id=inner.document_id,
        law_no=inner.law_no,
        article_no=inner.article_no,
        score=float(hit.rrf_score),
        rank=rank,
        content=inner.content or "",
        title=inner.title,
    )


class LivePipeline:
    """Talks to the live Elasticsearch index. Does not rechunk."""

    def __init__(
        self,
        *,
        es_client: Any | None = None,
        embedder: Any | None = None,
        reranker: Any | None = None,
        generator: str = "extractive",
        law_no: str | None = None,
        prefer_neural: bool = True,
        index_name: str | None = None,
        chat: Any | None = None,
    ) -> None:
        from retrieval.embeddings import HashingEmbedder, create_embedder
        from retrieval.es_client import create_es_client
        from retrieval.hybrid import HybridSearcher

        self.es = es_client or create_es_client()
        if embedder is not None:
            self.embedder = embedder
        elif prefer_neural:
            self.embedder = create_embedder(prefer_neural=True)
        else:
            self.embedder = HashingEmbedder()
        self.hybrid = HybridSearcher(
            self.es,
            self.embedder,
            bm25_size=50,
            semantic_size=50,
            limit=50,
            index_name=index_name,
        )
        self.reranker = reranker
        self.generator = generator
        self.law_no = law_no
        self.chat = chat

    def retrieve(
        self,
        question: GoldQuestion,
        *,
        top_k: int,
        retrieve_k: int,
        retrieval_method: str,
        threshold: float | None,
        reranker: str,
        rerank_k: int,
        query_strategy: str = "original",
    ) -> tuple[list[RetrievedHit], dict[str, float]]:
        from retrieval.rerank import rerank_fused
        from retrieval.rrf import FusedHit

        started = time.perf_counter()
        pool = max(retrieve_k, top_k, rerank_k, 10)
        query = question.question
        law_no = resolve_law_no(question, strategy=query_strategy, fallback=self.law_no)
        lexical, dense = query, query
        if query_strategy in {"rewrite", "hyde"}:
            try:
                lexical, dense = lexical_and_dense_queries(query, query_strategy, chat=self._chat)
            except Exception:
                lexical, dense = query, query
            query = lexical
        queries = expand_queries(query, query_strategy)
        if retrieval_method == "bm25":
            raw = self.hybrid.search_bm25(query, law_no=law_no)[:pool]
            hits = [_hit_from_search(item, i) for i, item in enumerate(raw, start=1)]
            fused: list[FusedHit] | None = None
        elif retrieval_method == "hybrid":
            if threshold is not None:
                probe = [
                    _hit_from_search(item, i)
                    for i, item in enumerate(self.hybrid.search_semantic(dense, law_no=law_no)[:1], start=1)
                ]
                if not passes_dense_gate(probe, threshold):
                    elapsed = (time.perf_counter() - started) * 1000.0
                    return [], {"retrieve_ms": elapsed}
            if query_strategy in {"hyde", "rewrite"}:
                try:
                    fused = self.hybrid.fuse(
                        lexical,
                        self.hybrid.search_bm25(lexical, law_no=law_no),
                        self.hybrid.search_semantic(dense, law_no=law_no),
                        limit=pool,
                    )
                except Exception:
                    fused = self.hybrid.search(question.question, law_no=law_no, limit=pool)
                    query = question.question
            elif len(queries) > 1:
                fused = self.hybrid.search_multi(queries, law_no=law_no, limit=pool)
            else:
                fused = self.hybrid.search(query, law_no=law_no, limit=pool)
            hits = [_hit_from_fused(item, i) for i, item in enumerate(fused, start=1)]
        else:
            raw = self.hybrid.search_semantic(query, law_no=law_no)[:pool]
            hits = [_hit_from_search(item, i) for i, item in enumerate(raw, start=1)]
            fused = None
        if threshold is not None and retrieval_method != "hybrid":
            hits = [h for h in hits if h.score >= threshold]
            hits = [
                RetrievedHit(
                    chunk_id=h.chunk_id,
                    document_id=h.document_id,
                    law_no=h.law_no,
                    article_no=h.article_no,
                    score=h.score,
                    rank=i,
                    content=h.content,
                    title=h.title,
                )
                for i, h in enumerate(hits, start=1)
            ]
        if reranker != "none" and fused is not None:
            scorer = self.reranker if reranker == "cross-encoder" else None
            fused = rerank_fused(query, fused, limit=max(rerank_k, 10), scorer=scorer)
            hits = [_hit_from_fused(item, i) for i, item in enumerate(fused, start=1)]
        elapsed = (time.perf_counter() - started) * 1000.0
        return hits, {"retrieve_ms": elapsed}

    def generate(
        self,
        question: GoldQuestion,
        hits: list[RetrievedHit],
        *,
        temperature: float,
        llm: str,
        prompt_version: str,
    ) -> tuple[str, dict[str, float]]:
        started = time.perf_counter()
        ordered = list(reversed(hits)) if prompt_version == "reverse" else hits
        if self.generator != "llm":
            answer = _extractive_answer(question, ordered)
            elapsed = (time.perf_counter() - started) * 1000.0
            ctx_tokens = sum(len((h.content or "").split()) for h in hits)
            return answer, {
                "generate_ms": elapsed,
                "input_tokens": ctx_tokens,
                "output_tokens": len(answer.split()),
                "context_tokens": ctx_tokens,
            }
        answer, usage = _llm_answer(
            question,
            ordered,
            temperature=temperature,
            model=llm,
            prompt_version=prompt_version,
            chat=self._chat,
        )
        elapsed = (time.perf_counter() - started) * 1000.0
        ctx_tokens = sum(len((h.content or "").split()) for h in hits)
        return answer, {
            "generate_ms": elapsed,
            "input_tokens": float(usage.get("input_tokens") or ctx_tokens),
            "output_tokens": float(usage.get("output_tokens") or len(answer.split())),
            "context_tokens": ctx_tokens,
        }

    def _chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        if self.chat is not None:
            return self.chat(messages, **kwargs)
        return forward_api_chat(messages, **kwargs)


def _extractive_answer(question: GoldQuestion, hits: list[RetrievedHit]) -> str:
    del question
    if not hits:
        return "Bu bilgi mevcut kaynaklarda bulunmuyor."
    parts: list[str] = []
    for hit in hits[:3]:
        cite = ""
        if hit.law_no and hit.article_no:
            cite = f"[{hit.law_no} m.{hit.article_no}] "
        parts.append(cite + (hit.content or hit.title or "")[:400])
    return " ".join(parts).strip() or "Bu bilgi mevcut kaynaklarda bulunmuyor."


def _llm_answer(
    question: GoldQuestion,
    hits: list[RetrievedHit],
    *,
    temperature: float,
    model: str,
    prompt_version: str = "baseline",
    chat: Any | None = None,
) -> tuple[str, dict[str, float]]:
    from llm.usage import take_usage

    if not hits:
        return "Bu bilgi mevcut kaynaklarda bulunmuyor.", {"input_tokens": 0, "output_tokens": 0}
    messages = prompt_messages(question, hits, prompt_version)
    if chat is None:
        from llm.api_client import api_chat

        text = api_chat(messages, timeout=60.0, json_mode=False, temperature=temperature, model=model)
    else:
        text = chat(messages, timeout=60.0, temperature=temperature, model=model)
    used = take_usage()
    return text or "", {
        "input_tokens": float(used.prompt_tokens),
        "output_tokens": float(used.completion_tokens),
    }

