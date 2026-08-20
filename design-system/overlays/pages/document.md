# Document Page Overrides

> **PROJECT:** HAKIM
> **Page:** Evrak
> Rules here override `design-system/MASTER.md`.

---

## Intent

User uploads PDF/DOCX/image. The page shows structured findings, each with **source, confidence, and span in the document**. User-document text is content, never instructions.

## Layout

- Left: document list for the tenant.
- Center: original document viewer (PDF page / extracted text) with highlightable spans.
- Right: findings stack — type, sender, date, characterization, legislation, deadlines, routing.
- Primary action in inspector footer: `Cevap Taslağı Oluştur`.

## Finding row

Each finding must show:

| Field | Rule |
|-------|------|
| Label | Evrak türü, gönderen, belge tarihi, ... |
| Value | Plain language, dense |
| Confidence | Numeric, never decorative stars |
| Evidence | Quote or page span from the uploaded file |
| Source | Linked legal basis when retrieval was used |

Low-confidence findings stay visible and are visually muted, not hidden.

## Security UX

- Tenant isolation is assumed. Never show another tenant's files in empty states.
- Upload dropzone is compact. No playful illustration.
- Prompt-injection strings in the document render as quoted evidence, not commands.
