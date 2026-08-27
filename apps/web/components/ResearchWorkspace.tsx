"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Evidence, ResearchResponse, runResearch, transcribeAudio } from "@/lib/api";
import { AppShell, InspectorMode } from "@/components/AppShell";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { RESEARCH_THINK_STEPS, ThinkingHops } from "@/components/ThinkingHops";
import { lawPrefix, shortLabel } from "@/components/graph/layout";
import { LegalDisclaimer } from "@/components/LegalDisclaimer";

const LegalGraphView = dynamic(
  () => import("@/components/graph/LegalGraphView").then((mod) => mod.LegalGraphView),
  { ssr: false },
);
const TraceGraphView = dynamic(
  () => import("@/components/graph/TraceGraphView").then((mod) => mod.TraceGraphView),
  { ssr: false },
);

type Tab = "metin" | "kaynaklar" | "emsal" | "graf" | "iz";
type SideView = "arastirmalar" | "gecmis" | "kaydedilen";
type ChatTurn = { id: string; query: string; answer: string; result: ResearchResponse };

const SIDE_ITEMS = [
  { id: "arastirmalar", label: "Araştırmalar" },
  { id: "gecmis", label: "Geçmiş" },
  { id: "kaydedilen", label: "Kaydedilen Maddeler" },
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
      <LegalDisclaimer variant="arastirma" />
    </div>
  );
}

function isDecision(item: Evidence) {
  return Boolean(item.document_id?.startsWith("decision:"));
}

function sourceHeading(item: Evidence) {
  if (isDecision(item)) {
    return shortLabel(item.title || item.document_id || "Mahkeme Kararı", 90);
  }
  return `${lawPrefix(item.law_no)} m.${item.article_no ?? "?"}`;
}

const COURT_LABELS: Record<string, string> = {
  yargitay: "Yargıtay",
  danistay: "Danıştay",
  yerelhukuk: "Yerel Hukuk",
  istinafhukuk: "İstinaf Hukuk",
  kyb: "KYB",
  aym: "AYM",
};

function courtLabel(item: Evidence): string {
  const slug = item.document_id?.split(":")[1] ?? "";
  return COURT_LABELS[slug] || "Emsal karar";
}

function contentPreview(text: string, limit = 320): string {
  const trimmed = text.trim();
  return trimmed.length > limit ? `${trimmed.slice(0, limit)}…` : trimmed;
}

function buildFollowUp(turns: ChatTurn[], userText: string): string {
  const topic = turns[0]?.query || turns[turns.length - 1]?.query || "";
  const lead = userText.trim();
  if (!topic || topic === lead) return lead;
  return `${lead}\nKonu: ${topic}`;
}

/**
 * Sesli okuma için cevap metnini "konuşulabilir" hale getirir: [n] atıf
 * işaretleri sessizce atlanmak yerine sözlü olarak belirtilir
 * ("...kaynak 3'e göre..."), başlıklar ve liste işaretleri de doğal
 * duraklamalarla okunacak şekilde sadeleştirilir.
 */
function toSpeakableText(text: string): string {
  return text
    .replace(/\[(\d+)\]/g, (_match, n: string) => `, kaynak ${n}'e göre,`)
    .replace(/^\d+\.\s+/gm, "")
    .replace(/^[•\-]\s+/gm, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s*,\s*,/g, ",")
    .replace(/\n{2,}/g, ". ")
    .replace(/\n/g, " ")
    .trim();
}

/** Tarayıcının desteklediği ilk MediaRecorder MIME türünü döndürür. */
function pickRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

/* Dikte/sesli-oku ikonları — SF Symbols'e yakın ince çizgi stili (renk
   düğmeden currentColor ile miras alınır, tema/durum CSS'te yönetilir). */

function MicIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="2.5" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0" />
      <line x1="12" y1="17.5" x2="12" y2="21" />
      <line x1="8.5" y1="21" x2="15.5" y2="21" />
    </svg>
  );
}

function StopIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2.5" />
    </svg>
  );
}

function LoadingIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="icon-spin" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeDasharray="24 30" opacity={0.85} />
    </svg>
  );
}

function SpeakerIcon({ size = 15 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 9.3v5.4h3.3L12.3 19V5L7.3 9.3H4z" fill="currentColor" />
      <path
        d="M15.6 9a4.1 4.1 0 0 1 0 6M18.3 6.8a7.6 7.6 0 0 1 0 10.4"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
      />
    </svg>
  );
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
  const [readingId, setReadingId] = useState<string | null>(null);

  // Dikte (Groq Whisper API) — yalnızca Araştırma modülünde, bkz. services/llm/speech.py
  const [micSupported, setMicSupported] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [micStatus, setMicStatus] = useState("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const micStreamRef = useRef<MediaStream | null>(null);

  // Sesli cevap (window.speechSynthesis) — atıflar sözlü belirtilir, bkz. toSpeakableText
  const [ttsSupported, setTtsSupported] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | null>(null);

  useEffect(() => {
    setHistory(readJson(HISTORY_KEY, []));
    setSaved(readJson(SAVED_KEY, []));
    setMicSupported(
      typeof navigator !== "undefined" &&
        Boolean(navigator.mediaDevices?.getUserMedia) &&
        typeof MediaRecorder !== "undefined",
    );
    setTtsSupported(typeof window !== "undefined" && Boolean(window.speechSynthesis));
  }, []);

  useEffect(() => {
    return () => {
      micStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, loading]);

  const selectedEvidence: Evidence | null = useMemo(() => {
    if (!result || selected == null) return result?.evidence[0] ?? null;
    return result.evidence.find((item) => item.n === selected) ?? null;
  }, [result, selected]);

  const savedIds = useMemo(() => new Set(saved.map((item) => item.id)), [saved]);
  const reading = saved.find((item) => item.id === readingId) ?? null;
  const hideSemantic = Boolean(result && !result.evidence.some((item) => item.semantic_rank));
  const decisions = useMemo(() => result?.evidence.filter(isDecision) ?? [], [result]);

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
    // "Kaynaklar" sekmesi kendi içeriğini göstermiyor — asıl kaynak listesi
    // AppShell'in sağ "inspector" paneli (bkz. openSource ile aynı mekanizma,
    // atıf [n] tıklanınca açılan panel). Sekmeye tıklamak önceden hiçbir şey
    // yapmıyordu; panel varsayılan olarak kapalı (`inspectorMode: "collapsed"`)
    // olduğu için "Kaynaklar" tıklaması görünürde ölü bir buton gibi duruyordu.
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

  async function toggleMic() {
    if (recording) {
      mediaRecorderRef.current?.stop();
      return;
    }
    if (transcribing) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      const mimeType = pickRecorderMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recordedChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        micStreamRef.current = null;
        setRecording(false);
        const blob = new Blob(recordedChunksRef.current, { type: mimeType || "audio/webm" });
        recordedChunksRef.current = [];
        if (!blob.size) {
          setMicStatus("Kayıt boş, tekrar deneyin.");
          return;
        }
        setTranscribing(true);
        setMicStatus("Ses metne çevriliyor…");
        try {
          const { text } = await transcribeAudio(blob);
          setQuery((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text));
          setMicStatus("Dikte tamamlandı.");
        } catch (err) {
          const message = err instanceof Error ? err.message : "Dikte başarısız";
          setError(message);
          setMicStatus(message);
        } finally {
          setTranscribing(false);
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      setMicStatus("Kayıt başladı, durdurmak için tekrar tıklayın.");
    } catch {
      setMicStatus("Mikrofon erişimi reddedildi veya kullanılamıyor.");
    }
  }

  function stopSpeaking() {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setSpeakingId(null);
  }

  function speakTurn(turn: ChatTurn) {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    if (speakingId === turn.id) {
      stopSpeaking();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(toSpeakableText(turn.answer));
    const voices = window.speechSynthesis.getVoices();
    const trVoice = voices.find((voice) => voice.lang?.toLowerCase().startsWith("tr"));
    if (trVoice) utterance.voice = trVoice;
    utterance.lang = trVoice?.lang || "tr-TR";
    utterance.onend = () => setSpeakingId((current) => (current === turn.id ? null : current));
    utterance.onerror = () => setSpeakingId((current) => (current === turn.id ? null : current));
    setSpeakingId(turn.id);
    window.speechSynthesis.speak(utterance);
  }

  function startNewResearch() {
    stopSpeaking();
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
            {selectedEvidence.title || (isDecision(selectedEvidence) ? "Başlıksız Karar" : "Başlıksız Madde")}
          </div>
          <p className="source-content">{selectedEvidence.content}</p>
          {selectedEvidence.mulga_warning ? <p className="error">⚠ {selectedEvidence.mulga_warning}</p> : null}
          <button type="button" className="side-action" onClick={toggleSave}>
            {savedIds.has(selectedEvidence.chunk_id) ? "Kayıttan Çıkar" : "Maddeyi Kaydet"}
          </button>
        </article>
      ) : null}
    </div>
  );

  return (
    <AppShell
      module="arastirma"
      sidebarTitle="Hukuki Araştırma"
      sidebarItems={SIDE_ITEMS}
      sidebarActive={side}
      onSidebarSelect={(id) => {
        const next = id as SideView;
        setSide(next);
        if (next === "kaydedilen" && saved[0] && !saved.some((item) => item.id === readingId)) {
          setReadingId(saved[0].id);
        }
      }}
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
              <h1>{side === "gecmis" ? "Geçmiş" : "Kaydedilen Maddeler"}</h1>
              <p>
                {side === "gecmis"
                  ? "Önceki araştırmalar. Tıklayınca yeni sohbet başlar."
                  : "Tuttuğunuz madde ve kararlar."}
              </p>
            </div>
          ) : tab !== "graf" && tab !== "iz" && turns.length === 0 ? (
            <div className="pane-hero">
              <h1>Hukuki Araştırma</h1>
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
              {result && tab === "emsal" ? (
                <div className="emsal-karar-list">
                  {decisions.length ? (
                    decisions.map((item) => (
                      <button
                        key={item.chunk_id}
                        type="button"
                        className={`emsal-karar-card ${selected === item.n ? "selected" : ""}`}
                        onClick={() => openSource(item.n)}
                      >
                        <div className="emsal-karar-head">
                          <span className="badge">{courtLabel(item)}</span>
                          <span className="emsal-karar-title">{sourceHeading(item)}</span>
                        </div>
                        <p className="emsal-karar-preview">{contentPreview(item.content)}</p>
                        {item.mulga_warning ? <p className="error">⚠ {item.mulga_warning}</p> : null}
                      </button>
                    ))
                  ) : (
                    <p className="muted">Bu sorguyla ilgili emsal karar bulunamadı.</p>
                  )}
                </div>
              ) : null}
              {tab !== "graf" && tab !== "iz" && tab !== "emsal" ? (
                <>
                  {turns.map((turn, index) => (
                    <div key={turn.id} className="chat-turn">
                      <p className="chat-q">{turn.query}</p>
                      <article className="answer">
                        <div className="answer-head">
                          {index === turns.length - 1 ? <h1>Cevap</h1> : <h2 className="chat-answer-label">Cevap</h2>}
                          {ttsSupported && turn.answer ? (
                            <button
                              type="button"
                              className={`speak-btn ${speakingId === turn.id ? "speaking" : ""}`}
                              onClick={() => speakTurn(turn)}
                              aria-pressed={speakingId === turn.id}
                            >
                              {speakingId === turn.id ? (
                                <>
                                  <StopIcon size={13} /> Durdur
                                </>
                              ) : (
                                <>
                                  <SpeakerIcon /> Sesli Oku
                                </>
                              )}
                            </button>
                          ) : null}
                        </div>
                        {turn.answer ? (
                          <AnswerBody text={turn.answer} selected={selected} onCite={openSource} />
                        ) : (
                          <p className="muted">Cevap metni boş döndü.</p>
                        )}
                      </article>
                      {index === turns.length - 1 && decisions.length ? (
                        <button type="button" className="emsal-karar-nudge" onClick={() => onTab("emsal")}>
                          🏛 {decisions.length} ilgili emsal karar bulundu — Emsal Karar sekmesine bakın
                        </button>
                      ) : null}
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
                  <>
                    {saved.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`source-row ${readingId === item.id ? "selected" : ""}`}
                        onClick={() => setReadingId(item.id)}
                      >
                        {item.heading}
                      </button>
                    ))}
                    {reading ? (
                      <article className="source-detail">
                        <div className="source-title">{reading.heading}</div>
                        <p className="source-content">{reading.content}</p>
                        <button
                          type="button"
                          className="side-action"
                          onClick={() => {
                            persistSaved(saved.filter((row) => row.id !== reading.id));
                            setReadingId(null);
                          }}
                        >
                          Kayıttan Çıkar
                        </button>
                      </article>
                    ) : (
                      <p className="muted">Bir madde seçin.</p>
                    )}
                  </>
                ) : (
                  <p className="muted">Kayıtlı madde yok. Kaynak panelinden «Maddeyi Kaydet» deyin.</p>
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
              aria-label={turns.length ? "Devam Sorusu" : "Hukuki Soru"}
            />
            {micSupported ? (
              <button
                type="button"
                className={`mic-btn ${recording ? "recording" : ""}`}
                onClick={toggleMic}
                disabled={transcribing}
                aria-pressed={recording}
                aria-label={recording ? "Dikteyi durdur" : "Dikte ile yaz"}
                title={recording ? "Dikteyi durdur" : "Dikte ile yaz"}
              >
                {transcribing ? <LoadingIcon /> : recording ? <StopIcon /> : <MicIcon />}
              </button>
            ) : null}
            <button type="submit" disabled={loading || query.trim().length < 2}>
              {loading ? "Kaynaklar Tartılıyor…" : turns.length ? "Devam Et" : "Araştır"}
            </button>
            <span className="mic-status" role="status" aria-live="polite">
              {micStatus}
            </span>
          </form>
        ) : null}
        {side === "arastirmalar" ? (
          <div className="bottom-tabs" role="tablist">
            {(
              [
                ["metin", "Metin"],
                ["kaynaklar", "Kaynaklar"],
                ["emsal", decisions.length ? `Emsal Karar (${decisions.length})` : "Emsal Karar"],
                ["graf", "Bilgi Grafı"],
                ["iz", "Arama İzi"],
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
