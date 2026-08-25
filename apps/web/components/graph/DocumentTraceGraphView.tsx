"use client";

import { useMemo, useState } from "react";
import { Evidence, TraceEdge, TraceNode } from "@/lib/api";
import { VisEdge, VisGraph, VisNode } from "@/components/graph/VisGraph";
import { shortLabel } from "@/components/graph/layout";

type Props = {
  nodes: TraceNode[];
  edges: TraceEdge[];
  evidence: Evidence[];
  selected: number | null;
  onSelect: (n: number) => void;
};

// Aynı görsel dil: TraceGraphView'daki (araştırma zinciri) renk sözleşmesi.
const COLORS: Record<string, VisNode["color"]> = {
  query: { background: "#0a1628", border: "#d4af37", highlight: { background: "#0a1628", border: "#f6e7b0" } },
  retriever: { background: "#1a3052", border: "#8aa0c0", highlight: { background: "#1a3052", border: "#e8c56a" } },
  fusion: { background: "#1a3052", border: "#d4af37", highlight: { background: "#1a3052", border: "#f6e7b0" } },
  chunk: { background: "#12233d", border: "#b8942a", highlight: { background: "#12233d", border: "#e8c56a" } },
  answer: { background: "#d4af37", border: "#f6e7b0", highlight: { background: "#e8c56a", border: "#f6e7b0" } },
  route: { background: "#1a3052", border: "#6a7f9c", highlight: { background: "#1a3052", border: "#e8c56a" } },
};

const PIPELINE_ORDER = ["okuyucu", "sinif", "mevzuat", "sure", "taslak", "havale"];

const COL = 132;
const ROW = 92;
const ORIGIN_X = 64;
const ORIGIN_Y = 52;
const CHUNK_COL_OFFSET = 40;

function formatMs(ms?: unknown) {
  const value = typeof ms === "number" ? ms : null;
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)} s`;
  return `${value} ms`;
}

export function DocumentTraceGraphView({ nodes, edges, evidence, selected, onSelect }: Props) {
  const [hover, setHover] = useState<string>("");

  const byId = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const pipeline = useMemo(
    () => PIPELINE_ORDER.map((id) => byId.get(id)).filter((node): node is TraceNode => Boolean(node)),
    [byId],
  );
  const chunks = useMemo(() => nodes.filter((node) => node.kind === "chunk"), [nodes]);

  const { visNodes, visEdges } = useMemo(() => {
    const visN: VisNode[] = [];
    const placed = new Map<string, { x: number; y: number }>();

    pipeline.forEach((node, index) => {
      const x = ORIGIN_X + index * COL;
      const y = ORIGIN_Y;
      placed.set(node.id, { x, y });
      visN.push({
        id: node.id,
        label: node.label,
        title: `${node.label}: ${node.meta.summary ?? ""}`.trim(),
        group: node.kind,
        shape: "ellipse",
        color: COLORS[node.kind] ?? COLORS.retriever,
        size: node.kind === "answer" ? 22 : 17,
        x,
        y,
        fixed: true,
        font: { color: node.kind === "answer" ? "#1a1204" : "#e8eef6", size: 11 },
      });
    });

    const mevzuatPos = placed.get("mevzuat");
    if (mevzuatPos && chunks.length) {
      chunks.forEach((node, index) => {
        placed.set(node.id, { x: mevzuatPos.x + CHUNK_COL_OFFSET, y: mevzuatPos.y + ROW * (index + 1) });
        const evidenceItem = evidence.find((item) => item.chunk_id === node.id);
        visN.push({
          id: node.id,
          label: shortLabel(node.label, 16),
          title: String(node.meta.title || node.label),
          group: "chunk",
          shape: "box",
          color: COLORS.chunk,
          size: 14,
          x: mevzuatPos.x + CHUNK_COL_OFFSET,
          y: mevzuatPos.y + ROW * (index + 1),
          fixed: true,
          font: { color: "#e8eef6", size: 10 },
          evidenceN: evidenceItem?.n,
        });
      });
    }

    // Kenarları doğrudan backend'in trace_edges'inden çiz — pipeline sırasını
    // frontend'de yeniden inşa etmiyoruz (retry self-loop dahil, tek kaynak backend).
    const nodeIds = new Set(visN.map((node) => node.id));
    const visE: VisEdge[] = edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge, index) => {
        const isRetry = edge.source === "mevzuat" && edge.target === "mevzuat";
        const isCite = edge.label === "cite";
        return {
          id: `e-${edge.source}-${edge.target}-${index}`,
          from: edge.source,
          to: edge.target,
          label: edge.label || undefined,
          color: isRetry ? "#d4af37" : "#8fa0b8",
          dashes: isRetry || isCite,
        };
      });

    return { visNodes: visN, visEdges: visE };
  }, [pipeline, chunks, evidence, edges]);

  const selectedId = visNodes.find((node) => node.evidenceN === selected)?.id ?? null;

  if (!pipeline.length) {
    return <p className="muted evrak-hint">Grafik için önce evrakı çözümleyin.</p>;
  }

  return (
    <div className="graph-shell full">
      <div className="graph-canvas vis">
        <VisGraph
          nodes={visNodes}
          edges={visEdges}
          selectedId={selectedId}
          onNodeClick={(id, n) => {
            const node = byId.get(id);
            if (node) {
              const state = node.meta.state ? ` (${node.meta.state})` : "";
              setHover(
                `${node.label}${state}: ${node.meta.summary ?? node.meta.title ?? ""} · ${formatMs(node.meta.ms)}`,
              );
            }
            if (n != null) onSelect(n);
          }}
        />
      </div>
      <p className="graph-hint">Okuyucu → sınıflandırıcı → mevzuat → süre → taslak → havale</p>
      <p className="graph-caption">{hover || "Hangi karar hangi maddeye dayanıyor — düğüme tıklayın."}</p>
    </div>
  );
}
