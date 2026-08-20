"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { BelgeKalip, getBelgeler, writerIsLlm, writerLabel } from "@/lib/api";
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
  { id: "ust_yazi", title: "Üst yazı / havale", when: "Kamu evrakı havalesi", makam: "Evrak kayıt ve havale", legal_basis: [], sections: [] },
  { id: "bilgi_yazisi", title: "Bilgi yazısı", when: "Duyuru / tebliğ", makam: "Bilgi için ilgili birimler", legal_basis: [], sections: [] },
];

export function IslemWorkbench() {
  const { text, setText, action, setAction, loading, error, result, submit } = useDocumentAnalysis(
    "/v1/islem",
  );
  const [approved, setApproved] = useState(false);
  const [side, setSide] = useState("anlat");
  const [kalip, setKalip] = useState<BelgeKalip[]>(FALLBACK);

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        if (rows.length) setKalip(rows);
      })
      .catch(() => setKalip(FALLBACK));
  }, []);

  const selected = useMemo(
    () => kalip.find((item) => item.id === action) ?? kalip.find((item) => item.id === side),
    [kalip, action, side],
  );

  useEffect(() => {
    if (result?.action) setSide(result.action);
  }, [result?.action]);

  const sidebarItems = [
    { id: "anlat", label: "Derdini anlat" },
    ...kalip.map((item) => ({ id: item.id, label: item.title })),
    { id: "disa-aktar", label: "Dışa aktar" },
  ];

  function downloadDraft() {
    if (!result?.draft || !approved) return;
    const blob = new Blob([result.draft], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `hakim-islem-${action}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function onSide(id: string) {
    setSide(id);
    if (id === "disa-aktar") return;
    setApproved(false);
    if (id === "anlat") {
      setAction("");
      return;
    }
    if (result) {
      void submit(undefined, id);
    } else {
      setAction(id);
    }
  }

  return (
    <AppShell
      module="islem"
      sidebarTitle="Belge kalıpları"
      sidebarItems={sidebarItems}
      sidebarActive={side}
      onSidebarSelect={onSide}
      quote="“Onaysız gönderim yoktur.”"
      quoteMeta="vatandas.uyap.gov.tr"
      inspectorTitle="Kontrol listesi"
      inspector={
        result ? (
          <div className="islem-check">
            <ul className="check-list">
              <li className={result.belge ? "ok" : ""}>Kalıp: {selected?.title ?? result.belge ?? action}</li>
              {result.route_reason ? <li className="ok">{result.route_reason}</li> : null}
              {result.gaps?.length ? (
                <li className="gap-item">
                  Şurada eksikliğin var ({result.gaps.length})
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
              <li className={writerIsLlm(result.writer) ? "ok" : ""}>
                Yazıcı: {writerLabel(result.writer)}
              </li>
              {result.writer_error ? <li>{result.writer_error}</li> : null}
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
            <button type="button" className="accent-btn" disabled={!approved} onClick={downloadDraft}>
              Onayla ve dışa aktar
            </button>
          </div>
        ) : (
          <p className="muted">
            Derdinizi yazın; sistem konuyu anlayıp uygun dilekçe kalıbını seçer. UYAP gönderimi yok.
          </p>
        )
      }
      footer={
        loading
          ? "Taslak yazılıyor…"
          : result
            ? `${selected?.title ?? action} · onay ${approved ? "var" : "yok"}`
            : "İşlem bekleniyor"
      }
    >
      <section className="main-pane islem-pane">
        <div className="pane-hero">
          <h1>
            {side === "disa-aktar"
              ? "Dışa aktar"
              : side === "anlat"
                ? "Derdini anlat"
                : selected?.title ?? "İşlem taslağı"}
          </h1>
          <p>
            {side === "disa-aktar"
              ? "Onay olmadan indirme yok. UYAP’a otomatik gönderim yoktur."
              : side === "anlat"
                ? "Olayı kendi cümlelerinizle yazın. Uygun format (şikayet, istinaf, tahliye…) anlatıdan seçilir."
                : selected
                  ? `${selected.when} · ${selected.makam}${selected.legal_basis?.length ? ` · ${selected.legal_basis.join(" · ")}` : ""}`
                  : "Kalıp seçin, derdinizi veya dayanak evrakı yazın."}
          </p>
        </div>
        {side !== "disa-aktar" ? (
          <form
            className="islem-compose"
            onSubmit={(event) => {
              setApproved(false);
              return submit(event, side === "anlat" ? "" : undefined);
            }}
          >
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Dert veya dayanak evrak"
              rows={6}
              spellCheck={false}
              placeholder="Örn. Bankada hesabımdan para çekildi, savcılığa şikayet etmek istiyorum."
            />
            <button type="submit" disabled={loading || text.trim().length < 8}>
              {loading
                ? "Anlaşıyor, kalıp yazılıyor…"
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
            <h2>Şurada eksikliğin var</h2>
            <p>
              Dilekçe yer tutucularla yazıldı. Aşağıdakileri metne ekleyip tekrar «Anla ve uygun dilekçeyi yaz»
              deyin; kimlik ve tarih uydurulmaz.
            </p>
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
            <p className="muted">Önce derdinizi yazıp uygun kalıbı üretin.</p>
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
            Soldan «Derdini anlat» ile olayı yazın; sistem uygun dilekçe formatını seçer. Kalıbı elle de değiştirebilirsiniz.
          </p>
        )}
      </section>
    </AppShell>
  );
}
