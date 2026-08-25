"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
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
type ChatTurn = { id: string; query: string; answer: string; result: ResearchResponse };

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

const ANSWER_HEADINGS = new Set([
  "Sonuç",
  "Hukuki dayanak",
  "İlgili hükümler",
  "Değerlendirme",
  "Kaynak",
]);

function CiteText({
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
    <>
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
    </>
  );
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
  const blocks = text.split(/\n\n+/).map((block) => block.trim()).filter(Boolean);
  return (
    <div className="answer-body memo">
      {blocks.map((block, index) => {
        if (ANSWER_HEADINGS.has(block)) {
          return (
            <h2 key={index} className="answer-section">
              {block}
            </h2>
          );
        }
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        if (lines.length && lines.every((line) => /^\d+\.\s+/.test(line))) {
          return (
            <ol key={index} className="answer-points">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>
                  <CiteText text={line.replace(/^\d+\.\s+/, "")} selected={selected} onCite={onCite} />
                </li>
              ))}
            </ol>
          );
        }
        if (lines.length && lines.every((line) => /^[•\-]\s+/.test(line))) {
          return (
            <ul key={index} className="answer-related">
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>
                  <CiteText text={line.replace(/^[•\-]\s+/, "")} selected={selected} onCite={onCite} />
                </li>
              ))}
            </ul>
          );
        }
        const note = index === blocks.length - 1 && blocks[index - 1] === "Kaynak";
        return (
          <p key={index} className={note ? "answer-source" : "answer-p"}>
            <CiteText text={block} selected={selected} onCite={onCite} />
          </p>
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

function buildFollowUp(turns: ChatTurn[], userText: string): string {
  const topic = turns[0]?.query || turns[turns.length - 1]?.query || "";
  const lead = userText.trim();
  if (!topic || topic === lead) return lead;
  return `${lead}\nKonu: ${topic}`;
}

export function ResearchWorkspace() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("metin");
  const [side, setSide] = useState<SideView>("arastirmalar");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [saved, setSaved] = useState<SavedArticle[]>([]);
  const [inspectorMode, setInspectorMode] = useState<InspectorMode>("collapsed");
  const threadEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory(readJson(HISTORY_KEY, []));
    setSaved(readJson(SAVED_KEY, []));
  }, []);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, loading]);

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

  async function runQuery(text: string, opts?: { followUp?: boolean; replace?: boolean }) {
    const display = text.trim();
    if (display.length < 2) return;
    const followUp = Boolean(opts?.followUp) && turns.length > 0 && !opts?.replace;
    const payload = followUp ? buildFollowUp(turns, display) : display;
    setLoading(true);
    setError(null);
    try {
      const data = await runResearch(payload);
      setResult(data);
      setSelected(data.evidence[0]?.n ?? null);
      setTab("metin");
      setSide("arastirmalar");
      const turn: ChatTurn = {
        id: String(Date.now()),
        query: display,
        answer: data.answer || "",
        result: data,
      };
      setTurns((prev) => (opts?.replace ? [turn] : [...prev, turn]));
      setQuery("");
      if (!followUp) {
        persistHistory(
          [{ id: String(Date.now()), query: display, at: new Date().toISOString() }, ...history.filter((h) => h.query !== display)].slice(0, 20),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit(event?: FormEvent) {
    event?.preventDefault();
    await runQuery(query, { followUp: turns.length > 0 });
  }

  function startNewResearch() {
    setTurns([]);
    setResult(null);
    setQuery("");
    setError(null);
    setSelected(null);
    setTab("metin");
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
            {item.mulga_warning ? "⚠ " : ""}[{item.n}] {sourceHeading(item)}
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
          {selectedEvidence.mulga_warning ? <p className="error">⚠ {selectedEvidence.mulga_warning}</p> : null}
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
        <div className={`research-scroll${tab === "graf" || tab === "iz" ? " graph-fill" : ""}`}>
          {side !== "arastirmalar" ? (
            <div className="pane-hero">
              <h1>{side === "gecmis" ? "Geçmiş" : "Kaydedilen maddeler"}</h1>
              <p>
                {side === "gecmis"
                  ? "Önceki araştırmalar. Tıklayınca yeni sohbet başlar."
                  : "Tuttuğunuz madde ve kararlar."}
              </p>
            </div>
          ) : tab !== "graf" && tab !== "iz" && turns.length === 0 ? (
            <div className="pane-hero">
              <h1>Hukuki araştırma</h1>
              <p>Sorunuzu yazın. Cevaptan sonra aynı sohbette devam edebilirsiniz.</p>
            </div>
          ) : null}

          {side === "arastirmalar" ? (
            <div className={`content-area ${tab === "graf" || tab === "iz" ? "graph-mode" : ""}`}>
              {error ? <p className="error">{error}</p> : null}
              {result && tab === "graf" ? (
                <LegalGraphView
                  evidence={result.evidence}
                  selected={selected}
                  onSelect={openSource}
                  query={turns[turns.length - 1]?.query || result.query}
                />
              ) : null}
              {result && tab === "iz" ? (
                <TraceGraphView
                  nodes={result.trace_nodes}
                  edges={result.trace_edges}
                  evidence={result.evidence}
                  selected={selected}
                  onSelect={openSource}
                  observability={result.observability}
                />
              ) : null}
              {tab !== "graf" && tab !== "iz" ? (
                <>
                  {turns.length === 0 && !error && !loading ? (
                    <div className="empty-state">
                      <p className="muted">Sorunuzu yazın. Atıflar kaynağı açar. Cevaptan sonra sohbet devam eder.</p>
                    </div>
                  ) : null}
                  {turns.map((turn, index) => (
                    <div key={turn.id} className="chat-turn">
                      <p className="chat-q">{turn.query}</p>
                      <article className="answer">
                        {index === turns.length - 1 ? <h1>Cevap</h1> : <h2 className="chat-answer-label">Cevap</h2>}
                        {turn.answer ? (
                          <AnswerBody text={turn.answer} selected={selected} onCite={openSource} />
                        ) : (
                          <p className="muted">Cevap metni boş döndü.</p>
                        )}
                      </article>
                      {index === turns.length - 1 && result?.reasoning ? (
                        <ReasoningPanel reasoning={result.reasoning} hideSemantic={hideSemantic} collapsible />
                      ) : null}
                    </div>
                  ))}
                  {loading ? (
                    <ThinkingHops steps={RESEARCH_THINK_STEPS} query={query || turns[turns.length - 1]?.query || ""} />
                  ) : null}
                  <div ref={threadEnd} />
                </>
              ) : null}
            </div>
          ) : (
            <div className="content-area">
              {side === "gecmis" ? (
                history.length ? (
                  history.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="source-row"
                      onClick={() => {
                        void runQuery(item.query, { replace: true });
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
                    <article key={item.id} className="saved-article">
                      <div className="saved-article-head">
                        <strong>{item.heading}</strong>
                        <button
                          type="button"
                          className="text-btn"
                          onClick={() => persistSaved(saved.filter((row) => row.id !== item.id))}
                        >
                          Kayıttan çıkar
                        </button>
                      </div>
                      <p>{item.content}</p>
                    </article>
                  ))
                ) : (
                  <p className="muted">Kayıtlı madde yok. Kaynak panelinden «Maddeyi kaydet» deyin.</p>
                )
              ) : null}
            </div>
          )}
        </div>
        {side === "arastirmalar" && tab !== "graf" && tab !== "iz" ? (
          <form className="query-bar research-composer" onSubmit={onSubmit}>
            {turns.length ? (
              <button type="button" className="text-btn composer-new" onClick={startNewResearch} disabled={loading}>
                Yeni
              </button>
            ) : null}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                turns.length ? "Devam sorunuzu yazın…" : "Hukuki sorunuzu yazın… örn. Madde 158"
              }
              aria-label={turns.length ? "Devam sorusu" : "Hukuki soru"}
            />
            <button type="submit" disabled={loading || query.trim().length < 2}>
              {loading ? "Aranıyor…" : turns.length ? "Devam et" : "Araştır"}
            </button>
          </form>
        ) : null}
        {side === "arastirmalar" ? (
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
