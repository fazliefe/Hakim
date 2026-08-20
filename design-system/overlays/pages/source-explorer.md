# Source Explorer Page Overrides

> **PROJECT:** HAKIM
> **Page:** Source Explorer
> Rules here override `design-system/MASTER.md`.

---

## Intent

Read official text the way a lawyer reads a gazette: article list, version timeline, metadata, raw snapshot link.

## Layout

- Left: document outline (articles / paragraphs).
- Center: article text. Historical versions available via a date control.
- Right: metadata — provider, official flag, gazette, content hash, retrieved_at, valid_from / valid_until.

## Versioning UX

- Date control answers “which text was in force on this date?”
- If no version exists for that date, show an empty official state, not a guessed current text.
- Current-in-force version is labeled `Yürürlükte`. Older versions are labeled with their range.

## Typography

- Statute text uses `--font-heading` at 16–18px for article titles and `--font-body` for body.
- Article numbers stay visible while scrolling (sticky subheader, 32px, no shadow).
