"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { writerLabel } from "@/lib/api";
import { STAGE_LABEL, useDocumentAnalysis } from "@/lib/useDocumentAnalysis";

const SIDE = [
  { id: "asama", label: "Aşama" },
  { id: "kanun", label: "Kanun yolları" },
  { id: "sureler", label: "Süreler" },
];

const REMEDY_LABEL: Record<string, string> = {
  itiraz: "İtiraz",
  istinaf: "İstinaf",
  temyiz: "Temyiz",
  bireysel_basvuru: "Bireysel başvuru",
  istinaf_idari: "İdari istinaf",
  sikayet: "Şikayet",
};

export function SurecWorkbench() {
  const { text, setText, loading, error, result, submit } = useDocumentAnalysis("/v1/surec");
  const [side, setSide] = useState("asama");
  const [picked, setPicked] = useState(0);
  const today = new Date().toISOString().slice(0, 10);
  const deadlines = result?.deadlines ?? [];
  const selected = deadlines[picked] ?? deadlines[0] ?? null;
  const missed = useMemo(
    () => deadlines.filter((item) => item.last_day && item.last_day < today),
    [deadlines, today],
  );

  return (
    <AppShell
      module="surec"
      sidebarTitle="Usul"
      sidebarItems={SIDE}
      sidebarActive={side}
      onSidebarSelect={setSide}
      quote="“Süre tahmini değil, hesaptır.”"
      quoteMeta="CMK 5271 · TCK 5237"
      inspectorTitle="Süre kartı"
      inspector={
        selected ? (
          <div className={`deadline-card ${selected.last_day && missed.includes(selected) ? "missed" : ""}`}>
            <strong>{selected.name}</strong>
            <p className="muted">
              {selected.duration} {selected.unit} · {selected.calendar}
            </p>
            <p>Tetikleyici: {selected.trigger ?? "yok"}</p>
            <p>
              Son gün:{" "}
              {selected.last_day ? (
                <span className="tabular last-day">{selected.last_day}</span>
              ) : (
                <span>Hesaplanamadı — {selected.missing}</span>
              )}
            </p>
            <p className="muted">{selected.legal_basis.join(" · ")}</p>
          </div>
        ) : (
          <p className="muted">Karar metnini çözün; süreler kural motoruyla hesaplanır.</p>
        )
      }
      footer={
        loading
          ? "Aşama ve süreler hesaplanıyor…"
          : result
            ? `${STAGE_LABEL[result.classification.stage] ?? result.classification.stage} · ${result.deadlines.length} süre · ${writerLabel(result.writer)}`
            : "Süreç bekleniyor"
      }
    >
      <section className="main-pane surec-pane">
        <div className="pane-hero">
          <h1>{side === "asama" ? "Aşama" : side === "kanun" ? "Kanun yolları" : "Süreler"}</h1>
          <p>Aşama, kanun yolu ve son gün — LLM değil, süre motoru.</p>
        </div>
        <form className="surec-input" onSubmit={submit}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Karar veya tebligat metni"
            rows={4}
            spellCheck={false}
          />
          <button type="submit" disabled={loading || text.trim().length < 8}>
            {loading ? "Hesaplanıyor…" : "Süreleri hesapla"}
          </button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        {result?.draft ? (
          <article className="evrak-draft" style={{ margin: "0 0.9rem 1rem" }}>
            <h2>Usul anlatımı</h2>
            <p className="muted" style={{ fontSize: 12 }}>
              Süre rakamları kural motorundan. Yazıcı: {writerLabel(result.writer)}
              {result.writer_error ? ` · ${result.writer_error}` : ""}
            </p>
            <pre className="draft-pre">{result.draft}</pre>
          </article>
        ) : null}
        {!result ? (
          <p className="muted surec-empty">Örnek gerekçeli kararı bırakıp süreleri hesaplayın.</p>
        ) : side === "asama" ? (
          <ol className="stage-rail" style={{ margin: "0 1.2rem 1rem" }}>
            {result.stages.map((stage) => (
              <li key={stage.id} className={stage.state}>
                <i />
                <span>{stage.title}</span>
              </li>
            ))}
          </ol>
        ) : side === "kanun" ? (
          <div className="deadline-board" style={{ padding: "0 0.9rem 1rem" }}>
            {(result.classification.remedies.length ? result.classification.remedies : ["belirsiz"]).map((remedy) => (
              <div key={remedy} className="deadline-tile">
                <span>Kanun yolu</span>
                <strong>{REMEDY_LABEL[remedy] ?? remedy}</strong>
                <em>{result.classification.label}</em>
              </div>
            ))}
          </div>
        ) : (
          <div className="deadline-board" style={{ padding: "0 0.9rem 1rem" }}>
            {deadlines.length === 0 ? (
              <p className="muted">Bu evrak için eşleşen süre kuralı yok.</p>
            ) : (
              deadlines.map((item, index) => {
                const late = Boolean(item.last_day && item.last_day < today);
                return (
                  <button
                    key={item.rule_id}
                    type="button"
                    className={`deadline-tile ${picked === index ? "selected" : ""} ${late ? "missed" : ""}`}
                    onClick={() => setPicked(index)}
                  >
                    <span>{item.name}</span>
                    <strong className="tabular">{item.last_day ?? "—"}</strong>
                    <em>
                      {item.duration} {item.unit}
                      {late ? " · geçti" : ""}
                    </em>
                  </button>
                );
              })
            )}
          </div>
        )}
      </section>
    </AppShell>
  );
}
