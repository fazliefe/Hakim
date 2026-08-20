# Process Page Overrides

> **PROJECT:** HAKIM
> **Page:** Süreç
> Rules here override `design-system/MASTER.md`.

---

## Intent

Show procedure stage, available remedies, and **deterministically computed deadlines**. The LLM does not calculate time. The deadline engine does.

## Layout

- Center: vertical stage map (current stage emphasized, not animated).
- Right: for each remedy — conditions, trigger date, duration, calendar, computed last day, legal basis.
- Computed dates use tabular numbers. Missed deadlines use `--color-destructive`.

## Copy rules

- Always show the legal basis article IDs next to the duration.
- Never phrase a deadline as “probably” or “around”.
- If the engine cannot compute, show `Hesaplanamadı` plus the missing input (trigger date, notification, etc.).

## Components

- **Deadline card:** trigger, duration + unit, calendar type, last day, basis.
- **Stage list:** past / current / next. Current is a left border in `--color-primary`, not a glow.
