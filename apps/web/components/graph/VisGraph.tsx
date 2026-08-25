"use client";

import { useEffect, useRef } from "react";
import { Network } from "vis-network/standalone";
import type { Options } from "vis-network";

export type VisNode = {
  id: string;
  label: string;
  title?: string;
  group?: string;
  size?: number;
  level?: number;
  x?: number;
  y?: number;
  fixed?: boolean;
  shape?: "dot" | "box" | "diamond" | "ellipse";
  color?: {
    background: string;
    border: string;
    highlight?: { background: string; border: string };
  };
  font?: { color?: string; size?: number; face?: string };
  evidenceN?: number;
};

export type VisEdge = {
  id: string;
  from: string;
  to: string;
  label?: string;
  color?: string;
  dashes?: boolean;
};

type Props = {
  nodes: VisNode[];
  edges: VisEdge[];
  selectedId?: string | null;
  hierarchical?: boolean;
  onNodeClick?: (id: string, evidenceN?: number) => void;
};

const baseOptions: Options = {
  nodes: {
    shape: "dot",
    font: { size: 13, color: "#e8eef6", face: "Source Sans 3, Segoe UI, sans-serif" },
    borderWidth: 2,
    shadow: false,
  },
  edges: {
    width: 1.4,
    color: { color: "#8fa0b8", highlight: "#d4af37" },
    arrows: { to: { enabled: true, scaleFactor: 0.55 } },
    font: { size: 10, color: "#a8b4c8", strokeWidth: 0 },
    smooth: { enabled: true, type: "continuous", roundness: 0.45 },
  },
  interaction: {
    hover: true,
    tooltipDelay: 180,
    hideEdgesOnDrag: false,
    navigationButtons: false,
    zoomView: true,
    dragView: true,
  },
};

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const item of items) {
    const id = String(item.id);
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  return out;
}

function uniqueEdges(edges: VisEdge[]): VisEdge[] {
  const ids = new Set<string>();
  const out: VisEdge[] = [];
  edges.forEach((edge, index) => {
    const id = String(edge.id || `e${index}`);
    if (ids.has(id)) return;
    ids.add(id);
    out.push({ ...edge, id });
  });
  return out.map((edge, index) => ({ ...edge, id: `e${index}` }));
}

export function VisGraph({ nodes, edges, selectedId, hierarchical, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const clickRef = useRef(onNodeClick);
  const evidenceRef = useRef(new Map<string, number | undefined>());
  clickRef.current = onNodeClick;
  evidenceRef.current = new Map(nodes.map((node) => [node.id, node.evidenceN]));

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const cleanNodes = uniqueById(nodes.map(({ evidenceN: _evidenceN, ...node }) => node));
    const nodeIds = new Set(cleanNodes.map((node) => String(node.id)));
    const payload = {
      nodes: cleanNodes,
      edges: uniqueEdges(edges.filter((edge) => nodeIds.has(String(edge.from)) && nodeIds.has(String(edge.to)))),
    };

    const hasFixed = cleanNodes.some((node) => node.x != null && node.y != null);
    const options: Options = hierarchical
      ? {
          ...baseOptions,
          layout: {
            hierarchical: {
              enabled: true,
              direction: "LR",
              sortMethod: "directed",
              levelSeparation: 168,
              nodeSpacing: 72,
              treeSpacing: 88,
              blockShifting: true,
              edgeMinimization: true,
            },
          },
          physics: { enabled: false },
        }
      : hasFixed
        ? {
            ...baseOptions,
            layout: { hierarchical: { enabled: false }, improvedLayout: false, randomSeed: 1 },
            physics: { enabled: false },
            edges: {
              ...baseOptions.edges,
              smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.38 },
            },
          }
      : {
          ...baseOptions,
          layout: { improvedLayout: nodes.length < 120, hierarchical: { enabled: false } },
          physics: {
            enabled: true,
            stabilization: { iterations: nodes.length > 200 ? 200 : 140, fit: true },
            barnesHut: {
              gravitationalConstant: nodes.length > 80 ? -28000 : -12000,
              centralGravity: nodes.length > 80 ? 0.08 : 0.18,
              springLength: nodes.length > 80 ? 70 : 160,
              springConstant: 0.03,
              damping: 0.16,
            },
          },
        };

    let network: Network;
    try {
      network = new Network(el, payload, options);
    } catch {
      return;
    }
    const resize = () => {
      if (!el.clientWidth || !el.clientHeight) return;
      network.setSize(`${el.clientWidth}px`, `${el.clientHeight}px`);
      network.redraw();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    network.once("stabilizationIterationsDone", () => {
      network.setOptions({ physics: { enabled: false } });
      network.fit({ animation: false });
    });
    if (hierarchical || hasFixed) {
      network.fit({ animation: false });
    }
    network.on("click", (params) => {
      if (params.nodes.length === 0) return;
      const id = String(params.nodes[0]);
      clickRef.current?.(id, evidenceRef.current.get(id));
    });
    networkRef.current = network;

    return () => {
      ro.disconnect();
      network.destroy();
      networkRef.current = null;
    };
  }, [nodes, edges, hierarchical]);

  useEffect(() => {
    const network = networkRef.current;
    if (!network || !selectedId) return;
    try {
      network.selectNodes([selectedId]);
    } catch {
      /* node may have been removed */
    }
  }, [selectedId]);

  return <div ref={containerRef} className="vis-canvas" />;
}
