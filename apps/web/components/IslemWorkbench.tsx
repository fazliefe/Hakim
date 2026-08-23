"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { BelgeKalip, getBelgeler } from "@/lib/api";
import { DownloadActions } from "@/components/DownloadActions";
import { useDocumentAnalysis } from "@/lib/useDocumentAnalysis";

const FALLBACK: BelgeKalip[] = [
  { id: "sikayet", title: "Şikayet dilekçesi", when: "Savcılığa şikayet", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "suc_duyurusu", title: "Suç duyurusu", when: "İhbar", makam: "Cumhuriyet Başsavcılığı", legal_basis: [], sections: [] },
  { id: "cevap", title: "Cevap dilekçesi", when: "İddiaya cevap", makam: "Görevli ceza mahkemesi", legal_basis: [], sections: [] },
  { id: "itiraz", title: "İtiraz dilekçesi", when: "CMK m.268", makam: "İtiraz mercii", legal_basis: [], sections: [] },
  { id: "istinaf", title: "İstinaf dilekçesi", when: "CMK m.273", makam: "Bölge Adliye Mahkemesi", legal_basis: [], sections: [] },
  { id: "temyiz", title: "Temyiz dilekçesi", when: "CMK m.291", makam: "Yargıtay", legal_basis: [], sections: [] },
  { id: "katilma", title: "Davaya katılma", when: "CMK m.237", makam: "Ceza mahkemesi", legal_basis: [], sections: [] },
  { id: "bireysel_basvuru", title: "Bireysel başvuru", when: "AYM", makam: "Anayasa Mahkemesi", legal_basis: [], sections: [] },
  { id: "idari_dava", title: "İdari dava dilekçesi", when: "İYUK", makam: "İdare mahkemesi", legal_basis: [], sections: [] },
  { id: "tahliye", title: "Tahliye talebi", when: "Tutukluluk", makam: "Mahkeme / hakimlik", legal_basis: [], sections: [] },
  { id: "adli_kontrol_itiraz", title: "Adli kontrol itirazı", when: "Koruma tedbiri", makam: "İtiraz mercii", legal_basis: [], sections: [] },
];

const SIDE = [
  { id: "yazim", label: "Yazım" },
  { id: "disa-aktar", label: "Dışa aktar" },
];

export function IslemWorkbench() {
  const { text, setText, action, setAction, loading, error, result, submit } = useDocumentAnalysis("/v1/islem");
  const [approved, setApproved] = useState(false);
  const [side, setSide] = useState("yazim");
  const [kalip, setKalip] = useState<BelgeKalip[]>(FALLBACK);

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        const dilekce = rows.filter((item) => item.family !== "kamu");
        if (dilekce.length) setKalip(dilekce);
        else if (rows.length) setKalip(rows);
      })
      .catch(() => setKalip(FALLBACK));
  }, []);

  const selected = useMemo(
    () => kalip.find((item) => item.id === action),
    [kalip, action],
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
              <li className={approved ? "ok" : ""}>Açık onay</li>
            </ul>
            <p className="muted">{result.uyap_note}</p>
            <div className="official-links">
              {result.official_targets.map((target) => (
                <a key={target.url} href={target.url} target="_blank" rel="noreferrer">
                  {target.name}
                </a>
              ))}
            </div>
            <label className="approve">
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
              />
              Taslağı okudum, dışa aktarmayı onaylıyorum
            </label>
            <DownloadActions
              content={result.draft || ""}
              basename={`hakim-dilekce-${action || "taslak"}`}
              disabled={!approved}
            />
          </div>
        ) : (
          <p className="muted">Olayı yazın; uygun dilekçe kalıbı anlatıdan seçilir. UYAP gönderimi yok.</p>
        )
      }
      footer={
        loading
          ? "Taslak yazılıyor…"
          : result
            ? `${selected?.title ?? "Dilekçe"} · onay ${approved ? "var" : "yok"}`
            : "Dilekçe bekleniyor"
      }
    >
      <section className="main-pane islem-pane">
        <div className="pane-hero">
          <h1>{side === "disa-aktar" ? "Dışa aktar" : selected?.title ?? "Dilekçe"}</h1>
          <p>
            {side === "disa-aktar"
              ? "Onay olmadan indirme yok. UYAP’a otomatik gönderim yoktur."
              : selected
                ? `${selected.when} · ${selected.makam}${selected.legal_basis?.length ? ` · ${selected.legal_basis.join(" · ")}` : ""}`
                : "Olayı yazın. Kalıp seçilmezse mevcut yönlendirme kullanılır."}
          </p>
        </div>
        {side !== "disa-aktar" ? (
          <form
            className="islem-compose"
            onSubmit={(event) => {
              setApproved(false);
              return submit(event, action || "");
            }}
          >
            <select
              className="kalip-select"
              aria-label="Dilekçe kalıbı"
              value={action}
              onChange={(event) => {
                setApproved(false);
                setAction(event.target.value);
              }}
            >
              <option value="">Kalıp seçilmedi — anlatıdan</option>
              {kalip.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Olay veya dayanak evrak"
              rows={6}
              spellCheck={false}
              placeholder="Örn. Bankada hesabımdan para çekildi, savcılığa şikayet etmek istiyorum."
            />
            <button type="submit" disabled={loading || text.trim().length < 8}>
              {loading
                ? "Yazılıyor…"
                : action
                  ? `${selected?.title ?? "Taslak"} üret`
                  : "Anla ve uygun dilekçeyi yaz"}
            </button>
          </form>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        {result?.route_reason ? <p className="evrak-verdict">{result.route_reason}</p> : null}
        {result?.gaps?.length && side !== "disa-aktar" ? (
          <aside className="gap-banner">
            <h2>Eksik hususlar</h2>
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
        {side === "disa-aktar" ? (
          <div className="evrak-draft">
            {result?.draft ? (
              <>
                <h2>Dışa aktarım</h2>
                <p className="muted">
                  {approved
                    ? "Onay verildi. Sağ panelden taslağı indirin."
                    : "Önce sağ paneldeki onay kutusunu işaretleyin."}
                </p>
                <pre className="draft-pre">{result.draft}</pre>
              </>
            ) : (
              <p className="muted">Önce olayı yazıp uygun kalıbı üretin.</p>
            )}
          </div>
        ) : result ? (
          <PetitionPreview
            petition={result.petition}
            draft={result.draft}
            badge={selected?.title ?? action}
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
