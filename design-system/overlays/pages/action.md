# Action Page Overrides

> **PROJECT:** HAKIM
> **Page:** İşlem
> Rules here override `design-system/MASTER.md`.

---

## Intent

v1 produces a petition/document, validates required fields and citations, exports DOCX/PDF, then waits for user approval. It does not call UYAP.

## Layout

- Center: document editor / preview with required-field markers.
- Right: checklist — sources verified, mandatory fields, export, approval.
- Accent button is only `Onayla ve dışa aktar`. Secondary: `DOCX`, `PDF`.

## Trust

- Every generated paragraph that states law must keep a citation chip.
- Unverified fields block export. The block reason is inline, not a toast-only error.
- Approval is explicit. No auto-send copy.

## Anti-patterns for this page

- No “magic generate” full-bleed gradient button.
- No fake UYAP success states.
- No hidden download.
