"use client";

import { useEffect, useState } from "react";
import { EvidenceOverlay } from "@/components/document/EvidenceOverlay";
import { fieldKey, usefulBbox } from "@/components/document/bbox";
import { StructuredDocument, StructuredField } from "@/lib/api";

export function DocumentViewer({
  document,
  focused,
  onFocus,
  showOverlay = true,
}: {
  document: StructuredDocument;
  focused: string | null;
  onFocus: (name: string | null) => void;
  showOverlay?: boolean;
}) {
  const focusedField = document.fields.find((item) => item.name === focused);
  const [page, setPage] = useState(focusedField?.page ?? document.pages[0]?.page ?? 1);

  useEffect(() => {
    if (focusedField?.page) setPage(focusedField.page);
  }, [focusedField?.page]);

  const current = document.pages.find((item) => item.page === page) ?? document.pages[0];
  const src = current?.preview_jpeg ? `data:image/jpeg;base64,${current.preview_jpeg}` : "";
  const pageFields = document.fields.filter(
    (item: StructuredField) => item.page === (current?.page ?? page) && usefulBbox(item.bbox),
  );

  if (!src) {
    return <p className="muted evrak-hint">Bu sayfa için görüntü önizlemesi yok.</p>;
  }

  return (
    <div className="document-viewer">
      {document.pages.length > 1 ? (
        <div className="document-pages" role="tablist" aria-label="Sayfalar">
          {document.pages.map((item) => (
            <button
              key={item.page}
              type="button"
              className={item.page === page ? "active" : ""}
              onClick={() => setPage(item.page)}
            >
              {item.page}
            </button>
          ))}
        </div>
      ) : null}
      <div className="document-scroll">
        <div className="document-stage">
          {/* preview is a live analyze payload, not a static asset */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={document.filename || "Evrak görüntüsü"} />
          <div className="document-overlays">
            {showOverlay
              ? pageFields.map((field, index) => (
                  <EvidenceOverlay
                    key={fieldKey(field, index)}
                    field={field}
                    active={focused === field.name}
                    onSelect={onFocus}
                  />
                ))
              : null}
          </div>
        </div>
      </div>
    </div>
  );
}
