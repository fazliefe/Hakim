export type GraphKind = "article" | "decision" | "query" | "retriever" | "fusion" | "chunk" | "answer";

export type LaidOutNode = {
  id: string;
  label: string;
  kind: GraphKind;
  x: number;
  y: number;
  evidenceN?: number;
  usedInAnswer?: boolean;
  subtitle?: string;
};

export type LaidOutEdge = {
  source: string;
  target: string;
  label?: string;
  official?: boolean;
};

export function shortLabel(text: string, max = 22) {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

export function lawPrefix(lawNo?: string | null) {
  if (lawNo === "5237") return "TCK";
  if (lawNo === "5271") return "CMK";
  return lawNo ? `K.${lawNo}` : "Kanun";
}

export function runForceLayout(
  nodes: LaidOutNode[],
  edges: LaidOutEdge[],
  width: number,
  height: number,
) {
  const count = nodes.length;
  if (count === 0) return;
  const radius = Math.min(width, height) * 0.32;
  nodes.forEach((node, index) => {
    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
    node.x = width / 2 + Math.cos(angle) * radius;
    node.y = height / 2 + Math.sin(angle) * radius * 0.72;
  });
  const index = new Map(nodes.map((node) => [node.id, node]));
  const k = Math.sqrt((width * height) / Math.max(count, 1));
  for (let step = 0; step < 80; step += 1) {
    const cool = 1 - step / 80;
    for (let i = 0; i < count; i += 1) {
      for (let j = i + 1; j < count; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const force = ((k * k) / dist) * 0.06;
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.x += dx;
        a.y += dy;
        b.x -= dx;
        b.y -= dy;
      }
    }
    for (const edge of edges) {
      const a = index.get(edge.source);
      const b = index.get(edge.target);
      if (!a || !b) continue;
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const force = ((dist * dist) / (k * 10)) * 0.035;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      a.x += dx;
      a.y += dy;
      b.x -= dx;
      b.y -= dy;
    }
    for (const node of nodes) {
      node.x += (width / 2 - node.x) * 0.015 * cool;
      node.y += (height / 2 - node.y) * 0.015 * cool;
      node.x = Math.max(56, Math.min(width - 56, node.x));
      node.y = Math.max(32, Math.min(height - 32, node.y));
    }
  }
}
