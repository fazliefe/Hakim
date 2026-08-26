"use client";

import { TYPE_LABEL } from "@/lib/useDocumentAnalysis";
import { StructuredDocument, StructuredField } from "@/lib/api";
import { confidencePct, fieldKey, usefulBbox } from "@/components/document/bbox";

const TABS = [
  { id: "ozet", label: "Özet" },
  { id: "kontrol", label: "Kontrol" },
  { id: "kanit", label: "Kanıt" },
  { id: "gizlilik", label: "Gizlilik" },
  { id: "dosya", label: "Dosya" },
] as const;

const BAND_LABEL: Record<string, string> = {
  trusted: "güvenilir",
  review: "incele",
  uncertain: "belirsiz",
};

function qualityLabel(status: string): string {
  if (status === "good") return "İyi";
  if (status === "unusable") return "Kullanılamaz";
  return "Uyarı";
}

export function EvidencePanel({
  document,
  focused,
  onShow,
  tab,
  onTab,
}: {
  document: StructuredDocument;
  focused: string | null;
  onShow: (field: StructuredField) => void;
  tab: string;
  onTab: (id: string) => void;
}) {
  const typeLabel = TYPE_LABEL[document.document_type] ?? document.document_type;
  const quality = document.quality;

  return (
    <aside className="evidence-panel">
      <header className="evidence-head">
        <span>Belge: {typeLabel}</span>
        <strong>{confidencePct(document.document_type_confidence)}</strong>
      </header>
      <nav className="evidence-tabs" aria-label="Evrak paneli">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "active" : ""}
            onClick={() => onTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {tab === "ozet" ? (
        <div className="evidence-body">
          <p className={`quality-pill ${quality.status}`}>
            Görüntü: {qualityLabel(quality.status)} · {confidencePct(quality.quality_score)}
          </p>
          {document.fields.length ? (
            <ul className="field-list">
              {document.fields.map((field, index) => (
                <li key={fieldKey(field, index)} className={field.band}>
                  <div>
                    <span>{field.label}</span>
                    <strong>{field.value}</strong>
                  </div>
                  <em>
                    {confidencePct(field.confidence)}
                    {field.band !== "trusted" ? ` ⚠ ${BAND_LABEL[field.band]}` : ""}
                  </em>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Henüz alan okunamadı.</p>
          )}
        </div>
      ) : null}

      {tab === "kontrol" ? (
        <div className="evidence-body">
          {document.warnings.length ? (
            <ul className="warn-list">
              {document.warnings.map((item, index) => (
                <li key={`${item.code}-${index}`}>{item.message}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Kalite ve eksik alan uyarısı yok.</p>
          )}
        </div>
      ) : null}

      {tab === "kanit" ? (
        <div className="evidence-body">
          {document.fields.filter((field) => usefulBbox(field.bbox) && field.value !== "[okunamadı]").length ? (
            <ul className="field-list">
              {document.fields
                .filter((field) => usefulBbox(field.bbox) && field.value !== "[okunamadı]")
                .map((field, index) => (
                  <li key={fieldKey(field, index)} className={focused === field.name ? "focused" : ""}>
                    <div>
                      <span>{field.label}</span>
                      <strong>{field.value}</strong>
                    </div>
                    <button type="button" className="show-on-doc" onClick={() => onShow(field)}>
                      Belgede göster
                    </button>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="muted">Görüntüde işaretlenecek alan yok.</p>
          )}
        </div>
      ) : null}

      {tab === "gizlilik" ? (
        <div className="evidence-body">
          {(document.sensitive_regions ?? []).length ? (
            <ul className="warn-list">
              {(document.sensitive_regions ?? []).map((item, index) => (
                <li key={`${item.type}-${index}`}>
                  {item.type === "tckn"
                    ? "T.C. kimlik no"
                    : item.type === "phone"
                      ? "Telefon"
                      : item.type === "iban"
                        ? "IBAN"
                        : item.type === "email"
                          ? "E-posta"
                          : item.type}{" "}
                  izi var. Paylaşmadan gizleyin.
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Paylaşılacak metinde T.C. kimlik, telefon veya IBAN izi yok.</p>
          )}
        </div>
      ) : null}

      {tab === "dosya" ? (
        <div className="evidence-body">
          {(document.attachments ?? []).length ? (
            <ul className="warn-list">
              {(document.attachments ?? []).map((item, index) => (
                <li key={`${item.name ?? "ek"}-${index}`}>
                  {item.name ?? "Ek"} {item.status === "declared" ? "(metinde anılıyor)" : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Bu belgede anılan ek yok. Çoklu paket karşılaştırması ayrı yükleme ister.</p>
          )}
        </div>
      ) : null}
    </aside>
  );
}
