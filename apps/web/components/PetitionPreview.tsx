import { ReactNode } from "react";
import { PetitionView } from "@/lib/api";

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
      {layout === "resmi" || !petition ? (
        <pre className="draft-pre">{draft}</pre>
      ) : (
        <div className="petition-body petition-classic">
          <p className="petition-tc">T.C.</p>
          {petition.via ? <p className="petition-via">{petition.via}</p> : null}
          <p className="petition-makam">{petition.hitap}</p>
          {petition.sehir ? <p className="petition-city">{petition.sehir}</p> : null}
          {paragraphs.map((paragraph, idx) => (
            <p
              key={`${idx}-${paragraph.slice(0, 24)}`}
              className={idx === 0 ? "petition-prose indent" : "petition-prose"}
            >
              {paragraph}
            </p>
          ))}
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
  if (layout === "resmi") return "Resmî yazı önizleme";
  if (layout === "aym") return "Bireysel başvuru önizleme";
  if (layout === "idari") return "İdari dava önizleme";
  if (layout === "savcilik" || layout === "ihbar") return "Savcılık yazısı önizleme";
  return title ? `${title} önizleme` : "Dilekçe önizleme";
}
