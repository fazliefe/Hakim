"use client";

import { ConfidenceBand, StructuredField } from "@/lib/api";
import { bboxCss, usefulBbox } from "@/components/document/bbox";

export function EvidenceOverlay({
  field,
  active,
  onSelect,
}: {
  field: StructuredField;
  active: boolean;
  onSelect: (name: string) => void;
}) {
  if (field.band === "uncertain" || !usefulBbox(field.bbox)) return null;
  const band: ConfidenceBand = field.band;
  return (
    <button
      type="button"
      className={`evidence-box ${band}${active ? " active" : ""}`}
      style={bboxCss(field.bbox)}
      title={`${field.label}: ${field.value}`}
      aria-label={`${field.label} belgede göster`}
      onClick={() => onSelect(field.name)}
    />
  );
}
