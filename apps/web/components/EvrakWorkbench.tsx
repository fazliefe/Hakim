"use client";

import dynamic from "next/dynamic";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AgentRail } from "@/components/AgentRail";
import { AppShell } from "@/components/AppShell";
import { DocumentViewer } from "@/components/document/DocumentViewer";
import { PetitionPreview } from "@/components/PetitionPreview";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { EVRAK_THINK_STEPS, ThinkingHops } from "@/components/ThinkingHops";
import { BelgeKalip, analyzeWorkspace, getBelgeler } from "@/lib/api";
import { DownloadActions } from "@/components/DownloadActions";
import { petitionToBlocks } from "@/lib/exportDocument";
import { calendarLabel, durationUnitLabel, formatTurkishDate } from "@/lib/labels";
import { KAMU_FALLBACK } from "@/lib/kamuSamples";
import { FIELD_LABEL, NATURE_LABEL, SAMPLE_EVRAK, STAGE_LABEL, useDocumentAnalysis } from "@/lib/useDocumentAnalysis";

const DocumentTraceGraphView = dynamic(
  () => import("@/components/graph/DocumentTraceGraphView").then((mod) => mod.DocumentTraceGraphView),
  { ssr: false },
);

const SIDE = [
  { id: "goruntuleme", label: "Evrak Görüntüleme" },
  { id: "sinif", label: "Sınıflandırma" },
  { id: "akil", label: "Akıl Yürütme" },
  { id: "usul", label: "Kanun Yolu ve Süreler" },
  { id: "kaynak", label: "Kaynak Grafiği" },
  { id: "taslaklar", label: "Taslaklar" },
];

const FILE_ACCEPT =
  ".pdf,.txt,.md,.docx,.doc,.jpg,.jpeg,.png,.webp,.tif,.tiff,application/pdf,text/plain,image/jpeg,image/png,image/webp,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const REMEDY_LABEL: Record<string, string> = {
  itiraz: "İtiraz",
  istinaf: "İstinaf",
  temyiz: "Temyiz",
  istinaf_ceza: "İstinaf",
  temyiz_ceza: "Temyiz",
  istinaf_hukuk: "İstinaf (Hukuk)",
  temyiz_hukuk: "Temyiz (Hukuk)",
  bireysel_basvuru: "Bireysel Başvuru",
  idari_dava: "İdari Dava",
  istinaf_idari: "İdari İstinaf",
  temyiz_idari: "İdari Temyiz",
  sikayet: "Şikayet",
};

export function EvrakWorkbench() {
  const params = useSearchParams();
  const initialSide = SIDE.some((item) => item.id === params.get("bolum")) ? params.get("bolum")! : "goruntuleme";
  const { text, setText, loading, error, result, setResult, submit, submitFile, submitSenaryo, fileName, structured } =
    useDocumentAnalysis("/v1/evrak");
  const [side, setSide] = useState(initialSide);
  const [kalipList, setKalipList] = useState<BelgeKalip[]>(KAMU_FALLBACK);
  const [kalip, setKalip] = useState(params.get("kalip") ?? "");
  const [picked, setPicked] = useState(0);
  const [surecLoading, setSurecLoading] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState<number | null>(null);
  const today = new Date().toISOString().slice(0, 10);
  const c = result?.classification;
  const deadlines = result?.deadlines ?? [];
  const selectedDeadline = deadlines[picked] ?? deadlines[0] ?? null;
  const selectedKalip = useMemo(
    () => kalipList.find((item) => item.id === kalip),
    [kalipList, kalip],
  );

  useEffect(() => {
    getBelgeler()
      .then((rows) => {
        const resmi = rows.filter((item) => item.family === "kamu");
        if (resmi.length) setKalipList(resmi);
      })
      .catch(() => setKalipList(KAMU_FALLBACK));
  }, []);

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void submitFile(file);
  }

  async function loadUsul() {
    if (text.trim().length < 8) return;
    setSurecLoading(true);
    try {
      const data = await analyzeWorkspace("/v1/surec", text.trim());
      setResult((prev) =>
        prev
          ? { ...prev, deadlines: data.deadlines, stages: data.stages, classification: data.classification }
          : data,
      );
    } finally {
      setSurecLoading(false);
    }
  }

  const downloadBody = result?.draft || text;
  const downloadName = result?.draft
    ? `hakim-taslak-${result.belge ?? result.action ?? "evrak"}`
    : fileName?.replace(/\.[^.]+$/, "") || "hakim-evrak";

  return (
    <AppShell
      module="evrak"
      sidebarTitle="Evrak"
      sidebarItems={SIDE}
      sidebarActive={side}
      onSidebarSelect={setSide}
      inspectorMode="hidden"
      footer={
        loading || surecLoading
          ? "Evrak Okunuyor…"
          : result
            ? `${result.classification.label} · ${result.deadlines.length} süre`
            : structured
              ? `${structured.document_type} · görüntü`
              : "Evrak Bekleniyor"
      }
    >
      <section className="main-pane evrak-pane">
        <div className="pane-hero">
          <h1>
            {side === "goruntuleme"
              ? "Evrak Görüntüleme"
              : side === "sinif"
                ? "Sınıflandırma"
                : side === "akil"
                  ? "Akıl Yürütme"
                  : side === "usul"
                    ? "Kanun Yolu ve Süreler"
                    : side === "kaynak"
                      ? "Kaynak Grafiği"
                      : "Taslaklar"}
          </h1>
          <p>
            {side === "goruntuleme"
              ? "Solda belge, sağda VLM’in yazıya çevirdiği metin. PDF/Word hâlâ tek metin kutusu."
              : side === "sinif"
                ? "Türü, niteliği ve birimi."
                : side === "akil"
                  ? "Çözümlemeden sonra adımlar burada durur."
                  : side === "usul"
                    ? "Aşama, kanun yolu ve son gün — süre motoru."
                    : side === "kaynak"
                      ? "Taslağın hangi maddeye dayandığı — okuyucudan havaleye zincir + atıf edilen mevzuat."
                      : "Kaynaklı taslak. Word veya PDF indirin."}
          </p>
        </div>
        {error ? <p className="error" style={{ padding: "0 0.9rem" }}>{error}</p> : null}
        {loading && side === "goruntuleme" ? <ThinkingHops steps={EVRAK_THINK_STEPS} /> : null}

        {side === "goruntuleme" ? (
          <>
            <div className={`evrak-desk ${structured ? "photo-split" : "single"}`}>
              {structured ? (
                <section className="doc-sheet photo-pane" aria-label="Yüklenen belge">
                  <header className="sheet-head">
                    <span>Belge</span>
                    <em className="muted">{fileName}</em>
                  </header>
                  <DocumentViewer document={structured} focused={null} onFocus={() => undefined} showOverlay={false} />
                </section>
              ) : null}
              <form className="doc-sheet text-pane" onSubmit={submit}>
                <header className="sheet-head">
                  <span>{structured ? "Yazıya çevrilmiş" : fileName ? fileName : "Asıl Metin"}</span>
                  <div className="sheet-actions">
                    <select
                      className="kalip-select"
                      aria-label="Resmi Yazışma Kalıbı"
                      value={kalip}
                      onChange={(event) => setKalip(event.target.value)}
                    >
                      <option value="">Kalıp Seçilmedi</option>
                      {kalipList.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.title}
                        </option>
                      ))}
                    </select>
                    <label className="file-btn">
                      Dosya yükle
                      <input
                        type="file"
                        accept={FILE_ACCEPT}
                        onChange={onFile}
                        disabled={loading}
                      />
                    </label>
                    <label className="file-btn">
                      Fotoğrafı yazıya çevir
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/tiff,.jpg,.jpeg,.png,.webp,.tif,.tiff"
                        onChange={onFile}
                        disabled={loading}
                      />
                    </label>
                    <button type="submit" disabled={loading || text.trim().length < 8}>
                      {loading ? "Okunuyor…" : "Çözümle"}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={loading || text.trim().length < 8}
                      onClick={() => {
                        void submitSenaryo(kalip || undefined).then((ok) => {
                          if (ok) setSide("taslaklar");
                        });
                      }}
                    >
                      Taslak Üret
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={loading}
                      onClick={() => setText(SAMPLE_EVRAK)}
                    >
                      Örnek Metni Yükle
                    </button>
                    <DownloadActions content={downloadBody} basename={downloadName} />
                  </div>
                </header>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  aria-label="Evrak Metni"
                  placeholder="Fotoğraf yüklerseniz tüm sayfa sağda yazılır. PDF/Word de yükleyebilir, metni yapıştırabilirsiniz…"
                  spellCheck={false}
                />
                {structured?.warnings?.length ? (
                  <ul className="evrak-checks" aria-label="Kontrol notları">
                    {structured.warnings.map((item, index) => (
                      <li key={`${item.code}-${index}`}>{item.message}</li>
                    ))}
                  </ul>
                ) : null}
              </form>
            </div>
          </>
        ) : null}

        {side === "akil" ? (
          <div style={{ padding: "0 0.9rem 1rem" }}>
            <AgentRail agents={result?.agents} />
            <ReasoningPanel reasoning={result?.reasoning} />
          </div>
        ) : null}

        {side === "sinif" ? (
          c ? (
            <div className="class-grid" style={{ padding: "0 0.9rem 1rem" }}>
              {result?.verdict ? (
                <div className="class-card wide">
                  <span>Ne Olduğu</span>
                  <strong>{result.verdict}</strong>
                </div>
              ) : null}
              {result?.legal_caveat ? (
                <p className="legal-caveat class-card wide">⚖ {result.legal_caveat}</p>
              ) : null}
              <div className="class-card">
                <span>Tür</span>
                <strong>{c.label}</strong>
              </div>
              <div className="class-card">
                <span>Nitelik</span>
                <strong>{NATURE_LABEL[c.legal_nature] ?? c.legal_nature}</strong>
              </div>
              <div className="class-card">
                <span>Aşama</span>
                <strong>{STAGE_LABEL[c.stage] ?? c.stage}</strong>
              </div>
              <div className="class-card wide">
                <span>Birim</span>
                <strong>{c.unit}</strong>
              </div>
              {Object.entries(result?.fields ?? {}).map(([key, value]) => (
                <div key={key} className="class-card">
                  <span>{FIELD_LABEL[key] ?? key}</span>
                  <strong>{value}</strong>
                </div>
              ))}
              {result?.missing?.length ? (
                <div className="class-card wide">
                  <span>Eksik Alan</span>
                  <strong>{result.missing.join(" · ")}</strong>
                </div>
              ) : null}
              {result?.findings.map((item) => (
                <div key={`${item.label}-${item.value}`} className="class-card wide">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted evrak-hint">Önce evrak görüntülemeden dosya yükleyin veya çözün.</p>
          )
        ) : null}

        {side === "usul" ? (
          <div style={{ padding: "0 0.9rem 1rem" }}>
            {!result?.stages?.length && !deadlines.length ? (
              <>
                <p className="muted evrak-hint">Aynı evrak metninden aşama ve süreler hesaplanır.</p>
                <button
                  type="button"
                  className="accent-btn"
                  disabled={surecLoading || text.trim().length < 8}
                  onClick={() => void loadUsul()}
                >
                  {surecLoading ? "Hesaplanıyor…" : "Süreleri Hesapla"}
                </button>
              </>
            ) : (
              <>
                {result?.stages?.length ? (
                  <ol className="stage-rail">
                    {result.stages.map((stage) => (
                      <li key={stage.id} className={stage.state}>
                        <i />
                        <span>{stage.title}</span>
                      </li>
                    ))}
                  </ol>
                ) : null}
                <div className="deadline-board">
                  {(c?.remedies?.length ? c.remedies : []).map((remedy) => (
                    <div key={remedy} className="deadline-tile">
                      <span>Kanun Yolu</span>
                      <strong>{REMEDY_LABEL[remedy] ?? remedy}</strong>
                      <em>{c?.label}</em>
                    </div>
                  ))}
                  {deadlines.map((item, index) => {
                    const late = Boolean(item.last_day && item.last_day < today);
                    return (
                      <button
                        key={item.rule_id}
                        type="button"
                        className={`deadline-tile ${picked === index ? "selected" : ""} ${late ? "missed" : ""}`}
                        onClick={() => setPicked(index)}
                      >
                        <span>{item.name}</span>
                        <strong className="tabular">{formatTurkishDate(item.last_day)}</strong>
                        <em>
                          {item.duration} {durationUnitLabel(item.unit)}
                          {late ? " · geçti" : ""}
                        </em>
                      </button>
                    );
                  })}
                </div>
                {selectedDeadline ? (
                  <div className={`deadline-card ${selectedDeadline.last_day && selectedDeadline.last_day < today ? "missed" : ""}`}>
                    <strong>{selectedDeadline.name}</strong>
                    <p className="muted">
                      {selectedDeadline.duration} {durationUnitLabel(selectedDeadline.unit)}
                      {calendarLabel(selectedDeadline.calendar) ? ` · ${calendarLabel(selectedDeadline.calendar)}` : ""}
                    </p>
                    <p>Tetikleyici: {selectedDeadline.trigger ?? "yok"}</p>
                    <p>Son gün: {formatTurkishDate(selectedDeadline.last_day)}</p>
                    {selectedDeadline.missing ? <p>Eksik: {selectedDeadline.missing}</p> : null}
                    {selectedDeadline.legal_basis.length ? (
                      <p className="muted">{selectedDeadline.legal_basis.join(" · ")}</p>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        {side === "kaynak" ? (
          result?.trace_nodes?.length ? (
            <div style={{ padding: "0 0.9rem 1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div style={{ height: "380px" }}>
                <DocumentTraceGraphView
                  nodes={result.trace_nodes}
                  edges={result.trace_edges ?? []}
                  evidence={result.related}
                  selected={selectedEvidence}
                  onSelect={setSelectedEvidence}
                />
              </div>
              {result.related.length ? (
                <div className="source-stack">
                  {result.related.map((item) => (
                    <button
                      key={item.chunk_id}
                      type="button"
                      className={`source-row ${selectedEvidence === item.n ? "selected" : ""}`}
                      onClick={() => setSelectedEvidence(item.n)}
                    >
                      {item.mulga_warning ? "⚠ " : ""}[{item.n}] {item.law_no ? `K.${item.law_no} m.${item.article_no}` : item.title}
                    </button>
                  ))}
                  {(() => {
                    const selectedItem = result.related.find((item) => item.n === selectedEvidence);
                    if (!selectedItem) return null;
                    return (
                      <article className="source-detail">
                        <div className="source-meta">
                          <span>
                            {selectedItem.law_no ? `K.${selectedItem.law_no} m.${selectedItem.article_no}` : selectedItem.title}
                          </span>
                          <span className="badge">{selectedItem.authority || "resmi"}</span>
                        </div>
                        <div className="source-title">{selectedItem.title || "Başlıksız madde"}</div>
                        <p className="source-content">{selectedItem.content}</p>
                        {selectedItem.mulga_warning ? <p className="error">⚠ {selectedItem.mulga_warning}</p> : null}
                        {selectedItem.graph_neighbors?.length ? (
                          <p className="muted">
                            Komşu madde:{" "}
                            {selectedItem.graph_neighbors
                              .slice(0, 3)
                              .map((n) => (n.article_no ? `m.${n.article_no}` : n.title))
                              .join(", ")}
                          </p>
                        ) : null}
                      </article>
                    );
                  })()}
                </div>
              ) : (
                <p className="muted evrak-hint">Bu evrak için eşleşen mevzuat bulunamadı.</p>
              )}
            </div>
          ) : (
            <p className="muted evrak-hint">Önce evrak görüntülemeden dosya yükleyin veya çözün.</p>
          )
        ) : null}

        {side === "taslaklar" ? (
          result?.draft ? (
            <div style={{ padding: "0 0.9rem 1rem" }}>
              {result.legal_caveat ? (
                <p className="legal-caveat" style={{ marginBottom: "0.7rem" }}>
                  ⚖ {result.legal_caveat}
                </p>
              ) : null}
              <div className="sheet-actions" style={{ marginBottom: "0.7rem" }}>
                <DownloadActions
                  content={result.draft}
                  blocks={
                    result.petition && result.petition.layout !== "resmi" && (result.petition.hitap || result.petition.sections?.length)
                      ? petitionToBlocks(result.petition)
                      : undefined
                  }
                  basename={downloadName}
                />
                {selectedKalip ? <span className="muted">{selectedKalip.title}</span> : null}
              </div>
              {result.petition ? (
                <PetitionPreview
                  petition={result.petition}
                  draft={result.draft}
                  badge={result.belge ?? result.action}
                />
              ) : (
                <article className="evrak-draft">
                  <h2>Cevap Taslağı</h2>
                  {result.havale ? (
                    <p className="muted">Havale: {result.havale.unit}. {result.havale.note}</p>
                  ) : null}
                  <pre className="draft-pre">{result.draft}</pre>
                </article>
              )}
            </div>
          ) : (
            <p className="muted evrak-hint">Henüz taslak yok. Görüntülemede «Taslak Üret» deyin.</p>
          )
        ) : null}
      </section>
    </AppShell>
  );
}
