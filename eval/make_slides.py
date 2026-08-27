"""Presentation JPGs from eval/results JSON. 16:9, Turkish labels."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib import font_manager

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

PALETTE = [TEAL, GOLD, BLUE, CORAL, LILAC, GREEN, ORANGE, "#7FDBDA"]


def _font() -> str:
    for name in ("Segoe UI", "Calibri", "Arial"):
        matches = font_manager.findSystemFonts()
        for path in matches:
            try:
                if name.lower() in Path(path).stem.lower().replace("-", " "):
                    return path
            except Exception:
                continue
    return ""


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def setup() -> None:
    path = _font()
    plt.rcParams.update(
        {
            "figure.facecolor": NAVY,
            "axes.facecolor": CARD,
            "axes.edgecolor": "#1C3F66",
            "axes.labelcolor": WHITE,
            "text.color": WHITE,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.grid": True,
            "grid.color": "#163554",
            "grid.linestyle": "-",
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "font.size": 13,
            "axes.titlesize": 22,
            "axes.titleweight": "bold",
            "figure.dpi": 140,
            "savefig.dpi": 160,
            "savefig.facecolor": NAVY,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.28,
        }
    )
    if path:
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=path).get_name()


def new_fig(title: str, subtitle: str):
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.suptitle(title, color=WHITE, fontsize=26, fontweight="bold", y=0.97)
    ax.set_title(subtitle, color=MUTED, fontsize=14, pad=12, loc="left")
    ax.text(
        0.99,
        -0.12,
        "HÂKİM  ·  TEKNOFEST 2026  ·  RAG Benchmark",
        transform=ax.transAxes,
        ha="right",
        color=MUTED,
        fontsize=10,
    )
    return fig, ax


def save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, format="jpeg", pil_kwargs={"quality": 92})
    plt.close(fig)
    return path


def barh(ax, labels, values, colors, fmt="{:.0%}"):
    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=colors, height=0.62, zorder=3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(1.0, max(values) * 1.18))
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    for bar, val in zip(bars, values):
        ax.text(
            val + 0.015,
            bar.get_y() + bar.get_height() / 2,
            fmt.format(val),
            va="center",
            color=WHITE,
            fontsize=13,
            fontweight="bold",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#1C3F66")
    ax.spines["bottom"].set_color("#1C3F66")
    return bars


def grouped_bars(ax, labels, series: dict[str, list[float]]):
    x = np.arange(len(labels))
    n = len(series)
    width = 0.78 / n
    for i, (name, vals) in enumerate(series.items()):
        offset = (i - (n - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=name, color=PALETTE[i % len(PALETTE)], zorder=3)
    ax.set_xticks(x, labels, rotation=0)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylim(0, 1.08)
    ax.legend(frameon=False, loc="upper right", labelcolor=WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def slide_retrieval() -> None:
    fig, ax = new_fig(
        "Arama yöntemi  ·  Recall@5",
        "400 soru  ·  madde bazlı chunk  ·  extractive  ·  kazanan: Hybrid RRF (CE kapalı)",
    )
    labels = ["Dense\n(Mursit)", "BM25", "Hybrid RRF\nCE yok", "Hybrid + CE\n50→12"]
    values = [
        load("baseline.json")["Recall@5"],
        load("bm25.json")["Recall@5"],
        load("hybrid.json")["Recall@5"],
        load("production.json")["Recall@5"],
    ]
    barh(ax, labels, values, [CORAL, GOLD, TEAL, BLUE])
    ax.set_xlabel("Recall@5")
    save(fig, "01_arama_yontemi.jpg")


def slide_latency() -> None:
    fig, ax = new_fig(
        "Gecikme  ·  p50 (ms)",
        "Aynı 400 soru  ·  CE production yolunu ~22× yavaşlatıyor",
    )
    labels = ["BM25", "Dense", "Hybrid\nCE yok", "CE 10→5", "CE 20→5", "CE 50→12"]
    values = [
        load("bm25.json")["p50_latency"],
        load("baseline.json")["p50_latency"],
        load("hybrid.json")["p50_latency"],
        load("rr_10_5.json")["p50_latency"],
        load("rr_20_5.json")["p50_latency"],
        load("production.json")["p50_latency"],
    ]
    colors = [GOLD, CORAL, TEAL, BLUE, LILAC, "#FF4D6D"]
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.62, zorder=3)
    ax.set_xticks(x, labels)
    ax.set_ylabel("p50 gecikme (ms)")
    ax.set_yscale("log")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val * 1.12,
            f"{val:.0f} ms",
            ha="center",
            va="bottom",
            color=WHITE,
            fontsize=12,
            fontweight="bold",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "02_gecikme.jpg")


def slide_chunking() -> None:
    fig, ax = new_fig(
        "Chunking  ·  Recall@5",
        "Pencere boyutu madde bazlı chunking'i geçemedi  ·  BM25 laboratuvar index'leri",
    )
    labels = ["Madde\n(article)", "1024 token", "512 token", "512 + 64\noverlap", "Cümle", "256 token"]
    values = [
        load("bm25.json")["Recall@5"],
        load("chunk1024.json")["Recall@5"],
        load("chunk512.json")["Recall@5"],
        load("chunk512o64.json")["Recall@5"],
        load("chunk_sent.json")["Recall@5"],
        load("chunk256.json")["Recall@5"],
    ]
    barh(ax, labels, values, [TEAL, BLUE, GOLD, LILAC, ORANGE, CORAL])
    ax.set_xlabel("Recall@5")
    save(fig, "03_chunking.jpg")


def slide_query() -> None:
    fig, ax = new_fig(
        "Sorgu stratejileri  ·  Recall@5",
        "400 soru  ·  hybrid RRF  ·  UI kanun seçici = oracle tavanı",
    )
    labels = [
        "Oracle kanun",
        "Multi-query",
        "Kanun hint",
        "Hybrid",
        "Eşanlamlı expand",
        "BM25 ağır 0.8",
        "Dense ağır 0.8",
    ]
    values = [
        load("hybrid_oracle.json")["Recall@5"],
        load("hybrid_mq.json")["Recall@5"],
        load("hybrid_hint.json")["Recall@5"],
        load("hybrid.json")["Recall@5"],
        load("hybrid_expand.json")["Recall@5"],
        load("hybrid_bm25w.json")["Recall@5"],
        load("hybrid_densew.json")["Recall@5"],
    ]
    barh(ax, labels, values, [TEAL, GREEN, GOLD, BLUE, LILAC, ORANGE, CORAL])
    ax.set_xlabel("Recall@5")
    save(fig, "04_sorgu_stratejisi.jpg")


def slide_aggregation() -> None:
    fig, ax = new_fig(
        "Aggregation soruları  ·  Recall@5",
        "\"Hangileri / listesi\"  ·  lexical multi-query 0.31 → 0.51",
    )
    labels = ["Hybrid\n(tek sorgu)", "Eşanlamlı\nexpand", "Multi-query"]
    values = [
        load("hybrid.json")["metrics_by_question_type"]["aggregation"]["Recall@5"],
        load("hybrid_expand.json")["metrics_by_question_type"]["aggregation"]["Recall@5"],
        load("hybrid_mq.json")["metrics_by_question_type"]["aggregation"]["Recall@5"],
    ]
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=[BLUE, LILAC, TEAL], width=0.5, zorder=3)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 0.7)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel("Recall@5")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.02,
            f"{val:.0%}",
            ha="center",
            color=WHITE,
            fontsize=18,
            fontweight="bold",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "05_aggregation.jpg")


def slide_topk() -> None:
    fig, ax = new_fig(
        "Top-K  ·  hybrid havuz 50",
        "Üretim için K=5  ·  arama havuzu 50  ·  K=1 kaçırıyor, K=50 marjinal",
    )
    board = json.loads((RESULTS / "leaderboard.json").read_text(encoding="utf-8"))
    ks = [int(row["k"]) for row in board["topk_hybrid"]]
    rec = [row["Recall@K"] for row in board["topk_hybrid"]]
    ax.plot(ks, rec, color=TEAL, linewidth=3.2, marker="o", markersize=10, zorder=4)
    highlight = {5: GOLD}
    for k, r in zip(ks, rec):
        color = highlight.get(k, WHITE)
        ax.scatter([k], [r], s=160 if k == 5 else 80, color=color, zorder=5)
        ax.annotate(
            f"{r:.0%}",
            (k, r),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            color=color,
            fontsize=13,
            fontweight="bold",
        )
    ax.set_xlabel("K (üretime verilen madde sayısı)")
    ax.set_ylabel("Recall@K")
    ax.set_xticks(ks)
    ax.set_ylim(0.5, 0.95)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "06_topk.jpg")


def slide_by_type() -> None:
    fig, ax = new_fig(
        "Soru tipi  ·  Hybrid RRF  ·  Recall@5",
        "400 soru  ·  zayıf: aggregation / comparison  ·  unanswerable extractive refuse etmiyor",
    )
    by = load("hybrid.json")["metrics_by_question_type"]
    order = [
        ("keyword", "Keyword"),
        ("factual", "Factual"),
        ("semantic", "Semantic"),
        ("multi_hop", "Multi-hop"),
        ("comparison", "Comparison"),
        ("ambiguous", "Ambiguous"),
        ("typo", "Typo"),
        ("aggregation", "Aggregation"),
        ("unanswerable", "Unanswerable*"),
    ]
    labels = [lab for _, lab in order]
    values = [by[key]["Recall@5"] if key != "unanswerable" else by[key].get("correct_refusal", 0.0) for key, _ in order]
    # unanswerable Recall@5 is null-ish; use correct_refusal from summarize
    una = load("hybrid.json")
    una_ref = una.get("correct_refusal")
    if una_ref is None:
        una_ref = una["metrics_by_question_type"]["unanswerable"].get("correct_refusal") or 0.0
    values[-1] = float(una_ref or 0.0)
    colors = [TEAL if v >= 0.8 else GOLD if v >= 0.6 else CORAL for v in values]
    barh(ax, labels, values, colors)
    ax.set_xlabel("Recall@5  (*unanswerable = doğru refuse)")
    save(fig, "07_soru_tipi.jpg")


def slide_reranker() -> None:
    fig, ax = new_fig(
        "Cross-encoder reranker",
        "R@5 neredeyse aynı  ·  typo kazanıyor, comparison kaybediyor  ·  varsayılan KAPALI",
    )
    labels = ["Hybrid\nCE yok", "CE 10→5", "CE 20→5", "CE 50→12"]
    files = ["hybrid.json", "rr_10_5.json", "rr_20_5.json", "production.json"]
    r5 = [load(f)["Recall@5"] for f in files]
    r1 = [load(f)["Recall@1"] for f in files]
    grouped_bars(ax, labels, {"Recall@5": r5, "Recall@1": r1})
    ax.set_ylabel("Skor")
    save(fig, "08_reranker.jpg")


def slide_llm_quality() -> None:
    fig, ax = new_fig(
        "LLM cevap kalitesi  ·  50 soru",
        "Madde-eşleşmeli correctness  ·  extractive ~0.04 sinyal değildi  ·  refuse %100",
    )
    rows = [
        ("Cite prompt", "hybrid_prompt_cite.json"),
        ("llm-large", "hybrid_llm_large.json"),
        ("HyDE", "hybrid_hyde.json"),
        ("temp 0.2", "hybrid_temp02.json"),
        ("llm-fast  temp 0", "hybrid_llm.json"),
        ("temp 0.7", "hybrid_temp07.json"),
        ("Strict prompt", "hybrid_prompt_strict.json"),
        ("Query rewrite", "hybrid_rewrite.json"),
    ]
    labels = [a for a, _ in rows]
    corr = [load(b)["Answer Correctness"] for _, b in rows]
    hallu = [load(b)["Hallucination Rate"] for _, b in rows]
    grouped_bars(ax, labels, {"Correctness": corr, "Hallucination": hallu})
    ax.tick_params(axis="x", labelsize=10)
    save(fig, "09_llm_kalite.jpg")


def slide_llm_model_prompt() -> None:
    fig, ax = new_fig(
        "Prompt ve model  ·  kazananlar",
        "Cite: [5237 m.158] zorunlu  ·  llm-large daha az lexical hallu  ·  temp 0 ≈ 0.2",
    )
    labels = ["llm-fast\nbaseline", "temp 0.2", "Cite\nprompt", "llm-large", "Strict\nprompt"]
    files = [
        "hybrid_llm.json",
        "hybrid_temp02.json",
        "hybrid_prompt_cite.json",
        "hybrid_llm_large.json",
        "hybrid_prompt_strict.json",
    ]
    corr = [load(f)["Answer Correctness"] for f in files]
    cite = [load(f)["Citation Precision"] for f in files]
    grouped_bars(ax, labels, {"Correctness": corr, "Citation precision": cite})
    save(fig, "10_llm_prompt_model.jpg")


def slide_hyde_rewrite() -> None:
    fig, ax = new_fig(
        "HyDE ve query rewrite  ·  kullanma",
        "Rewrite retrieval'ı kırıyor  ·  HyDE 2.5× yavaş, R@5 düşüyor",
    )
    labels = ["Hybrid LLM\n(orijinal sorgu)", "HyDE", "Query rewrite"]
    files = ["hybrid_llm.json", "hybrid_hyde.json", "hybrid_rewrite.json"]
    r5 = [load(f)["Recall@5"] for f in files]
    corr = [load(f)["Answer Correctness"] for f in files]
    grouped_bars(ax, labels, {"Recall@5": r5, "Correctness": corr})
    save(fig, "11_hyde_rewrite.jpg")


def slide_llm_types() -> None:
    fig, ax = new_fig(
        "LLM  ·  soru tipi correctness",
        "llm-fast  ·  50 soru  ·  aggregation / multi-hop / ambiguous hâlâ zayıf",
    )
    by = load("hybrid_llm.json")["metrics_by_question_type"]
    order = [
        ("typo", "Typo"),
        ("keyword", "Keyword"),
        ("factual", "Factual"),
        ("comparison", "Comparison"),
        ("semantic", "Semantic"),
        ("unanswerable", "Unanswerable"),
        ("multi_hop", "Multi-hop"),
        ("aggregation", "Aggregation"),
        ("ambiguous", "Ambiguous"),
    ]
    labels = [lab for _, lab in order]
    values = [by[key]["Answer Correctness"] for key, _ in order]
    colors = [TEAL if v >= 0.75 else GOLD if v >= 0.4 else CORAL for v in values]
    barh(ax, labels, values, colors)
    ax.set_xlabel("Answer correctness")
    save(fig, "12_llm_soru_tipi.jpg")


def slide_english() -> None:
    fig, ax = new_fig(
        "İngilizce sorgu  ·  Hybrid",
        "20 soruluk mini set  ·  TR embedder zayıf  ·  ayrı İngilizce embed / çeviri gerekir",
    )
    labels = ["Türkçe hybrid\n(400 soru)", "İngilizce hybrid\n(20 soru)"]
    values = [load("hybrid.json")["Recall@5"], load("lang_en.json")["Recall@5"]]
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=[TEAL, CORAL], width=0.45, zorder=3)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.set_ylabel("Recall@5")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.03,
            f"{val:.0%}",
            ha="center",
            color=WHITE,
            fontsize=20,
            fontweight="bold",
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    save(fig, "13_ingilizce.jpg")


def slide_stack() -> None:
    fig, ax = new_fig("Production yığını  ·  benchmark kararı", "Ölçülen kazananlar  ·  HyDE / rewrite / varsayılan CE yok")
    ax.set_axis_off()
    items = [
        (TEAL, "Chunking", "Madde bazlı  ·  512 token pencereye geçme"),
        (GOLD, "Retrieval", "Hybrid RRF  ·  BM25 50 + dense 50  ·  K=5 üret"),
        (BLUE, "Kapı", "Dense cosine 0.70  ·  RRF skoru ~0.03, 0.70 ile kıyaslama"),
        (GREEN, "Sorgu", "Kanun hint + aggregation multi-query  ·  rewrite yok"),
        (LILAC, "Cevap", "Cite prompt [kanun m.madde]  ·  llm-large kalite"),
        (CORAL, "Kapalı tut", "Cross-encoder varsayılan  ·  HyDE  ·  query rewrite"),
    ]
    for i, (color, title, body) in enumerate(items):
        y = 0.82 - i * 0.14
        ax.add_patch(
            plt.Rectangle((0.06, y - 0.04), 0.88, 0.12, transform=ax.transAxes, color="#102F52", zorder=2)
        )
        ax.add_patch(
            plt.Rectangle((0.06, y - 0.04), 0.012, 0.12, transform=ax.transAxes, color=color, zorder=3)
        )
        ax.text(0.10, y + 0.035, title, transform=ax.transAxes, fontsize=18, fontweight="bold", color=color, zorder=4)
        ax.text(0.10, y - 0.012, body, transform=ax.transAxes, fontsize=14, color=WHITE, zorder=4)
    save(fig, "14_production_yigini.jpg")


def main() -> None:
    setup()
    slide_retrieval()
    slide_latency()
    slide_chunking()
    slide_query()
    slide_aggregation()
    slide_topk()
    slide_by_type()
    slide_reranker()
    slide_llm_quality()
    slide_llm_model_prompt()
    slide_hyde_rewrite()
    slide_llm_types()
    slide_english()
    slide_stack()
    print(f"wrote {len(list(OUT.glob('*.jpg')))} jpgs -> {OUT}")


if __name__ == "__main__":
    main()
