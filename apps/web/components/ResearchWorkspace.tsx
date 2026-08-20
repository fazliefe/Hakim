"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Evidence, ResearchResponse, SourceCatalog, getLegalSources, runResearch, writerLabel } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { RESEARCH_THINK_STEPS, ThinkingHops } from "@/components/ThinkingHops";
import { lawPrefix } from "@/components/graph/layout";

const LegalGraphView = dynamic(
  () => import("@/components/graph/LegalGraphView").then((mod) => mod.LegalGraphView),
  { ssr: false },
);
const TraceGraphView = dynamic(
  () => import("@/components/graph/TraceGraphView").then((mod) => mod.TraceGraphView),
  { ssr: false },
);

type Tab = "metin" | "kaynaklar" | "graf" | "iz";
type SideView = "arastirmalar" | "dosyalar" | "gecmis" | "kaydedilen" | "acik-kaynaklar";

const SIDE_ITEMS = [
  { id: "arastirmalar", label: "Araştırmalar" },
  { id: "dosyalar", label: "Dosyalar" },
  { id: "gecmis", label: "Geçmiş" },
  { id: "kaydedilen", label: "Kaydedilen maddeler" },
  { id: "acik-kaynaklar", label: "Açık kaynaklar" },
];

const HISTORY_KEY = "hakim-research-history";
const SAVED_KEY = "hakim-saved-articles";

type HistoryEntry = { id: string; query: string; at: string };
type SavedArticle = { id: string; heading: string; content: string };

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function AnswerBody({
  text,
  selected,
  onCite,
}: {
  text: string;
  selected: number | null;
  onCite: (n: number) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <div className="answer-body">
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) {
          return <span key={index}>{part}</span>;
        }
        const n = Number(match[1]);
        return (
          <button
            key={index}
            type="button"
            className={`cite ${selected === n ? "selected" : ""}`}
            onClick={() => onCite(n)}
          >
            [{n}]
          </button>
        );
      })}
    </div>
  );
}

function isDecision(item: Evidence) {
  return Boolean(item.document_id?.startsWith("decision:"));
}

function sourceHeading(item: Evidence) {
  if (isDecision(item)) {
    return item.title || item.document_id || "Mahkeme kararı";
  }
  return `${lawPrefix(item.law_no)} m.${item.article_no ?? "?"}`;
}

function routeLabel(route: string) {
  if (route === "exact_citation") return "kesin madde atıfı";
  if (route === "hybrid") return "hibrit arama";
  return route;
}

export function ResearchWorkspace() {
  const [query, setQuery] = useState("nitelikli dolandırıcılıkta banka hesabının kullanılması");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("metin");
  const [side, setSide] = useState<SideView>("arastirmalar");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [saved, setSaved] = useState<SavedArticle[]>([]);
  const [catalog, setCatalog] = useState<SourceCatalog | null>(null);

  useEffect(() => {
    setHistory(readJson(HISTORY_KEY, []));
    setSaved(readJson(SAVED_KEY, []));
    getLegalSources()
      .then(setCatalog)
      .catch(() => setCatalog({ official: [], mcp: [], huggingface: [], counts: {} }));
  }, []);

  const selectedEvidence: Evidence | null = useMemo(() => {
    if (!result || selected == null) return result?.evidence[0] ?? null;
    return result.evidence.find((item) => item.n === selected) ?? null;
  }, [result, selected]);

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved]);

  function persistHistory(next: HistoryEntry[]) {
    setHistory(next);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  }

  function persistSaved(next: SavedArticle[]) {
    setSaved(next);
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(next));
  }

  async function runQuery(text: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await runResearch(text.trim());
      setResult(data);
      setSelected(data.evidence[0]?.n ?? null);
      setTab("metin");
      setSide("arastirmalar");
      persistHistory(
        [{ id: String(Date.now()), query: text.trim(), at: new Date().toISOString() }, ...history.filter((h) => h.query !== text.trim())].slice(0, 20),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await runQuery(query);
  }

  function toggleSave() {
    if (!selectedEvidence) return;
    const id = selectedEvidence.chunk_id;
    if (savedIds.has(id)) {
      persistSaved(saved.filter((item) => item.id !== id));
      return;
    }
    persistSaved([
      { id, heading: sourceHeading(selectedEvidence), content: selectedEvidence.content },
      ...saved,
    ]);
  }

  const inspector = !selectedEvidence ? (
    <p className="muted">Bir kaynak seçin veya atıfa tıklayın.</p>
  ) : (
    <div>
      <div className="source-meta">
        <span>{sourceHeading(selectedEvidence)}</span>
        <span className="badge">{selectedEvidence.authority || "resmi"}</span>
      </div>
      <div className="source-title">
        {selectedEvidence.title || (isDecision(selectedEvidence) ? "Başlıksız karar" : "Başlıksız madde")}
      </div>
      <p className="muted" style={{ fontSize: 12 }}>
        BM25 #{selectedEvidence.bm25_rank ?? "—"} · Anlamsal #{selectedEvidence.semantic_rank ?? "—"} · RRF #
        {selectedEvidence.rrf_rank}
      </p>
      <p className="source-content">{selectedEvidence.content}</p>
      <p className="muted" style={{ fontSize: 12 }}>
        Getirici: {selectedEvidence.retrievers.join(" + ") || "—"}
      </p>
      <button type="button" className="side-action" onClick={toggleSave}>
        {savedIds.has(selectedEvidence.chunk_id) ? "Kayıttan çıkar" : "Maddeyi kaydet"}
      </button>
    </div>
  );

  return (
    <AppShell
      module="arastirma"
      sidebarTitle="Dava dosyası"
      sidebarItems={SIDE_ITEMS}
      sidebarActive={side}
      onSidebarSelect={(id) => setSide(id as SideView)}
      quote="“Hukuk, kaynaklarla konuşur.”"
      quoteMeta="Resmi mevzuat, içtihat ve kurul kararları"
      inspectorTitle="Kaynak / Delil"
      inspector={inspector}
      footer={
        loading
          ? "Kaynaklar tartılıyor…"
            : result
              ? `${result.evidence.length} kaynak · ${routeLabel(result.route)}`
            : "Salon hazır"
      }
    >
      <section className="main-pane">
          {side !== "arastirmalar" ? (
            <div className="pane-hero">
              <h1>
                {side === "dosyalar"
                  ? "Dosyalar"
                  : side === "gecmis"
                    ? "Geçmiş"
                    : side === "acik-kaynaklar"
                      ? "Açık kaynaklar"
                      : "Kaydedilen maddeler"}
              </h1>
              <p>
                {side === "dosyalar"
                  ? "Bu araştırmanın kaynak dosyaları."
                  : side === "gecmis"
                    ? "Önceki sorgular. Tıklayınca yeniden araştırılır."
                    : side === "acik-kaynaklar"
                      ? "Resmi siteler birincil kaynaktır. Hugging Face derlemleri ikincil katalogdadır."
                      : "Kalıcı olarak tuttuğunuz madde ve kararlar."}
              </p>
            </div>
          ) : tab !== "graf" && tab !== "iz" ? (
          <div className="pane-hero">
            <h1>Hukuki Araştırma</h1>
            <p>Cevap Elasticsearch, atıf grafı ve madde metniyle birlikte gelir.</p>
          </div>
          ) : null}

          {side === "arastirmalar" ? (
          <>
          <form className="query-bar" onSubmit={onSubmit}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Hukuki sorunuzu yazın… örn. Madde 158"
              aria-label="Hukuki soru"
            />
            <button type="submit" disabled={loading || query.trim().length < 2}>
              {loading ? "Kaynaklar tartılıyor…" : "Araştır"}
            </button>
          </form>

          <div className={`content-area ${tab === "graf" || tab === "iz" ? "graph-mode" : ""}`}>
            {error ? <p className="error">{error}</p> : null}
            {loading ? <ThinkingHops steps={RESEARCH_THINK_STEPS} query={query} /> : null}
            {result && tab === "graf" ? (
              <LegalGraphView
                evidence={result.evidence}
                selected={selected}
                onSelect={setSelected}
                query={result.query}
              />
            ) : null}
            {result && tab === "iz" ? (
              <TraceGraphView
                nodes={result.trace_nodes}
                edges={result.trace_edges}
                evidence={result.evidence}
                selected={selected}
                onSelect={setSelected}
              />
            ) : null}
            {(!result && !error && !loading) || (result && !loading && tab !== "graf" && tab !== "iz") ? (
              <>
                {!result && !error ? (
                  <div className="empty-state">
                    <p className="muted">
                      Kaynak odaklı araştırma için sorunuzu yazın. Atıflar tıklanabilir; sağ panelde madde
                      metni ve bilgi grafı açılır.
                    </p>
                  </div>
                ) : null}
                {result ? (
                  <>
                    {result.reasoning ? <ReasoningPanel reasoning={result.reasoning} /> : null}
                    <article className="answer">
                      <h1>Gerekçe</h1>
                      <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
                        {`Yazım: ${writerLabel(result.writer)}`}
                        {` · ${routeLabel(result.route)} · ${result.evidence.length} kaynak`}
                      </p>
                      {result.answer ? (
                        <AnswerBody text={result.answer} selected={selected} onCite={setSelected} />
                      ) : (
                        <p className="muted">Cevap metni boş döndü; yukarıdaki akıl yürütmeye bakın.</p>
                      )}
                    </article>
                  </>
                ) : null}
              </>
            ) : null}
          </div>

          <div className="bottom-tabs" role="tablist">
            {(
              [
                ["metin", "Metin"],
                ["kaynaklar", "Kaynaklar"],
                ["graf", "Bilgi grafı"],
                ["iz", "Arama izi"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                className={tab === id ? "active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className={`bottom-panel ${tab === "graf" || tab === "iz" ? "hidden" : ""}`} role="tabpanel">
            {!result ? <p className="muted">Sonuç bekleniyor.</p> : null}
            {result && tab === "metin" ? (
              <p className="muted">
                Rota: <strong>{routeLabel(result.route)}</strong> · Aktif kaynak:{" "}
                {result.evidence.filter((e) => e.used_in_answer).length}
              </p>
            ) : null}
            {result && tab === "kaynaklar" ? (
              <div>
                {result.evidence.map((item) => (
                  <button
                    key={item.chunk_id}
                    type="button"
                    className={`source-row ${selected === item.n ? "selected" : ""}`}
                    onClick={() => setSelected(item.n)}
                  >
                    [{item.n}] {isDecision(item) ? item.title || "Mahkeme kararı" : `${lawPrefix(item.law_no)} ${item.article_no}`} —{" "}
                    {isDecision(item) ? "içtihat" : item.title || "Başlıksız"}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          </> ) : (
          <div className="content-area">
            {side === "dosyalar" ? (
              result ? (
                result.evidence.map((item) => (
                  <button
                    key={item.chunk_id}
                    type="button"
                    className={`source-row ${selected === item.n ? "selected" : ""}`}
                    onClick={() => setSelected(item.n)}
                  >
                    [{item.n}] {isDecision(item) ? item.title || "Mahkeme kararı" : `${lawPrefix(item.law_no)} ${item.article_no}`}
                  </button>
                ))
              ) : (
                <p className="muted">Henüz dosya yok. Araştırmalar’dan bir sorgu çalıştırın.</p>
              )
            ) : null}
            {side === "gecmis" ? (
              history.length ? (
                history.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="source-row"
                    onClick={() => {
                      setQuery(item.query);
                      void runQuery(item.query);
                    }}
                  >
                    {item.query}
                    <span className="muted"> {item.at.slice(0, 10)}</span>
                  </button>
                ))
              ) : (
                <p className="muted">Kayıtlı sorgu yok.</p>
              )
            ) : null}
            {side === "kaydedilen" ? (
              saved.length ? (
                saved.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="source-row"
                    onClick={() => persistSaved(saved.filter((row) => row.id !== item.id))}
                    title="Kayıttan çıkarmak için tıklayın"
                  >
                    {item.heading}
                    <span className="muted"> — tıkla, kayıttan çıkar</span>
                  </button>
                ))
              ) : (
                <p className="muted">Kayıtlı madde yok. Kaynak panelinden «Maddeyi kaydet» deyin.</p>
              )
            ) : null}
            {side === "acik-kaynaklar" ? (
              catalog ? (
                <div className="source-catalog">
                  {catalog.official.map((item) => (
                    <a
                      key={item.id || item.url}
                      className="source-row"
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {item.name}
                      <span className="muted">
                        {" "}
                        · {item.documents ?? 0} belge · {item.status || "resmi"}
                      </span>
                    </a>
                  ))}
                  <p className="muted" style={{ marginTop: 16 }}>
                    Hugging Face (ikincil, içe aktarılmadı)
                  </p>
                  {catalog.huggingface.map((item) => (
                    <p key={item.id || item.repo} className="muted">
                      {item.repo}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="muted">Kaynak listesi yükleniyor…</p>
              )
            ) : null}
          </div>
          )}
        </section>
    </AppShell>
  );
}
