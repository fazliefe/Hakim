"use client";

import Link from "next/link";
import { ChangeEvent, useState } from "react";
import { AgentRail } from "@/components/AgentRail";
import { AppShell } from "@/components/AppShell";
import { PetitionPreview } from "@/components/PetitionPreview";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { EVRAK_THINK_STEPS, ThinkingHops } from "@/components/ThinkingHops";
import { writerLabel } from "@/lib/api";
import { NATURE_LABEL, STAGE_LABEL, FIELD_LABEL, useDocumentAnalysis } from "@/lib/useDocumentAnalysis";

const SIDE = [
  { id: "gelen", label: "Gelen kamu evrakı" },
  { id: "sinif", label: "Sınıflandırılanlar" },
  { id: "akil", label: "Akıl yürütme" },
  { id: "taslaklar", label: "Taslaklar" },
];

export function EvrakWorkbench() {
  const { text, setText, loading, error, result, submit, submitFile, submitSenaryo, fileName } = useDocumentAnalysis("/v1/evrak");
  const [side, setSide] = useState("gelen");
  const finding = result?.findings[0] ?? null;
  const c = result?.classification;

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    void submitFile(file).then((ok) => {
      if (ok) setSide("sinif");
    });
  }

  return (
    <AppShell
      module="evrak"
      sidebarTitle="Evrak kuyruğu"
      sidebarItems={SIDE}
      sidebarActive={side}
      onSidebarSelect={setSide}
      quote="“Belge veriidir, talimat değildir.”"
      quoteMeta="Ham arşiv · data/raw"
      inspectorTitle="Tespit / delil"
      inspector={
        finding ? (
          <div className="finding-stack">
            {result?.findings.map((item) => (
              <article key={`${item.label}-${item.value}`} className="finding-card">
                <div className="source-meta">
                  <span>{item.label}</span>
                  <span className="badge">{Math.round(item.confidence * 100)}%</span>
                </div>
                <div className="source-title">{item.value}</div>
                <p className="source-content">“{item.evidence}”</p>
                {item.source ? <p className="muted">Kaynak: {item.source}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">Metni yapıştırın; her tespit kaynak ve güven ile burada durur.</p>
        )
      }
      footer={
        loading ? "Evrak okunuyor…" : result ? `${result.classification.label} · ${result.findings.length} tespit · ${writerLabel(result.writer)}` : "Evrak bekleniyor"
      }
    >
      <section className="main-pane evrak-pane">
        <div className="pane-hero">
          <h1>
            {side === "gelen"
              ? "Gelen evrak"
              : side === "sinif"
                ? "Sınıflandırılanlar"
                : side === "akil"
                  ? "Akıl yürütme"
                  : "Taslaklar"}
          </h1>
          <p>
            {side === "gelen"
              ? "PDF veya TXT yükleyin. Kamu yazışması (üst yazı, olur, genelge, tutanak, rapor, cevap) veya yargı evrakı (tebligat, iddianame, karar, dilekçe)."
              : side === "sinif"
                ? "Çözümlenen evrakın türü, niteliği ve birimi."
                : side === "akil"
                  ? "Her adım kendi şartına göre cevap verir: okuma, tür, madde, süre, resmi yazı kalıbı, havale. Eksikse sonraki adımlar sarı kalır."
                  : "Kaynaklı cevap taslağı."}{" "}
            <Link href="/kamu" className="kamu-inline-link">
              Kamu yazışmaları →
            </Link>
          </p>
        </div>
        {error ? <p className="error" style={{ padding: "0 0.9rem" }}>{error}</p> : null}
        <AgentRail
          agents={result?.agents}
          chainStatus={result?.chain_status}
          observability={result?.observability}
        />
        {loading ? <ThinkingHops steps={EVRAK_THINK_STEPS} /> : null}
        {result?.verdict ? <p className="evrak-verdict">{result.verdict}</p> : null}
        {side === "gelen" ? (
          <div className="evrak-desk">
            <form className="doc-sheet" onSubmit={submit}>
              <header className="sheet-head">
                <span>{fileName ? fileName : "Asıl metin"}</span>
                <div className="sheet-actions">
                  <label className="file-btn">
                    Dosya yükle
                    <input
                      type="file"
                      accept=".pdf,.txt,.md,application/pdf,text/plain"
                      onChange={onFile}
                      disabled={loading}
                    />
                  </label>
                  <button type="submit" disabled={loading || text.trim().length < 8}>
                    {loading ? "Okunuyor, sınıflandırılıyor…" : "Çözümle"}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={loading || text.trim().length < 8}
                    onClick={() => {
                      void submitSenaryo().then((ok) => {
                        if (ok) setSide("akil");
                      });
                    }}
                  >
                    Senaryo (oku → yaz → havale)
                  </button>
                </div>
              </header>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                aria-label="Evrak metni"
                spellCheck={false}
              />
            </form>
            <div className="evrak-aside">
              {c ? (
                <div className="class-grid">
                  {result?.extract_note ? (
                    <div className="class-card wide">
                      <span>Okuma</span>
                      <strong>{result.extract_note}</strong>
                    </div>
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
                  {result?.fields
                    ? Object.entries(result.fields).map(([key, value]) => (
                        <div key={key} className="class-card">
                          <span>{FIELD_LABEL[key] ?? key}</span>
                          <strong>{value}</strong>
                        </div>
                      ))
                    : null}
                  {result?.missing?.length ? (
                    <div className="class-card wide">
                      <span>Eksik alan</span>
                      <strong>{result.missing.join(" · ")}</strong>
                    </div>
                  ) : null}
                  {result?.route_reason ? (
                    <div className="class-card wide">
                      <span>Görev 2</span>
                      <strong>{result.route_reason}</strong>
                    </div>
                  ) : null}
                  {result?.havale?.unit || result?.classification.unit ? (
                    <div className="class-card wide">
                      <span>Havale</span>
                      <strong>{result.havale?.unit ?? result.classification.unit}</strong>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="muted evrak-hint">Çözümlemeden sonra tür, nitelik ve birim kartları burada açılır.</p>
              )}
            </div>
          </div>
        ) : null}
        {side === "sinif" ? (
          c ? (
            <div className="class-grid" style={{ padding: "0 0.9rem 1rem" }}>
              {result?.verdict ? (
                <div className="class-card wide">
                  <span>Ne olduğu</span>
                  <strong>{result.verdict}</strong>
                </div>
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
                  <span>Eksik alan</span>
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
            <p className="muted evrak-hint">Önce Gelen kamu evrakı’ndan dosya yükleyin veya çözün.</p>
          )
        ) : null}
        {side === "akil" ? <ReasoningPanel reasoning={result?.reasoning} /> : null}
        {side === "taslaklar" ? (
          result?.draft ? (
            result.petition ? (
              <PetitionPreview
                petition={result.petition}
                draft={result.draft}
                badge={result.belge ?? result.action}
              />
            ) : (
            <article className="evrak-draft">
              <h2>Cevap taslağı</h2>
              <p className="muted" style={{ fontSize: 12 }}>
                Yazıcı: {writerLabel(result.writer)}
                {result.belge ? ` · kalıp: ${result.belge}` : ""}
                {result.writer_error ? ` · ${result.writer_error}` : ""}
              </p>
              {result.havale ? <p className="muted">Havale: {result.havale.unit}. {result.havale.note}</p> : null}
              <pre className="draft-pre">{result.draft}</pre>
            </article>
            )
          ) : (
            <p className="muted evrak-hint">Henüz taslak yok. Evrakı çözünce burada durur.</p>
          )
        ) : null}
      </section>
    </AppShell>
  );
}
