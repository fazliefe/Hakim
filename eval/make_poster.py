"""Single-page poster of every HÂKİM RAG benchmark so far."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUT = ROOT / "slides"

NAVY = "#071526"
CARD = "#0E2A4A"
GOLD = "#F0C14B"
TEAL = "#2EC4B6"
CORAL = "#FF6B6B"
BLUE = "#5B9DFF"
LILAC = "#B8A4FF"
WHITE = "#F4F7FB"
MUTED = "#9BB0C9"
GREEN = "#3DDC97"
ORANGE = "#FF9F43"
EDGE = "#1C3F66"


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _font_name() -> str | None:
    for name in ("Segoe UI", "Calibri", "Arial"):
        for path in font_manager.findSystemFonts():
            if name.lower() in Path(path).stem.lower().replace("-", " "):
                return font_manager.FontProperties(fname=path).get_name()
    return None


def style_ax(ax) -> None:
    ax.set_facecolor(CARD)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color="#163554", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(EDGE)
    ax.spines["bottom"].set_color(EDGE)


def title_ax(ax, text: str) -> None:
    ax.set_title(text, color=WHITE, fontsize=11, fontweight="bold", loc="left", pad=6)


def barh(ax, labels, values, colors) -> None:
    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=colors, height=0.64, zorder=3)
    ax.set_yticks(y, labels, fontsize=8, color=WHITE)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.12)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    for bar, val in zip(bars, values):
        ax.text(
            min(val + 0.02, 1.0),
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0%}",
            va="center",
            color=WHITE,
            fontsize=8,
            fontweight="bold",
        )


def grouped(ax, labels, series: dict[str, list[float]], colors: list[str]) -> None:
    x = np.arange(len(labels))
    n = len(series)
    width = 0.78 / n
    for i, (name, vals) in enumerate(series.items()):
        offset = (i - (n - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=name, color=colors[i % len(colors)], zorder=3)
    ax.set_xticks(x, labels, fontsize=7.5, color=WHITE)
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend(frameon=False, loc="upper right", fontsize=7, labelcolor=WHITE)


def kpi(ax, value: str, label: str, color: str) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0.04, 0.08),
            0.92,
            0.84,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=CARD,
            edgecolor=color,
            linewidth=1.6,
            transform=ax.transAxes,
        )
    )
    ax.text(0.5, 0.58, value, ha="center", va="center", fontsize=20, fontweight="bold", color=color)
    ax.text(0.5, 0.22, label, ha="center", va="center", fontsize=8, color=MUTED)


def main() -> None:
    name = _font_name()
    plt.rcParams.update(
        {
            "figure.facecolor": NAVY,
            "axes.facecolor": CARD,
            "text.color": WHITE,
            "axes.labelcolor": WHITE,
            "savefig.facecolor": NAVY,
        }
    )
    if name:
        plt.rcParams["font.family"] = name

    hybrid = load("hybrid.json")
    bm25 = load("bm25.json")
    dense = load("baseline.json")
    prod = load("production.json")
    llm = load("hybrid_llm.json")
    cite = load("hybrid_prompt_cite.json")
    large = load("hybrid_llm_large.json")
    hyde = load("hybrid_hyde.json")
    rewrite = load("hybrid_rewrite.json")
    board = json.loads((RESULTS / "leaderboard.json").read_text(encoding="utf-8"))

    fig = plt.figure(figsize=(28, 16), dpi=130)
    gs = GridSpec(
        4,
        4,
        figure=fig,
        height_ratios=[0.72, 1.35, 1.35, 1.45],
        hspace=0.38,
        wspace=0.28,
        left=0.04,
        right=0.98,
        top=0.90,
        bottom=0.05,
    )

    fig.text(
        0.04,
        0.96,
        "HÂKİM RAG Benchmark  ·  tüm deneyler tek bakış",
        fontsize=26,
        fontweight="bold",
        color=WHITE,
    )
    fig.text(
        0.04,
        0.925,
        "Retrieval: 400 soru, madde chunk, extractive   ·   LLM: aynı 50 soruluk stratified set, Evren API",
        fontsize=11,
        color=MUTED,
    )
    fig.text(
        0.98,
        0.96,
        "TEKNOFEST 2026",
        fontsize=12,
        color=GOLD,
        ha="right",
        fontweight="bold",
    )

    kpi(fig.add_subplot(gs[0, 0]), f"{hybrid['Recall@5']:.0%}", "Hybrid R@5  ·  kazanan arama", TEAL)
    kpi(fig.add_subplot(gs[0, 1]), f"{cite['Answer Correctness']:.0%}", "Cite prompt  ·  cevap correctness", GOLD)
    kpi(fig.add_subplot(gs[0, 2]), "100%", "LLM unanswerable  ·  doğru refuse", GREEN)
    kpi(fig.add_subplot(gs[0, 3]), f"{hybrid['p50_latency']:.0f} ms", "Hybrid p50  ·  CE ~3 s", BLUE)

    ax = fig.add_subplot(gs[1, 0])
    style_ax(ax)
    title_ax(ax, "Arama  ·  Recall@5")
    barh(
        ax,
        ["Dense (Mursit)", "BM25", "Hybrid RRF", "Hybrid + CE"],
        [dense["Recall@5"], bm25["Recall@5"], hybrid["Recall@5"], prod["Recall@5"]],
        [CORAL, GOLD, TEAL, BLUE],
    )

    ax = fig.add_subplot(gs[1, 1])
    style_ax(ax)
    title_ax(ax, "Chunking  ·  Recall@5")
    barh(
        ax,
        ["Madde (article)", "1024 token", "512 token", "512+64", "Cümle", "256 token"],
        [
            bm25["Recall@5"],
            load("chunk1024.json")["Recall@5"],
            load("chunk512.json")["Recall@5"],
            load("chunk512o64.json")["Recall@5"],
            load("chunk_sent.json")["Recall@5"],
            load("chunk256.json")["Recall@5"],
        ],
        [TEAL, BLUE, GOLD, LILAC, ORANGE, CORAL],
    )

    ax = fig.add_subplot(gs[1, 2])
    style_ax(ax)
    title_ax(ax, "Sorgu stratejisi  ·  Recall@5")
    barh(
        ax,
        ["Oracle kanun", "Multi-query", "Kanun hint", "Hybrid", "Expand", "BM25 ağır", "Dense ağır"],
        [
            load("hybrid_oracle.json")["Recall@5"],
            load("hybrid_mq.json")["Recall@5"],
            load("hybrid_hint.json")["Recall@5"],
            hybrid["Recall@5"],
            load("hybrid_expand.json")["Recall@5"],
            load("hybrid_bm25w.json")["Recall@5"],
            load("hybrid_densew.json")["Recall@5"],
        ],
        [TEAL, GREEN, GOLD, BLUE, LILAC, ORANGE, CORAL],
    )

    ax = fig.add_subplot(gs[1, 3])
    style_ax(ax)
    title_ax(ax, "Gecikme p50  (log ms)")
    labels = ["BM25", "Dense", "Hybrid", "CE 10→5", "CE 20→5", "CE 50→12"]
    vals = [
        bm25["p50_latency"],
        dense["p50_latency"],
        hybrid["p50_latency"],
        load("rr_10_5.json")["p50_latency"],
        load("rr_20_5.json")["p50_latency"],
        prod["p50_latency"],
    ]
    colors = [GOLD, CORAL, TEAL, BLUE, LILAC, "#FF4D6D"]
    x = np.arange(len(labels))
    bars = ax.bar(x, vals, color=colors, width=0.62, zorder=3)
    ax.set_xticks(x, labels, fontsize=7.5, color=WHITE)
    ax.set_yscale("log")
    ax.set_ylabel("ms", color=MUTED, fontsize=8)
    for bar, val in zip(bars, vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val * 1.15,
            f"{val:.0f}",
            ha="center",
            va="bottom",
            color=WHITE,
            fontsize=7,
            fontweight="bold",
        )

    ax = fig.add_subplot(gs[2, 0])
    style_ax(ax)
    title_ax(ax, "Hybrid  ·  soru tipi R@5")
    by = hybrid["metrics_by_question_type"]
    order = [
        ("keyword", "Keyword"),
        ("factual", "Factual"),
        ("semantic", "Semantic"),
        ("multi_hop", "Multi-hop"),
        ("comparison", "Comparison"),
        ("ambiguous", "Ambiguous"),
        ("typo", "Typo"),
        ("aggregation", "Aggregation"),
    ]
    vals = [by[k]["Recall@5"] for k, _ in order]
    colors = [TEAL if v >= 0.8 else GOLD if v >= 0.6 else CORAL for v in vals]
    barh(ax, [lab for _, lab in order], vals, colors)

    ax = fig.add_subplot(gs[2, 1])
    style_ax(ax)
    title_ax(ax, "Top-K  ·  hybrid havuz 50")
    ks = [int(row["k"]) for row in board["topk_hybrid"]]
    rec = [row["Recall@K"] for row in board["topk_hybrid"]]
    ax.plot(ks, rec, color=TEAL, linewidth=2.4, marker="o", markersize=6, zorder=4)
    ax.scatter([5], [rec[ks.index(5)]], s=90, color=GOLD, zorder=5)
    ax.set_xticks(ks)
    ax.set_ylim(0.52, 0.94)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_xlabel("K", color=MUTED, fontsize=8)
    for k, r in zip(ks, rec):
        ax.annotate(f"{r:.0%}", (k, r), xytext=(0, 7), textcoords="offset points", ha="center", color=WHITE, fontsize=7)

    ax = fig.add_subplot(gs[2, 2])
    style_ax(ax)
    title_ax(ax, "Reranker  ·  R@5 vs R@1")
    grouped(
        ax,
        ["CE yok", "10→5", "20→5", "50→12"],
        {
            "Recall@5": [
                hybrid["Recall@5"],
                load("rr_10_5.json")["Recall@5"],
                load("rr_20_5.json")["Recall@5"],
                prod["Recall@5"],
            ],
            "Recall@1": [
                hybrid["Recall@1"],
                load("rr_10_5.json")["Recall@1"],
                load("rr_20_5.json")["Recall@1"],
                prod["Recall@1"],
            ],
        },
        [TEAL, GOLD],
    )

    ax = fig.add_subplot(gs[2, 3])
    style_ax(ax)
    title_ax(ax, "Aggregation R@5  ·  multi-query")
    agg = [
        hybrid["metrics_by_question_type"]["aggregation"]["Recall@5"],
        load("hybrid_expand.json")["metrics_by_question_type"]["aggregation"]["Recall@5"],
        load("hybrid_mq.json")["metrics_by_question_type"]["aggregation"]["Recall@5"],
    ]
    x = np.arange(3)
    bars = ax.bar(x, agg, color=[BLUE, LILAC, TEAL], width=0.5, zorder=3)
    ax.set_xticks(x, ["Hybrid", "Expand", "Multi-query"], fontsize=8, color=WHITE)
    ax.set_ylim(0, 0.7)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    for bar, val in zip(bars, agg):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.0%}", ha="center", color=WHITE, fontsize=10, fontweight="bold")

    ax = fig.add_subplot(gs[3, 0])
    style_ax(ax)
    title_ax(ax, "LLM  ·  correctness vs hallucination")
    rows = [
        ("Cite", cite),
        ("large", large),
        ("HyDE", hyde),
        ("t=0.2", load("hybrid_temp02.json")),
        ("fast", llm),
        ("t=0.7", load("hybrid_temp07.json")),
        ("strict", load("hybrid_prompt_strict.json")),
        ("rewrite", rewrite),
    ]
    grouped(
        ax,
        [a for a, _ in rows],
        {
            "Correctness": [b["Answer Correctness"] for _, b in rows],
            "Hallucination": [b["Hallucination Rate"] for _, b in rows],
        },
        [TEAL, CORAL],
    )

    ax = fig.add_subplot(gs[3, 1])
    style_ax(ax)
    title_ax(ax, "LLM  ·  soru tipi correctness")
    lby = llm["metrics_by_question_type"]
    lord = [
        ("typo", "Typo"),
        ("keyword", "Keyword"),
        ("factual", "Factual"),
        ("comparison", "Cmp"),
        ("semantic", "Sem"),
        ("unanswerable", "Una"),
        ("multi_hop", "Hop"),
        ("aggregation", "Agg"),
        ("ambiguous", "Amb"),
    ]
    lvals = [lby[k]["Answer Correctness"] for k, _ in lord]
    barh(ax, [lab for _, lab in lord], lvals, [TEAL if v >= 0.75 else GOLD if v >= 0.4 else CORAL for v in lvals])

    ax = fig.add_subplot(gs[3, 2])
    style_ax(ax)
    title_ax(ax, "HyDE / rewrite  ·  kullanma")
    grouped(
        ax,
        ["Orijinal", "HyDE", "Rewrite"],
        {
            "Recall@5": [llm["Recall@5"], hyde["Recall@5"], rewrite["Recall@5"]],
            "Correctness": [llm["Answer Correctness"], hyde["Answer Correctness"], rewrite["Answer Correctness"]],
        },
        [TEAL, GOLD],
    )

    ax = fig.add_subplot(gs[3, 3])
    ax.set_facecolor(CARD)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    title_ax(ax, "Karar  ·  production yığını")
    en = load("lang_en.json")["Recall@5"]
    lines = [
        (TEAL, f"Madde chunk  ·  pencere max {load('chunk1024.json')['Recall@5']:.0%} < madde {bm25['Recall@5']:.0%}"),
        (GOLD, f"Hybrid RRF, CE kapalı  ·  dense kapı 0.70"),
        (BLUE, f"Kanun hint + aggregation MQ  ·  üret K=5 / havuz 50"),
        (GREEN, f"Cite prompt + llm-large  ·  refuse {llm['correct_refusal']:.0%}"),
        (CORAL, f"Yapma: HyDE, rewrite ({rewrite['Recall@5']:.0%} R@5), EN ({en:.0%})"),
        (LILAC, "Sonraki: UI kanun seçici, cite+large, aggregation graf"),
    ]
    for i, (color, text) in enumerate(lines):
        y = 0.82 - i * 0.14
        ax.add_patch(
            FancyBboxPatch(
                (0.02, y - 0.04),
                0.96,
                0.12,
                boxstyle="round,pad=0.01,rounding_size=0.03",
                facecolor="#102F52",
                edgecolor=color,
                linewidth=1.2,
                transform=ax.transAxes,
            )
        )
        ax.text(0.06, y + 0.02, text, transform=ax.transAxes, fontsize=8.2, color=WHITE, va="center")

    fig.text(
        0.04,
        0.018,
        "HÂKİM  ·  TEKNOFEST 2026  ·  kaynak: eval/results/*.json",
        fontsize=9,
        color=MUTED,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "00_tum_benchmark.jpg"
    fig.savefig(path, format="jpeg", dpi=140, pil_kwargs={"quality": 93})
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
