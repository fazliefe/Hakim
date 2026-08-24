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

  return (
    <article className={`petition-sheet ${layout}`} data-layout={layout} data-family={family}>
      <header>
        <span>{headerLabel(layout, petition?.title)}</span>
        <span className="badge">{badge || petition?.title}</span>
      </header>
      {actions ? <div className="petition-toolbar">{actions}</div> : null}
      {layout === "resmi" || !petition ? (
        <pre className="draft-pre">{draft}</pre>
      ) : (
        <div className="petition-body">
          <p className="petition-tc">T.C.</p>
          {petition.via ? <p className="petition-via">{petition.via}</p> : null}
          <p className="petition-makam">{petition.hitap}</p>
          {petition.subtitle ? <p className="petition-subtitle">{petition.subtitle}</p> : null}
          {petition.meta?.length ? (
            <dl className="petition-meta">
              {petition.meta.map((row) => (
                <div key={row.label} className="petition-meta-row">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          ) : petition.konu && layout === "dilekce" ? (
            <p className="petition-konu">KONU: {petition.konu}</p>
          ) : null}
          {petition.sections?.map((section) => (
            <section key={section.id} className={`petition-section kind-${section.kind || "prose"}`}>
              <h3>{section.label}</h3>
              <p>{section.text}</p>
            </section>
          ))}
          {petition.closing ? <p className="petition-closing">{petition.closing}</p> : null}
          {petition.signature?.role ? (
            <p className="petition-sign">
              <span>{petition.signature.role}</span>
              <span>{petition.signature.name || "(İmza)"}</span>
            </p>
          ) : null}
          {petition.onay_notu ? <p className="petition-onay">{petition.onay_notu}</p> : null}
        </div>
      )}
    </article>
  );
}

function headerLabel(layout: string, title?: string) {
  if (layout === "resmi") return "Resmî Yazı Önizleme";
  if (layout === "aym") return "Bireysel Başvuru Önizleme";
  if (layout === "idari") return "İdari Dava Önizleme";
  if (layout === "savcilik" || layout === "ihbar") return "Savcılık Yazısı Önizleme";
  return title ? `${title} Önizleme` : "Dilekçe Önizleme";
}
