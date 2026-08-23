"use client";

import { FormEvent, PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Evidence, ResearchResponse, runResearch } from "@/lib/api";
import { AppShell, InspectorMode } from "@/components/AppShell";
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
type SideView = "arastirmalar" | "gecmis" | "kaydedilen";

const SIDE_ITEMS = [
  { id: "arastirmalar", label: "Araştırmalar" },
  { id: "gecmis", label: "Geçmiş" },
  { id: "kaydedilen", label: "Kaydedilen maddeler" },
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
  const [inspectorMode, setInspectorMode] = useState<InspectorMode>("collapsed");
  const [bottomHeight, setBottomHeight] = useState(190);
  const bottomDrag = useRef({ startY: 0, startH: 190 });

  useEffect(() => {
    setHistory(readJson(HISTORY_KEY, []));
    setSaved(readJson(SAVED_KEY, []));
  }, []);

  const selectedEvidence: Evidence | null = useMemo(() => {
    if (!result || selected == null) return result?.evidence[0] ?? null;
    return result.evidence.find((item) => item.n === selected) ?? null;
  }, [result, selected]);

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved]);
  const hideSemantic = Boolean(result && !result.evidence.some((item) => item.semantic_rank));

  function persistHistory(next: HistoryEntry[]) {
    setHistory(next);
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  }

  function persistSaved(next: SavedArticle[]) {
    setSaved(next);
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(next));
  }

  function openSource(n: number) {
    setSelected(n);
    setInspectorMode("open");
  }

  function onTab(next: Tab) {
    setTab(next);
    if (next === "kaynaklar") setInspectorMode("open");
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

  function onBottomStart(event: PointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    bottomDrag.current = { startY: event.clientY, startH: bottomHeight };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onBottomMove(event: PointerEvent<HTMLButtonElement>) {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    const next = bottomDrag.current.startH - (event.clientY - bottomDrag.current.startY);
    setBottomHeight(Math.min(420, Math.max(120, next)));
  }

  const inspector = (
    <div className="source-stack">
      {result?.evidence.length ? (
        result.evidence.map((item) => (
          <button
            key={item.chunk_id}
            type="button"
            className={`source-row ${selected === item.n ? "selected" : ""}`}
            onClick={() => openSource(item.n)}
          >
            [{item.n}] {sourceHeading(item)}
          </button>
        ))
      ) : (
        <p className="muted">Bir kaynağa veya atıfa tıklayın.</p>
      )}
      {selectedEvidence ? (
        <article className="source-detail">
          <div className="source-meta">
            <span>{sourceHeading(selectedEvidence)}</span>
            <span className="badge">{selectedEvidence.authority || "resmi"}</span>
          </div>
          <div className="source-title">
            {selectedEvidence.title || (isDecision(selectedEvidence) ? "Başlıksız karar" : "Başlıksız madde")}
          </div>
          <p className="source-content">{selectedEvidence.content}</p>
          <button type="button" className="side-action" onClick={toggleSave}>
            {savedIds.has(selectedEvidence.chunk_id) ? "Kayıttan çıkar" : "Maddeyi kaydet"}
          </button>
        </article>
      ) : null}
    </div>
  );

  return (
    <AppShell
      module="arastirma"
      sidebarTitle="Hukuki araştırma"
      sidebarItems={SIDE_ITEMS}
      sidebarActive={side}
      onSidebarSelect={(id) => setSide(id as SideView)}
      inspectorTitle="Kaynak"
      inspector={inspector}
      inspectorMode={inspectorMode}
      onInspectorModeChange={setInspectorMode}
      hideStatusBar
    >
      <section className="main-pane research-pane">
          <div className="research-scroll">
          {side !== "arastirmalar" ? (
            <div className="pane-hero">
              <h1>{side === "gecmis" ? "Geçmiş" : "Kaydedilen maddeler"}</h1>
              <p>
                {side === "gecmis"
                  ? "Önceki araştırmalar. Tıklayınca yeniden çalışır."
                  : "Tuttuğunuz madde ve kararlar."}
              </p>
            </div>
          ) : tab !== "graf" && tab !== "iz" ? (
          <div className="pane-hero">
            <h1>Hukuki araştırma</h1>
            <p>Cevap, madde metni ve atıflarla birlikte gelir.</p>
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
                onSelect={openSource}
                query={result.query}
              />
            ) : null}
            {result && tab === "iz" ? (
              <TraceGraphView
                nodes={result.trace_nodes}
                edges={result.trace_edges}
                evidence={result.evidence}
                selected={selected}
                onSelect={openSource}
              />
            ) : null}
            {(!result && !error && !loading) || (result && !loading && tab !== "graf" && tab !== "iz") ? (
              <>
                {!result && !error ? (
                  <div className="empty-state">
                    <p className="muted">Sorunuzu yazın. Atıflar kaynağı açar.</p>
                  </div>
                ) : null}
                {result ? (
                  <>
                    <article className="answer">
                      <h1>Cevap</h1>
                      {result.answer ? (
                        <AnswerBody text={result.answer} selected={selected} onCite={openSource} />
                      ) : (
                        <p className="muted">Cevap metni boş döndü.</p>
                      )}
                    </article>
                    {result.reasoning ? (
                      <ReasoningPanel reasoning={result.reasoning} hideSemantic={hideSemantic} collapsible />
                    ) : null}
                  </>
                ) : null}
              </>
            ) : null}
          </div>
          </> ) : (
          <div className="content-area">
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
          </div>
          )}
          </div>
          {side === "arastirmalar" && tab !== "graf" && tab !== "iz" ? (
            <>
              <button
                type="button"
                className="bottom-resizer"
                aria-label="Alt paneli boyutlandır"
                onPointerDown={onBottomStart}
                onPointerMove={onBottomMove}
              />
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
                    onClick={() => onTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="bottom-panel" style={{ height: bottomHeight }} role="tabpanel">
                {!result ? <p className="muted">Sonuç bekleniyor.</p> : null}
                {result && tab === "metin" ? (
                  <p className="muted">
                    Cevaptaki atıflar sağ panelde kaynağı açar. {result.evidence.filter((e) => e.used_in_answer).length} kaynak kullanıldı.
                  </p>
                ) : null}
                {result && tab === "kaynaklar" ? (
                  <p className="muted">Kaynak açıklamaları sağ panelde. Atıfa veya Kaynaklar’a tıklayın.</p>
                ) : null}
              </div>
            </>
          ) : side === "arastirmalar" ? (
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
                  onClick={() => onTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
        </section>
    </AppShell>
  );
}
