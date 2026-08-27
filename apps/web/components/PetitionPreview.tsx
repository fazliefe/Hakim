import { ReactNode } from "react";
import { PetitionView } from "@/lib/api";
import { LegalDisclaimer } from "@/components/LegalDisclaimer";

export function PetitionPreview({
  petition,
  draft,
  badge,
  actions,
}: {
  petition?: PetitionView | null;
  draft?: string;
  badge?: string;
  actions?: ReactNode;
}) {
  const layout = petition?.layout || (draft ? "dilekce" : "");
  const family = petition?.family || "ceza";
  const paragraphs = petition?.paragraphs?.length
    ? petition.paragraphs
    : fallbackParagraphs(petition);
  const ekler = petition?.ekler?.length ? petition.ekler : ["—"];
  const adresLines = splitAdres(petition?.adres);

  return (
    <article className={`petition-sheet ${layout}`} data-layout={layout} data-family={family}>
      <header>
        <span>{headerLabel(layout, petition?.title)}</span>
        <span className="badge">{petition?.title || badge}</span>
      </header>
      {actions ? <div className="petition-toolbar">{actions}</div> : null}
      <LegalDisclaimer variant="dilekce" />
      {layout === "resmi" || !petition ? (
        <pre className="draft-pre">{draft}</pre>
      ) : (
        <div className="petition-body petition-classic">
          <p className="petition-tc">T.C.</p>
          {petition.via ? <p className="petition-via">{petition.via}</p> : null}
          <p className="petition-makam">{petition.hitap}</p>
          {petition.sehir ? <p className="petition-city">{petition.sehir}</p> : null}
          {(petition.meta || []).length ? (
            <dl className="petition-meta">
              {(petition.meta || []).map((row) => (
                <div key={`${row.label}-${row.value.slice(0, 24)}`} className="petition-meta-row">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {(petition.sections || [])
            .filter((section) => section.kind !== "eksik" && section.text?.trim())
            .map((section) => (
              <section key={section.id || section.label} className="petition-block">
                {section.label ? <h3 className="petition-heading">{section.label}</h3> : null}
                <p className="petition-prose">{section.text}</p>
              </section>
            ))}
          {!(petition.meta || []).length && !(petition.sections || []).length
            ? paragraphs.map((paragraph, idx) => (
                <p
                  key={`${idx}-${paragraph.slice(0, 24)}`}
                  className={idx === 0 ? "petition-prose indent" : "petition-prose"}
                >
                  {paragraph}
                </p>
              ))
            : null}
          {petition.closing ? <p className="petition-closing">{petition.closing}</p> : null}
          <div className="petition-footer">
            <div className="petition-adres">
              <p>Adres:</p>
              {adresLines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
            <div className="petition-sign">
              {petition.tarih ? <span>{petition.tarih}</span> : null}
              <span>(imza)</span>
              {petition.signature?.role && petition.signature.role !== "(imza)" ? (
                <span>{petition.signature.role}</span>
              ) : null}
              <span>{petition.signature?.name || "«[ad soyad]»"}</span>
            </div>
          </div>
          <div className="petition-ekler">
            <p>EKLER:</p>
            {ekler.map((item, idx) => (
              <p key={`${idx}-${item}`}>
                EK-{idx + 1}  {item}
              </p>
            ))}
          </div>
          {petition.onay_notu ? <p className="petition-onay">{petition.onay_notu}</p> : null}
          {petition.evolver && !petition.evolver.ok ? (
            <p className="petition-evolver">
              Taslak kalite: {(petition.evolver.suggestions || []).join(" ")}
            </p>
          ) : null}
        </div>
      )}
    </article>
  );
}

function splitAdres(adres?: string): string[] {
  const raw = (adres || "«[adres]»").trim();
  const parts = raw.split(/[\n;]+/).map((part) => part.trim()).filter(Boolean);
  return parts.length ? parts : ["«[adres]»"];
}

function fallbackParagraphs(petition?: PetitionView | null): string[] {
  return (petition?.sections || [])
    .filter((section) => section.kind !== "eksik" && section.text?.trim())
    .map((section) => section.text);
}

function headerLabel(layout: string, title?: string) {
  if (layout === "resmi") return "Resmî Yazı Önizleme";
  if (layout === "aym") return "Bireysel Başvuru Önizleme";
  if (layout === "idari") return "İdari Dava Önizleme";
  if (layout === "savcilik" || layout === "ihbar") return "Savcılık Yazısı Önizleme";
  return title ? `${title} Önizleme` : "Dilekçe Önizleme";
}
