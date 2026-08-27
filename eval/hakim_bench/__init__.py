"""HÂKİM RAG benchmark harness (Faz 0–1)."""

from hakim_bench.dataset import load_dataset
from hakim_bench.experiments import BASELINE, get_experiment
from hakim_bench.runner import run_experiment
from hakim_bench.schema import GoldQuestion

__all__ = [
    "BASELINE",
    "GoldQuestion",
    "get_experiment",
    "load_dataset",
    "run_experiment",
]
