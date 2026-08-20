# Graph Page Overrides

> **PROJECT:** HAKIM
> **Page:** Knowledge Graph
> Rules here override `design-system/MASTER.md`.

---

## Intent

Graph is a retrieval signal and an explanation view, not a toy visualization. Use Sigma.js + Graphology. Keep it readable at article/decision density.

## Visual rules

- Nodes: law, article, decision, concept — distinguished by shape, not neon color.
- Official edges: solid, `--color-primary`.
- LLM-extracted edges: dashed, lower opacity, confidence label on hover/inspect.
- Selected node: 2px ring using `--color-ring`. No bloom.
- Background matches `--color-background`. No dark-web / cyber grid.

## Inspector

Clicking a node opens the source inspector with canonical id, validity range, provenance, and “used in answer”.

## Motion

Pan/zoom only. No orbit, no particle effects, no auto-layout thrashing after the first settle.
