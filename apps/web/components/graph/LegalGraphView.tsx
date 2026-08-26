"use client";

import { useEffect, useMemo, useState } from "react";
import { Evidence, GraphDump, getGraph } from "@/lib/api";
import { VisEdge, VisGraph, VisNode } from "@/components/graph/VisGraph";
import { lawPrefix, shortLabel } from "@/components/graph/layout";

type Props = {
  evidence: Evidence[];
  selected: number | null;
  onSelect: (n: number) => void;
  query?: string;
};

const ARTICLE = {
  background: "#1a3052",
  border: "#8aa0c0",
  highlight: { background: "#1a3052", border: "#e8c56a" },
};
const DECISION = {
  background: "#b8942a",
  border: "#e8c56a",
  highlight: { background: "#d4af37", border: "#f6e7b0" },
};
const LAW = {
  background: "#0a1628",
  border: "#d4af37",
  highlight: { background: "#12233d", border: "#f6e7b0" },
};
const QUERY = {
  background: "#d4af37",
  border: "#f6e7b0",
  highlight: { background: "#e8c56a", border: "#f6e7b0" },
};
const COURT = {
  background: "#12233d",
  border: "#8fa0b8",
  highlight: { background: "#1a3052", border: "#e8c56a" },
};

function evidenceId(item: Evidence) {
  if (item.document_id?.startsWith("decision:")) return item.document_id;
  if (item.law_no && item.article_no) return `law:${item.law_no}:article:${item.article_no}`;
  return item.chunk_id;
}

function evidenceLabel(item: Evidence) {
  if (item.document_id?.startsWith("decision:")) {
    return shortLabel(item.title || "Karar", 22);
  }
  return `${lawPrefix(item.law_no)} ${item.article_no ?? "?"}`;
}

function kindColor(kind: string, hit: boolean) {
  if (kind === "decision") return DECISION;
  if (kind === "law") return LAW;
  if (kind === "court") return COURT;
  if (kind === "query") return QUERY;
  return hit ? { ...ARTICLE, border: "#e8c56a" } : ARTICLE;
}

function kindShape(kind: string): VisNode["shape"] {
  if (kind === "decision") return "box";
  if (kind === "law") return "diamond";
  if (kind === "query") return "ellipse";
  return "dot";
}

export function LegalGraphView({ evidence, selected, onSelect, query }: Props) {
  const [hover, setHover] = useState<string>("");
  const [corpus, setCorpus] = useState<GraphDump | null>(null);

  useEffect(() => {
    let cancelled = false;
    getGraph()
      .then((data) => {
        if (!cancelled) setCorpus(data);
      })
      .catch(() => {
        if (!cancelled) setCorpus({ nodes: [], edges: [], counts: {} });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { nodes, edges, stats } = useMemo(() => {
    const nodeMap = new Map<string, VisNode>();
    const edgeList: VisEdge[] = [];
    const seen = new Set<string>();
    const hitIds = new Set(evidence.map(evidenceId));
    const evidenceById = new Map(evidence.map((item) => [evidenceId(item), item]));

    function addNode(node: VisNode) {
      const existing = nodeMap.get(node.id);
      if (existing) {
        if (node.evidenceN != null) existing.evidenceN = node.evidenceN;
        if ((node.size ?? 0) > (existing.size ?? 0)) existing.size = node.size;
        if (node.font) existing.font = node.font;
        return;
      }
      nodeMap.set(node.id, node);
    }

    function addEdge(from: string, to: string, label: string) {
      if (from === to) return;
      const key = `${from}>${to}`;
      if (seen.has(key)) return;
      seen.add(key);
      const gold = label === "CITES" || label === "HIT";
      edgeList.push({
        id: key,
        from,
        to,
        label: label === "HAS_ARTICLE" ? "" : label,
        color: gold ? "#d4af37" : label === "HAS_ARTICLE" ? "#3d4f6a" : "#8fa0b8",
      });
    }

    for (const raw of corpus?.nodes ?? []) {
      const hit = hitIds.has(raw.id);
      const ev = evidenceById.get(raw.id);
      addNode({
        id: raw.id,
        label: raw.kind === "article" && !hit ? String(raw.article_no || raw.label) : raw.label,
        title: raw.title || raw.label,
        group: raw.kind,
        shape: kindShape(raw.kind),
        color: kindColor(raw.kind, hit),
        size: hit ? 26 : raw.kind === "law" ? 28 : raw.kind === "decision" ? 18 : 10,
        font: {
          color: raw.kind === "decision" ? "#1a1204" : hit ? "#f6e7b0" : "#8aa0c0",
          size: hit || raw.kind === "law" || raw.kind === "decision" ? 12 : 0,
        },
        evidenceN: ev?.n,
      });
    }

    for (const raw of corpus?.edges ?? []) {
      addEdge(raw.source, raw.target, raw.label);
    }

    for (const item of evidence) {
      const id = evidenceId(item);
      const decision = Boolean(item.document_id?.startsWith("decision:"));
      addNode({
        id,
        label: evidenceLabel(item),
        title: `${decision ? "Karar" : "Madde"}: ${item.title || evidenceLabel(item)}`,
        group: decision ? "decision" : "article",
        shape: decision ? "box" : "dot",
        color: decision ? DECISION : ARTICLE,
        size: item.used_in_answer ? 28 : 20,
        font: { color: decision ? "#1a1204" : "#e8eef6", size: 13 },
        evidenceN: item.n,
      });
      addEdge("query", id, "HIT");
      for (const neighbor of item.graph_neighbors) {
        if (!neighbor.id) continue;
        const neighborDecision = neighbor.kind === "decision";
        addNode({
          id: neighbor.id,
          label: neighborDecision
            ? shortLabel(neighbor.title || neighbor.article_no || "Karar", 20)
            : `m.${neighbor.article_no ?? "?"}`,
          title: `${neighborDecision ? "Karar" : "Madde"}: ${neighbor.title || neighbor.article_no || neighbor.id}`,
          group: neighborDecision ? "decision" : "article",
          shape: neighborDecision ? "box" : "dot",
          color: neighborDecision ? DECISION : ARTICLE,
          size: 14,
          font: { color: neighborDecision ? "#1a1204" : "#e8eef6", size: 11 },
        });
        if (neighbor.direction === "out") addEdge(id, neighbor.id, neighborDecision || decision ? "CITES" : "REFERENCES");
        else addEdge(neighbor.id, id, neighbor.kind === "decision" ? "CITES" : "REFERENCES");
      }
    }

    if (evidence.length) {
      addNode({
        id: "query",
        label: shortLabel(query?.trim() || "SORGU", 18),
        title: query || "Sorgu",
        group: "query",
        shape: "ellipse",
        color: QUERY,
        size: 34,
        font: { color: "#1a1204", size: 13 },
      });
    }

    const laid = [...nodeMap.values()];
    return {
      nodes: laid,
      edges: edgeList,
      stats: {
        articles: laid.filter((n) => n.group === "article").length,
        decisions: laid.filter((n) => n.group === "decision").length,
        relations: edgeList.length,
      },
    };
  }, [corpus, evidence, query]);

  const selectedId = nodes.find((node) => node.evidenceN === selected)?.id ?? null;
  const caption =
    hover ||
    (selected != null
      ? nodes.find((n) => n.evidenceN === selected)?.title
      : "Tüm arşiv grafı. Altın düğümler bu sorguya ait. Sürükleyin, tekerlekle yakınlaştırın.");

  if (!corpus) {
    return <p className="muted graph-empty">Graf Yükleniyor…</p>;
  }
  if (nodes.length === 0) {
    return <p className="muted graph-empty">Graf için kaynak yok. Neo4j veya sorgu sonucu gerekli.</p>;
  }

  return (
    <div className="graph-shell full">
      <div className="graph-stats" aria-hidden>
        <span>
          <strong>{stats.articles}</strong> madde
        </span>
        <span>
          <strong>{stats.decisions}</strong> karar
        </span>
        <span>
          <strong>{stats.relations}</strong> atıf
        </span>
      </div>
      <div className="graph-canvas vis">
        <VisGraph
          nodes={nodes}
          edges={edges}
          selectedId={selectedId}
          onNodeClick={(id, n) => {
            const node = nodes.find((item) => item.id === id);
            setHover(node?.title || node?.label || "");
            if (n != null) onSelect(n);
          }}
        />
      </div>
      <div className="graph-legend" aria-hidden>
        <span>
          <i className="legend-dot article" /> Madde
        </span>
        <span>
          <i className="legend-dot decision" /> Karar
        </span>
        <span>
          <i className="legend-dot used" /> Cevapta
        </span>
        <span>
          <i className="legend-dot query" /> Sorgu
        </span>
      </div>
      <p className="graph-caption">{caption}</p>
    </div>
  );
}
