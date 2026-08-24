"use client";

import { useMemo, useState } from "react";
import { Evidence, Observability, TraceEdge, TraceHop, TraceNode } from "@/lib/api";
import { hopTitle } from "@/lib/labels";
import { VisEdge, VisGraph, VisNode } from "@/components/graph/VisGraph";
import { shortLabel } from "@/components/graph/layout";

type Props = {
  nodes: TraceNode[];
  edges: TraceEdge[];
  evidence: Evidence[];
  selected: number | null;
  onSelect: (n: number) => void;
  observability?: Observability | null;
};

type Step = { visId: string; base: string; label: string; kind: string };

const COLORS: Record<string, VisNode["color"]> = {
  query: { background: "#0a1628", border: "#d4af37", highlight: { background: "#0a1628", border: "#f6e7b0" } },
  retriever: { background: "#1a3052", border: "#8aa0c0", highlight: { background: "#1a3052", border: "#e8c56a" } },
  fusion: { background: "#1a3052", border: "#d4af37", highlight: { background: "#1a3052", border: "#f6e7b0" } },
  chunk: { background: "#12233d", border: "#b8942a", highlight: { background: "#12233d", border: "#e8c56a" } },
  answer: { background: "#d4af37", border: "#f6e7b0", highlight: { background: "#e8c56a", border: "#f6e7b0" } },
};

const HOP_TO_NODE: Record<string, string> = {
  sorgu: "query",
  kontrol: "query",
  bm25: "bm25",
  vektor: "vector",
  rrf: "rrf",
  rerank: "rerank",
  graf: "graph",
  cevap: "answer",
  reddet: "answer",
};

const PIPELINE: Record<string, { label: string; kind: string }> = {
  query: { label: "SORGU", kind: "query" },
  bm25: { label: "BM25", kind: "retriever" },
  vector: { label: "VEKTÖR", kind: "retriever" },
  rrf: { label: "RRF", kind: "fusion" },
  rerank: { label: "RERANK", kind: "fusion" },
  graph: { label: "GRAPH", kind: "retriever" },
  answer: { label: "CEVAP", kind: "answer" },
};

const EDGE_LABELS: Record<string, string> = {
  "query-bm25": "lexical",
  "query-vector": "gerekirse",
  "query-answer": "reddet",
  "bm25-vector": "gerekirse",
  "bm25-rrf": "top50",
  "vector-rrf": "semantic",
  "rrf-rerank": "reorder",
  "rerank-graph": "neighbors",
  "answer-vector": "retry",
};

function executedSteps(hops: TraceHop[]): Step[] {
  const steps: Step[] = [];
  const counts: Record<string, number> = {};
  for (const hop of hops) {
    if (hop.state === "skip") continue;
    const base = HOP_TO_NODE[hop.id];
    const spec = base ? PIPELINE[base] : undefined;
    if (!spec) continue;
    if (steps.length && steps[steps.length - 1].base === base) continue;
    counts[base] = (counts[base] || 0) + 1;
    const visId = counts[base] === 1 ? base : `${base}#${counts[base]}`;
    steps.push({ visId, base, label: spec.label, kind: spec.kind });
  }
  return steps;
}

function splitPasses(steps: Step[]): Step[][] {
  const passes: Step[][] = [];
  let current: Step[] = [];
  for (const step of steps) {
    current.push(step);
    if (step.base === "answer") {
      passes.push(current);
      current = [];
    }
  }
  if (current.length) passes.push(current);
  return passes.length ? passes : [steps];
}

const COL = 118;
const ROW = 124;
const ORIGIN_X = 56;
const ORIGIN_Y = 52;

function hopForVisId(hops: TraceHop[], visId: string) {
  const base = visId.split("#")[0];
  const nth = visId.includes("#") ? Number(visId.split("#")[1]) : 1;
  const matches = hops.filter((hop) => HOP_TO_NODE[hop.id] === base);
  return matches[nth - 1];
}

function formatMs(ms?: number) {
  if (ms == null) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${ms} ms`;
}

function formatTokens(n?: number) {
  return (n ?? 0).toLocaleString("tr-TR");
}

function formatCost(n?: number) {
  if (!n) return "$0";
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

function hopCaption(hop: TraceHop) {
  const tokens = (hop.prompt_tokens ?? 0) + (hop.completion_tokens ?? 0);
  const parts = [formatMs(hop.ms)];
  if (tokens) parts.push(`${formatTokens(tokens)} tok`);
  if (hop.cost_usd) parts.push(formatCost(hop.cost_usd));
  return parts.join(" · ");
}

export function TraceGraphView({ nodes, evidence, selected, onSelect, observability }: Props) {
  const [hover, setHover] = useState<string>("");
  const hops = (observability?.hops ?? []).filter((hop) => hop.state !== "skip");
  const steps = useMemo(() => executedSteps(observability?.hops ?? []), [observability?.hops]);

  const { visNodes, visEdges } = useMemo(() => {
    const visNodes: VisNode[] = [];
    const visEdges: VisEdge[] = [];
    const ids = new Set<string>();
    const chunks = nodes.filter((node) => node.kind === "chunk" && node.meta.used_in_answer);
    const passes = splitPasses(steps);
    const placed = new Map<string, { x: number; y: number }>();

    passes.forEach((pass, row) => {
      let startCol = 0;
      if (row > 0) {
        const prev = passes[0];
        const aligned = prev.findIndex((step) => step.base === pass[0]?.base);
        startCol = aligned >= 0 ? aligned : Math.max(0, prev.length - pass.length);
      }
      pass.forEach((step, index) => {
        ids.add(step.visId);
        const x = ORIGIN_X + (startCol + index) * COL;
        const y = ORIGIN_Y + row * ROW;
        placed.set(step.visId, { x, y });
        visNodes.push({
          id: step.visId,
          label: step.label,
          title: step.label,
          group: step.kind,
          shape: "ellipse",
          color: COLORS[step.kind] ?? COLORS.retriever,
          size: step.kind === "answer" || step.kind === "query" ? 22 : 16,
          x,
          y,
          fixed: true,
          font: { color: step.kind === "answer" ? "#1a1204" : "#e8eef6", size: 11 },
        });
      });
    });

    steps.slice(1).forEach((target, index) => {
      const source = steps[index];
      const key = `${source.base}-${target.base}`;
      visEdges.push({
        id: `e-${source.visId}-${target.visId}-${index}`,
        from: source.visId,
        to: target.visId,
        label: EDGE_LABELS[key] ?? "",
        color: key === "answer-vector" ? "#d4af37" : "#8fa0b8",
        dashes: key === "answer-vector",
      });
    });

    const lastPass = passes[passes.length - 1] ?? [];
    const lastAnswer = [...steps].reverse().find((step) => step.base === "answer");
    const citeFrom = [...steps].reverse().find((step) => ["rerank", "rrf", "bm25", "query"].includes(step.base));
    if (chunks.length && lastAnswer && citeFrom) {
      const lastPos = placed.get(lastPass[lastPass.length - 1]?.visId ?? lastAnswer.visId) ?? { x: ORIGIN_X, y: ORIGIN_Y };
      const cols = chunks.length > 3 ? 2 : 1;
      const rows = Math.ceil(chunks.length / cols);
      chunks.forEach((node, index) => {
        if (ids.has(node.id)) return;
        ids.add(node.id);
        const col = index % cols;
        const row = Math.floor(index / cols);
        const x = lastPos.x + COL + col * 108;
        const y = lastPos.y - ((rows - 1) * 42) / 2 + row * 42;
        const evidenceN = evidence.find((item) => item.chunk_id === node.id)?.n;
        visNodes.push({
          id: node.id,
          label: shortLabel(node.label, 14),
          title: node.label,
          group: "chunk",
          shape: "box",
          color: COLORS.chunk,
          size: 14,
          x,
          y,
          fixed: true,
          font: { color: "#e8eef6", size: 10 },
          evidenceN,
        });
        const rank = Number.isInteger(node.meta.rrf_rank) ? node.meta.rrf_rank : evidenceN ?? index + 1;
        visEdges.push({
          id: `e-${citeFrom.visId}-${node.id}-rank`,
          from: citeFrom.visId,
          to: node.id,
          label: `#${rank}`,
          color: "#8fa0b8",
        });
        visEdges.push({
          id: `e-${node.id}-${lastAnswer.visId}-cite`,
          from: node.id,
          to: lastAnswer.visId,
          label: "cite",
          color: "#8fa0b8",
        });
      });
    }

    return { visNodes, visEdges };
  }, [nodes, evidence, steps]);

  const selectedId = visNodes.find((node) => node.evidenceN === selected)?.id ?? null;
  const totals = observability?.totals;
  const showStats = Boolean(totals?.ms || totals?.prompt_tokens || totals?.completion_tokens || totals?.cost_usd);

  return (
    <div className="graph-shell full">
      {showStats ? (
        <div className="graph-stats">
          <span>
            Süre: <strong>{formatMs(totals?.ms)}</strong>
          </span>
          <span>
            Token:{" "}
            <strong>
              {formatTokens(totals?.prompt_tokens)} giriş / {formatTokens(totals?.completion_tokens)} çıkış
            </strong>
          </span>
          <span>
            Maliyet: <strong>{formatCost(totals?.cost_usd)}</strong>
          </span>
        </div>
      ) : null}
      {hops.length ? (
        <ol className="trace-hops" aria-label="Adım süreleri">
          {hops.map((hop, index) => {
            const title = hopTitle(hop.id, hop.title);
            return (
              <li key={`${hop.id}-${index}`}>
                <button
                  type="button"
                  className={`trace-hop ${hop.state}`}
                  title={`${title}: ${hopCaption(hop)}`}
                  onClick={() => setHover(`${title}: ${hopCaption(hop)}`)}
                >
                  <span className="trace-hop-title">{title}</span>
                  <span className="trace-hop-ms">{formatMs(hop.ms)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      ) : null}
      <div className="graph-canvas vis">
        <VisGraph
          nodes={visNodes}
          edges={visEdges}
          selectedId={selectedId}
          onNodeClick={(id, n) => {
            const node = visNodes.find((item) => item.id === id);
            const hop = hopForVisId(hops, id);
            setHover(hop ? `${hopTitle(hop.id, hop.title)}: ${hopCaption(hop)}` : node?.title || "");
            if (n != null) onSelect(n);
          }}
        />
      </div>
      <p className="graph-hint">Soru → tarama → kaynak → cevap</p>
      <p className="graph-caption">{hover || "Süre, token ve maliyet."}</p>
    </div>
  );
}
