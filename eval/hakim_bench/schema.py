from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


QUESTION_TYPES = frozenset(
    {
        "factual",
        "semantic",
        "keyword",
        "comparison",
        "multi_hop",
        "aggregation",
        "ambiguous",
        "typo",
        "unanswerable",
    }
)
DIFFICULTIES = frozenset({"easy", "medium", "hard"})
_TYPE_ALIASES = {
    "simple factual": "factual",
    "keyword-heavy": "keyword",
    "keyword_heavy": "keyword",
    "multi-hop": "multi_hop",
    "typo/noisy": "typo",
    "typo_noisy": "typo",
}


class SchemaError(ValueError):
    pass


def _norm_type(raw: str) -> str:
    key = (raw or "").strip().lower().replace(" ", "_")
    return _TYPE_ALIASES.get((raw or "").strip().lower(), _TYPE_ALIASES.get(key, key))


@dataclass(frozen=True, slots=True)
class GoldQuestion:
    id: str
    question: str
    expected_answer: str
    question_type: str
    difficulty: str
    answerable: bool
    relevant_documents: tuple[str, ...] = ()
    relevant_chunks: tuple[str, ...] = ()
    relevant_articles: tuple[dict[str, str], ...] = ()

    @property
    def article_keys(self) -> frozenset[tuple[str, str]]:
        return frozenset(
            (str(item.get("law_no") or ""), str(item.get("article_no") or ""))
            for item in self.relevant_articles
            if item.get("law_no") and item.get("article_no")
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GoldQuestion":
        qid = str(raw.get("id") or "").strip()
        question = str(raw.get("question") or "").strip()
        expected = str(raw.get("expected_answer") or "").strip()
        qtype = _norm_type(str(raw.get("question_type") or ""))
        difficulty = str(raw.get("difficulty") or "easy").strip().lower()
        if not qid or not question:
            raise SchemaError("id and question are required")
        if qtype not in QUESTION_TYPES:
            raise SchemaError(f"unknown question_type: {raw.get('question_type')!r}")
        if difficulty not in DIFFICULTIES:
            raise SchemaError(f"unknown difficulty: {raw.get('difficulty')!r}")
        articles_raw = raw.get("relevant_articles") or []
        articles: list[dict[str, str]] = []
        if isinstance(articles_raw, list):
            for item in articles_raw:
                if not isinstance(item, dict):
                    continue
                law_no = str(item.get("law_no") or "").strip()
                article_no = str(item.get("article_no") or "").strip()
                if law_no and article_no:
                    articles.append({"law_no": law_no, "article_no": article_no})
        answerable = bool(raw.get("answerable", True))
        if qtype == "unanswerable":
            answerable = False
        return cls(
            id=qid,
            question=question,
            expected_answer=expected,
            question_type=qtype,
            difficulty=difficulty,
            answerable=answerable,
            relevant_documents=tuple(str(x) for x in (raw.get("relevant_documents") or [])),
            relevant_chunks=tuple(str(x) for x in (raw.get("relevant_chunks") or [])),
            relevant_articles=tuple(articles),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "relevant_documents": list(self.relevant_documents),
            "relevant_chunks": list(self.relevant_chunks),
            "relevant_articles": [dict(item) for item in self.relevant_articles],
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "answerable": self.answerable,
        }


@dataclass(frozen=True, slots=True)
class RetrievedHit:
    chunk_id: str
    document_id: str | None
    law_no: str | None
    article_no: str | None
    score: float
    rank: int
    content: str
    title: str | None = None


@dataclass
class ExperimentConfig:
    experiment_id: str
    chunk_method: str = "article"
    chunk_size: int | None = None
    chunk_overlap: int = 0
    embedding_model: str = "newmindai/Mursit-Base-TR-Retrieval"
    retrieval_method: str = "dense"
    top_k: int = 5
    threshold: float | None = None
    reranker: str = "none"
    retrieve_k: int = 5
    rerank_k: int = 5
    query_strategy: str = "original"
    llm: str = "llm-fast"
    temperature: float = 0.0
    prompt_version: str = "baseline"
    dense_weight: float = 0.5
    bm25_weight: float = 0.5
    input_per_million: float = 0.0
    output_per_million: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "chunk_method": self.chunk_method,
            "embedding_model": self.embedding_model,
            "retrieval_method": self.retrieval_method,
            "top_k": self.top_k,
            "threshold": self.threshold,
            "reranker": self.reranker,
            "retrieve_k": self.retrieve_k,
            "rerank_k": self.rerank_k,
            "query_strategy": self.query_strategy,
            "llm": self.llm,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
            "dense_weight": self.dense_weight,
            "bm25_weight": self.bm25_weight,
        }


@dataclass
class ExperimentRun:
    experiment_id: str
    timestamp: str
    config: dict[str, Any]
    metrics: dict[str, float]
    metrics_by_question_type: dict[str, dict[str, float]] = field(default_factory=dict)
    per_question: list[dict[str, Any]] = field(default_factory=list)
