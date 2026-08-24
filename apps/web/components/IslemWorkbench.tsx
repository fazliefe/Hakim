"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { BelgeKalip, getBelgeler } from "@/lib/api";
import { DownloadActions } from "@/components/DownloadActions";
import { petitionToBlocks } from "@/lib/exportDocument";
import { useDocumentAnalysis } from "@/lib/useDocumentAnalysis";
import { titleCaseLabel } from "@/lib/labels";

const FALLBACK: BelgeKalip[] = [
  { id: "sikayet", title: "Şikayet Dilekçesi", when: "Savcılığa Şikayet", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "suc_duyurusu", title: "Suç Duyurusu", when: "İhbar", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "cevap", title: "Cevap Dilekçesi", when: "İddiaya Cevap", makam: "Görevli Ceza Mahkemesi", legal_basis: [], sections: [] },
  { id: "itiraz", title: "İtiraz Dilekçesi", when: "CMK m.268", makam: "İtiraz Mercii", legal_basis: [], sections: [] },
  { id: "istinaf", title: "İstinaf Dilekçesi", when: "CMK m.273", makam: "Bölge Adliye Mahkemesi", legal_basis: [], sections: [] },
  { id: "temyiz", title: "Temyiz Dilekçesi", when: "CMK m.291", makam: "Yargıtay", legal_basis: [], sections: [] },
  { id: "katilma", title: "Davaya Katılma", when: "CMK m.237", makam: "Ceza Mahkemesi", legal_basis: [], sections: [] },
  { id: "bireysel_basvuru", title: "Bireysel Başvuru", when: "AYM", makam: "Anayasa Mahkemesi", legal_basis: [], sections: [] },
  { id: "idari_dava", title: "İdari Dava Dilekçesi", when: "İYUK", makam: "İdare Mahkemesi", legal_basis: [], sections: [] },
  { id: "tahliye", title: "Tahliye Talebi", when: "Tutukluluk", makam: "Mahkeme / Hakimlik", legal_basis: [], sections: [] },
  { id: "adli_kontrol_itiraz", title: "Adli Kontrol İtirazı", when: "Koruma Tedbiri", makam: "İtiraz Mercii", legal_basis: [], sections: [] },
];

const SIDE = [{ id: "yazim", label: "Yazım" }];

export function IslemWorkbench() {
  const { text, setText, action, setAction, loading, error, result, submit } = useDocumentAnalysis("/v1/islem");
  const [side, setSide] = useState("yazim");
  const [kalip, setKalip] = useState<BelgeKalip[]>(FALLBACK);

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        const dilekce = rows.filter((item) => item.family !== "kamu");
        const titled = (rows: BelgeKalip[]) =>
          rows.map((item) => ({ ...item, title: titleCaseLabel(item.title) }));
        if (dilekce.length) setKalip(titled(dilekce));
        else if (rows.length) setKalip(titled(rows));
      })
      .catch(() => setKalip(FALLBACK));
  }, []);

  const selected = useMemo(
    () => kalip.find((item) => item.id === action),
    [kalip, action],
  );
  const petitionReady = Boolean(
    result?.petition &&
      result.petition.layout !== "resmi" &&
      (result.petition.hitap || result.petition.sections?.length || result.petition.konu),
  );
  const petitionBlocks = petitionReady && result?.petition ? petitionToBlocks(result.petition) : undefined;
  const downloadBody = result?.draft || "";
  const downloadName = `hakim-dilekce-${action || selected?.id || "taslak"}`;
  const downloads = (
    <DownloadActions
      content={downloadBody}
      blocks={petitionBlocks}
      basename={downloadName}
      disabled={!petitionBlocks?.length && !downloadBody}
    />
  );

  return (
    <AppShell
      module="islem"
      sidebarTitle="Dilekçe"
      sidebarItems={SIDE}
      sidebarActive={side}
      onSidebarSelect={setSide}
      inspectorTitle="Kontrol"
      inspector={
        result ? (
          <div className="islem-check">
            <ul className="check-list">
              <li className={result.belge ? "ok" : ""}>Kalıp: {selected?.title ?? result.belge ?? "anlatıdan"}</li>
              {result.route_reason ? <li className="ok">{result.route_reason}</li> : null}
              {result.gaps?.length ? (
                <li className="gap-item">
                  Eksik ({result.gaps.length})
                  <ul className="gap-mini">
                    {result.gaps.map((gap) => (
                      <li key={gap.id}>
                        {gap.label}: {gap.hint}
                      </li>
                    ))}
                  </ul>
                </li>
              ) : (
                <li className="ok">Anlatım yeterli</li>
              )}
              <li className={result.related.length ? "ok" : ""}>Kaynak doğrulandı ({result.related.length})</li>
              <li className={result.classification.document_type !== "belirsiz" ? "ok" : ""}>Evrak türü</li>
              <li className={result.draft ? "ok" : ""}>Taslak hazır</li>
            </ul>
            <p className="muted">{result.uyap_note}</p>
            <div className="official-links">
              {result.official_targets.map((target) => (
                <a key={target.url} href={target.url} target="_blank" rel="noreferrer">
                  {target.name}
                </a>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted">Olayı yazın; uygun dilekçe kalıbı anlatıdan seçilir. UYAP gönderimi yok.</p>
        )
      }
      footer={
        loading
          ? "Taslak Yazılıyor…"
          : result
            ? `${selected?.title ?? "Dilekçe"}`
            : "Dilekçe Bekleniyor"
      }
    >
      <section className="main-pane islem-pane">
        <div className="pane-hero">
          <h1>{selected?.title ?? "Dilekçe"}</h1>
          <p>
            {selected
              ? `${selected.when} · ${selected.makam}${selected.legal_basis?.length ? ` · ${selected.legal_basis.join(" · ")}` : ""}`
              : "Olayı yazın. Kalıp seçilmezse mevcut yönlendirme kullanılır."}
          </p>
        </div>
        <form
          className="islem-compose"
          onSubmit={(event) => submit(event, action || "")}
        >
          <select
            className="kalip-select"
            aria-label="Dilekçe Kalıbı"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          >
            <option value="">Kalıp Seçilmedi — Anlatıdan</option>
            {kalip.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Olay veya Dayanak Evrak"
            rows={6}
            spellCheck={false}
            placeholder="Örn. Bankada hesabımdan para çekildi, savcılığa şikayet etmek istiyorum."
          />
          <div className="islem-compose-actions">
            <button type="submit" disabled={loading || text.trim().length < 8}>
              {loading
                ? "Yazılıyor…"
                : action
                  ? `${selected?.title ?? "Taslak"} Üret`
                  : "Anla ve Uygun Dilekçeyi Yaz"}
            </button>
            {downloads}
          </div>
        </form>
        {error ? <p className="error">{error}</p> : null}
        {result?.route_reason ? <p className="evrak-verdict">{result.route_reason}</p> : null}
        {result?.gaps?.length ? (
          <aside className="gap-banner">
            <h2>Eksik Hususlar</h2>
            <p>Dilekçe yer tutucularla yazıldı. Kimlik ve tarih uydurulmaz.</p>
            <ul>
              {result.gaps.map((gap) => (
                <li key={gap.id}>
                  <strong>{gap.label}</strong>
                  {gap.hint}
                </li>
              ))}
            </ul>
          </aside>
        ) : null}
        {result ? (
          <PetitionPreview
            petition={result.petition}
            draft={result.draft}
            badge={selected?.title ?? action}
            actions={downloads}
          />
        ) : (
          <p className="muted islem-empty">
            Olayı yazın. Kalıbı üstteki listeden de seçebilirsiniz.
          </p>
        )}
      </section>
    </AppShell>
  );
}
