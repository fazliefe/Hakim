# Research Page Overrides

> **PROJECT:** HAKIM
> **Page:** Araştırma
> Rules here override `design-system/MASTER.md`.

---

## Intent

This is the first product surface. A lawyer asks a legal question and must see **answer + sources + graph + retrieval trace** without leaving the workspace.

Chat is the query box. It is not the page.

## Layout

- Full-height three-pane workspace. Do not center a 1200px marketing column.
- Center: compact query field at top, answer below with inline citation markers `[1]`.
- Right inspector: official sources, article numbers, court docket, “Kaynağa Git”.
- Bottom tabs: `Metin | Kaynaklar | Graph | Retrieval Trace`.

## Content density

- Answer typography: body 14–15px, line-height 1.5, citation chips 12px.
- Source cards are list rows, not large marketing cards.
- No hero, no empty-state illustration, no gradient orb.

## Components unique to this page

- **Query bar:** single-line input, placeholder `Hukuki sorunuzu yazın...`
- **Citation marker:** monospace `[n]`, click selects that source in the inspector.
- **Source row:** law number, article, validity range, authority badge (`official`).
- **Retrieval trace graph:** query → BM25 / vector / graph → RRF → rerank → answer.
  Node click shows retriever, ranks, graph distance, authority, used-in-answer.

## Motion

None except 150ms inspector highlight when a citation is selected. No scroll-reveal on the answer.
