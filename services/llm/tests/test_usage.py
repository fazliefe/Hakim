from llm.usage import (
    LlmUsage,
    add_usage,
    estimate_cost,
    parse_usage,
    peek_usage,
    reset_usage,
    take_usage,
    usage_totals,
)


def test_estimate_cost_groq_gpt_oss_20b() -> None:
    cost = estimate_cost(1_000_000, 1_000_000, input_per_million=0.075, output_per_million=0.30)
    assert abs(cost - 0.375) < 1e-9


def test_estimate_cost_zero_tokens() -> None:
    assert estimate_cost(0, 0) == 0.0


def test_parse_usage_from_openai_shape() -> None:
    usage = parse_usage(
        {"usage": {"prompt_tokens": 80, "completion_tokens": 20}, "model": "openai/gpt-oss-20b"}
    )
    assert usage.prompt_tokens == 80
    assert usage.completion_tokens == 20
    assert usage.total_tokens == 100
    assert usage.model == "openai/gpt-oss-20b"


def test_parse_usage_missing_is_zero() -> None:
    usage = parse_usage({})
    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0


def test_parse_usage_from_groq_x_groq() -> None:
    usage = parse_usage(
        {"x_groq": {"usage": {"prompt_tokens": 12, "completion_tokens": 4}}, "model": "openai/gpt-oss-20b"}
    )
    assert usage.prompt_tokens == 12
    assert usage.completion_tokens == 4
    assert usage.model == "openai/gpt-oss-20b"


def test_usage_context_accumulates_and_resets() -> None:
    reset_usage()
    add_usage(LlmUsage(prompt_tokens=10, completion_tokens=2, model="m"))
    add_usage(LlmUsage(prompt_tokens=5, completion_tokens=3, model="m"))
    peeked = peek_usage()
    assert peeked.prompt_tokens == 15
    assert peeked.completion_tokens == 5
    taken = take_usage()
    assert taken.prompt_tokens == 15
    assert peek_usage().prompt_tokens == 0


def test_usage_survives_copied_context() -> None:
    """Langfuse/OTel attach a copied context around the Groq call; tokens must still be readable after it exits."""
    import contextvars

    reset_usage()

    def record() -> None:
        add_usage(LlmUsage(prompt_tokens=80, completion_tokens=20, model="openai/gpt-oss-20b"))

    contextvars.copy_context().run(record)
    taken = take_usage()
    assert taken.prompt_tokens == 80
    assert taken.completion_tokens == 20
    assert taken.model == "openai/gpt-oss-20b"


def test_usage_survives_worker_thread() -> None:
    import threading

    reset_usage()

    def record() -> None:
        add_usage(LlmUsage(prompt_tokens=80, completion_tokens=20, model="openai/gpt-oss-20b"))

    worker = threading.Thread(target=record)
    worker.start()
    worker.join()
    taken = take_usage()
    assert taken.prompt_tokens == 80
    assert taken.completion_tokens == 20


def test_parse_usage_from_ollama_eval_counts() -> None:
    usage = parse_usage({"prompt_eval_count": 30, "eval_count": 9, "model": "llama3.2:3b"})
    assert usage.prompt_tokens == 30
    assert usage.completion_tokens == 9
    assert usage.model == "llama3.2:3b"


def test_usage_totals_shape_matches_research_observability() -> None:
    """Madde B: /v1/evrak, /v1/işlem, /v1/senaryo da /v1/arastirma ile aynı
    observability.totals şeklini üretmeli — frontend Observability tipi tek."""
    totals = usage_totals(LlmUsage(prompt_tokens=100, completion_tokens=50))
    assert set(totals) == {"prompt_tokens", "completion_tokens", "cost_usd", "provider", "model", "model_label"}
    assert totals["prompt_tokens"] == 100
    assert totals["completion_tokens"] == 50


def test_usage_totals_zero_when_no_llm_call_happened() -> None:
    totals = usage_totals(LlmUsage())
    assert totals["cost_usd"] == 0.0
    assert totals["prompt_tokens"] == 0
