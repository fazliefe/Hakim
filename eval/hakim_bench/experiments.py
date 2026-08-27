from __future__ import annotations

from dataclasses import replace

from hakim_bench.schema import ExperimentConfig

try:
    from hakim_config import get_models
except Exception:  # pragma: no cover - bench can run without config
    get_models = None  # type: ignore[assignment]


def _from_config() -> tuple[str, str, float, float]:
    if get_models is None:
        return (
            "newmindai/Mursit-Base-TR-Retrieval",
            "llm-fast",
            0.0,
            0.0,
        )
    cfg = get_models()
    return (
        cfg.embedding_model,
        cfg.llm_model,
        cfg.llm_input_per_million,
        cfg.llm_output_per_million,
    )


_embed, _llm, _in, _out = _from_config()

BASELINE = ExperimentConfig(
    experiment_id="baseline",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="dense",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

# Current HÂKİM production snapshot — later phases compare against this too.
PRODUCTION = ExperimentConfig(
    experiment_id="production",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="cross-encoder",
    retrieve_k=50,
    rerank_k=12,
    query_strategy="original",
    llm=_llm,
    temperature=0.2,
    prompt_version="production",
    input_per_million=_in,
    output_per_million=_out,
)

BM25 = ExperimentConfig(
    experiment_id="bm25",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID = ExperimentConfig(
    experiment_id="hybrid",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

RR_10_5 = ExperimentConfig(
    experiment_id="rr_10_5",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="cross-encoder",
    retrieve_k=10,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

RR_20_5 = ExperimentConfig(
    experiment_id="rr_20_5",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="cross-encoder",
    retrieve_k=20,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_GATED = ExperimentConfig(
    experiment_id="hybrid_gated",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=0.70,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_HINT = ExperimentConfig(
    experiment_id="hybrid_hint",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="law_hint",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_ORACLE = ExperimentConfig(
    experiment_id="hybrid_oracle",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="oracle_law",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_BM25W = ExperimentConfig(
    experiment_id="hybrid_bm25w",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    dense_weight=0.2,
    bm25_weight=0.8,
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_DENSEW = ExperimentConfig(
    experiment_id="hybrid_densew",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    dense_weight=0.8,
    bm25_weight=0.2,
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_MQ = ExperimentConfig(
    experiment_id="hybrid_mq",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="multi_query",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_EXPAND = ExperimentConfig(
    experiment_id="hybrid_expand",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="expand",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

DENSE_HASH = ExperimentConfig(
    experiment_id="dense_hash",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model="HashingEmbedder",
    retrieval_method="dense",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_REV = ExperimentConfig(
    experiment_id="hybrid_rev",
    chunk_method="article",
    chunk_size=None,
    chunk_overlap=0,
    embedding_model=_embed,
    retrieval_method="hybrid",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=50,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="reverse",
    input_per_million=_in,
    output_per_million=_out,
)

HYBRID_LLM = replace(HYBRID, experiment_id="hybrid_llm", temperature=0.0, prompt_version="baseline")
HYBRID_TEMP02 = replace(HYBRID, experiment_id="hybrid_temp02", temperature=0.2)
HYBRID_TEMP07 = replace(HYBRID, experiment_id="hybrid_temp07", temperature=0.7)
HYBRID_PROMPT_STRICT = replace(HYBRID, experiment_id="hybrid_prompt_strict", prompt_version="strict")
HYBRID_PROMPT_CITE = replace(HYBRID, experiment_id="hybrid_prompt_cite", prompt_version="cite")
HYBRID_LLM_LARGE = replace(HYBRID, experiment_id="hybrid_llm_large", llm="llm-large")
HYBRID_HYDE = replace(HYBRID, experiment_id="hybrid_hyde", query_strategy="hyde")
HYBRID_REWRITE = replace(HYBRID, experiment_id="hybrid_rewrite", query_strategy="rewrite")

CHUNK256 = ExperimentConfig(
    experiment_id="chunk256",
    chunk_method="window",
    chunk_size=256,
    chunk_overlap=0,
    embedding_model="HashingEmbedder",
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

CHUNK512 = ExperimentConfig(
    experiment_id="chunk512",
    chunk_method="window",
    chunk_size=512,
    chunk_overlap=0,
    embedding_model="HashingEmbedder",
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

CHUNK1024 = ExperimentConfig(
    experiment_id="chunk1024",
    chunk_method="window",
    chunk_size=1024,
    chunk_overlap=0,
    embedding_model="HashingEmbedder",
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

CHUNK512O64 = ExperimentConfig(
    experiment_id="chunk512o64",
    chunk_method="window",
    chunk_size=512,
    chunk_overlap=64,
    embedding_model="HashingEmbedder",
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

CHUNK_SENT = ExperimentConfig(
    experiment_id="chunk_sent",
    chunk_method="sentence",
    chunk_size=512,
    chunk_overlap=0,
    embedding_model="HashingEmbedder",
    retrieval_method="bm25",
    top_k=5,
    threshold=None,
    reranker="none",
    retrieve_k=5,
    rerank_k=5,
    query_strategy="original",
    llm=_llm,
    temperature=0.0,
    prompt_version="baseline",
    input_per_million=_in,
    output_per_million=_out,
)

_REGISTRY = {
    BASELINE.experiment_id: BASELINE,
    BM25.experiment_id: BM25,
    HYBRID.experiment_id: HYBRID,
    HYBRID_GATED.experiment_id: HYBRID_GATED,
    HYBRID_HINT.experiment_id: HYBRID_HINT,
    HYBRID_ORACLE.experiment_id: HYBRID_ORACLE,
    HYBRID_BM25W.experiment_id: HYBRID_BM25W,
    HYBRID_DENSEW.experiment_id: HYBRID_DENSEW,
    HYBRID_MQ.experiment_id: HYBRID_MQ,
    HYBRID_EXPAND.experiment_id: HYBRID_EXPAND,
    DENSE_HASH.experiment_id: DENSE_HASH,
    HYBRID_REV.experiment_id: HYBRID_REV,
    HYBRID_LLM.experiment_id: HYBRID_LLM,
    HYBRID_TEMP02.experiment_id: HYBRID_TEMP02,
    HYBRID_TEMP07.experiment_id: HYBRID_TEMP07,
    HYBRID_PROMPT_STRICT.experiment_id: HYBRID_PROMPT_STRICT,
    HYBRID_PROMPT_CITE.experiment_id: HYBRID_PROMPT_CITE,
    HYBRID_LLM_LARGE.experiment_id: HYBRID_LLM_LARGE,
    HYBRID_HYDE.experiment_id: HYBRID_HYDE,
    HYBRID_REWRITE.experiment_id: HYBRID_REWRITE,
    CHUNK256.experiment_id: CHUNK256,
    CHUNK512.experiment_id: CHUNK512,
    CHUNK1024.experiment_id: CHUNK1024,
    CHUNK512O64.experiment_id: CHUNK512O64,
    CHUNK_SENT.experiment_id: CHUNK_SENT,
    RR_10_5.experiment_id: RR_10_5,
    RR_20_5.experiment_id: RR_20_5,
    PRODUCTION.experiment_id: PRODUCTION,
}


def get_experiment(name: str) -> ExperimentConfig:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown experiment {name!r}; known: {known}") from exc


def list_experiments() -> list[str]:
    return sorted(_REGISTRY)
