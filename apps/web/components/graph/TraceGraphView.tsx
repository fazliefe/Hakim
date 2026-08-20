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

const LEVEL: Record<string, number> = {
  query: 0,
  retriever: 1,
  fusion: 2,
  chunk: 3,
  answer: 4,
};

const COLORS: Record<string, VisNode["color"]> = {
  query: { background: "#0a1628", border: "#d4af37", highlight: { background: "#0a1628", border: "#f6e7b0" } },
  retriever: { background: "#1a3052", border: "#8aa0c0", highlight: { background: "#1a3052", border: "#e8c56a" } },
  fusion: { background: "#1a3052", border: "#d4af37", highlight: { background: "#1a3052", border: "#f6e7b0" } },
  chunk: { background: "#12233d", border: "#b8942a", highlight: { background: "#12233d", border: "#e8c56a" } },
  answer: { background: "#d4af37", border: "#f6e7b0", highlight: { background: "#e8c56a", border: "#f6e7b0" } },
};

export function TraceGraphView({ nodes, edges, evidence, selected, onSelect }: Props) {
  const [hover, setHover] = useState<string>("");

  const { visNodes, visEdges } = useMemo(() => {
    const visNodes: VisNode[] = [];
    const ids = new Set<string>();
    for (const node of nodes) {
      if (node.kind === "chunk" && !node.meta.used_in_answer) continue;
      const evidenceN = evidence.find((item) => item.chunk_id === node.id)?.n;
      ids.add(node.id);
      visNodes.push({
        id: node.id,
        label: shortLabel(node.label, node.kind === "chunk" ? 20 : 14),
        title:
          node.kind === "chunk"
            ? `${node.label} · BM25 ${String(node.meta.bm25_rank ?? "—")} · Anlamsal ${String(node.meta.semantic_rank ?? "—")} · RRF ${String(node.meta.rrf_rank ?? "—")}`
            : node.label,
        group: node.kind,
        shape: node.kind === "chunk" ? "box" : "ellipse",
        color: COLORS[node.kind] ?? COLORS.retriever,
        size: node.kind === "answer" || node.kind === "query" ? 26 : 18,
        level: LEVEL[node.kind] ?? 2,
        font: { color: node.kind === "answer" ? "#1a1204" : "#e8eef6", size: 12 },
        evidenceN,
      });
    }
    const visEdges: VisEdge[] = edges
      .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
      .map((edge) => ({
        id: `${edge.source}-${edge.target}-${edge.label}`,
        from: edge.source,
        to: edge.target,
        label: edge.label,
        color: "#8fa0b8",
      }));
    return { visNodes, visEdges };
  }, [nodes, edges, evidence]);

  const selectedId = visNodes.find((node) => node.evidenceN === selected)?.id ?? null;

  return (
    <div className="graph-shell full">
      <div className="graph-canvas vis">
        <VisGraph
          nodes={visNodes}
          edges={visEdges}
          selectedId={selectedId}
          hierarchical
          onNodeClick={(id, n) => {
            const node = visNodes.find((item) => item.id === id);
            setHover(node?.title || "");
            if (n != null) onSelect(n);
          }}
        />
      </div>
      <p className="graph-hint">Sorgu → BM25 / vektör / graf → RRF → kaynak → cevap</p>
      <p className="graph-caption">
        {hover || "Düğüme tıklayın: getirici, sıra ve kaynağın cevapta kullanılıp kullanılmadığı."}
      </p>
    </div>
  );
}
