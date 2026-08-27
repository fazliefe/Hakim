"""One 16:9 presentation slide: six must-have RAG benches."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUT = ROOT / "slides"

BG = "#F4F0E8"
INK = "#1A2330"
NAVY = "#15233A"
GOLD = "#C4A35A"
TEAL = "#1A7A6D"
MUTED = "#6A7684"
LINE = "#E2D9CB"
WHITE = "#FFFDF8"
SLATE = "#8A94A0"
CORAL = "#C45C4A"


def load(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))


def r(name: str, key: str = "Recall@5") -> float:
    return float(load(name)[key])


def font_name() -> str:
    for name in ("Segoe UI", "Calibri", "Arial"):
        for path in font_manager.findSystemFonts():
            if name.lower() in Path(path).stem.lower().replace("-", " "):
                return font_manager.FontProperties(fname=path).get_name()
    return "DejaVu Sans"


def card(ax, title: str, metric: str) -> None:
    ax.set_facecolor(WHITE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, loc="left", fontsize=13.5, color=NAVY, fontweight="bold", pad=14)
    ax.text(1.0, 1.04, metric, transform=ax.transAxes, ha="right", va="bottom", fontsize=9.5, color=MUTED)


def bars(ax, pairs: list[tuple[str, float]], *, winner: int = 0, extra: list[str] | None = None, coral: int | None = None) -> None:
    ax.tick_params(length=0, labelsize=9, colors=MUTED)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=LINE, linewidth=0.7)
    n = len(pairs)
    y = np.arange(n)
    vals = [p[1] for p in pairs]
    cols = []
    for i in range(n):
        if coral is not None and i == coral:
            cols.append(CORAL)
        elif i == winner:
            cols.append(TEAL)
        else:
            cols.append(SLATE)
    ax.barh(y, vals, color=cols, height=0.58, zorder=3)
    ax.set_yticks([])
    ax.set_ylim(-0.55, n - 0.45)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.22)
    ax.set_xticks([0, 0.5, 1.0])
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.spines["bottom"].set_color(LINE)
    ax.spines["left"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for i, (lab, val) in enumerate(pairs):
        ax.text(-0.02, i, lab, ha="right", va="center", fontsize=11, color=INK, transform=ax.get_yaxis_transform(), clip_on=False)
        right = extra[i] if extra else f"{val * 100:.1f}"
        ax.text(min(val + 0.03, 1.14), i, right, va="center", fontsize=11.5, color=INK, fontweight="bold")


def slide() -> Path:
    fig = plt.figure(figsize=(19.2, 10.8), dpi=170, facecolor=BG)
    fig.add_artist(Rectangle((0, 0), 0.006, 1, transform=fig.transFigure, color=GOLD, zorder=10))
    fig.add_artist(Rectangle((0, 0.932), 1, 0.068, transform=fig.transFigure, color=NAVY, zorder=8))

    fig.text(0.028, 0.966, "HAKIM", fontsize=13, color=GOLD, fontweight="bold", transform=fig.transFigure, va="center")
    fig.text(0.078, 0.966, "RAG Benchmark", fontsize=13, color="white", transform=fig.transFigure, va="center")
    fig.text(0.972, 0.966, "TEKNOFEST  2026", fontsize=11, color="#C9D3DE", ha="right", transform=fig.transFigure, va="center")

    gs = GridSpec(2, 3, figure=fig, left=0.11, right=0.97, top=0.86, bottom=0.08, hspace=0.42, wspace=0.38)

    # 1 Search
    ax = fig.add_subplot(gs[0, 0])
    card(ax, "1  Retrieval", "R@5   n=400")
    bars(
        ax,
        [
            ("Hybrid", r("hybrid")),
            ("BM25", r("bm25")),
            ("Dense", r("baseline")),
        ],
        winner=0,
    )

    # 2 Rerank: quality vs time
    ax = fig.add_subplot(gs[0, 1])
    card(ax, "2  Reranker", "R@5 vs latency")
    bars(
        ax,
        [
            ("Hybrid", r("hybrid")),
            ("Hybrid + CE", r("production")),
        ],
        winner=0,
        extra=[
            f"{r('hybrid') * 100:.1f}   {load('hybrid')['p50_latency']:.0f} ms",
            f"{r('production') * 100:.1f}   {load('production')['p50_latency'] / 1000:.1f} s",
        ],
    )

    # 3 Chunking (same retriever family: BM25 article vs windows)
    ax = fig.add_subplot(gs[0, 2])
    card(ax, "3  Chunking", "R@5   n=400")
    bars(
        ax,
        [
            ("Article", r("bm25")),
            ("1024 tok", r("chunk1024")),
            ("512 tok", r("chunk512")),
            ("256 tok", r("chunk256")),
        ],
        winner=0,
    )

    # 4 Answer
    ax = fig.add_subplot(gs[1, 0])
    card(ax, "4  Answer", "correct   n=50")
    bars(
        ax,
        [
            ("Cite prompt", r("hybrid_prompt_cite", "Answer Correctness")),
            ("llm-large", r("hybrid_llm_large", "Answer Correctness")),
            ("llm-fast", r("hybrid_llm", "Answer Correctness")),
            ("Extractive", r("hybrid", "Answer Correctness")),
        ],
        winner=0,
        coral=3,
    )

    # 5 Rewrite
    ax = fig.add_subplot(gs[1, 1])
    card(ax, "5  Query rewrite", "R@5   n=50")
    bars(
        ax,
        [
            ("Original", r("hybrid_llm")),
            ("HyDE", r("hybrid_hyde")),
            ("Rewrite", r("hybrid_rewrite")),
        ],
        winner=0,
        coral=2,
    )

    # 6 Citations
    ax = fig.add_subplot(gs[1, 2])
    card(ax, "6  Citations", "precision   n=50")
    bars(
        ax,
        [
            ("Cite prompt", r("hybrid_prompt_cite", "Citation Precision")),
            ("llm-large", r("hybrid_llm_large", "Citation Precision")),
            ("llm-fast", r("hybrid_llm", "Citation Precision")),
        ],
        winner=0,
    )

    fig.text(
        0.028,
        0.032,
        "gold set  ·  article chunks  ·  ES hybrid RRF k=60  ·  teal = selected  ·  red = rejected",
        fontsize=10.5,
        color=MUTED,
        transform=fig.transFigure,
    )

    path = OUT / "01_arama.jpg"
    fig.savefig(path, format="jpeg", dpi=170, facecolor=BG, pil_kwargs={"quality": 95})
    plt.close(fig)
    return path


def main() -> None:
    plt.rcParams["font.family"] = font_name()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    print(slide())


if __name__ == "__main__":
    main()
