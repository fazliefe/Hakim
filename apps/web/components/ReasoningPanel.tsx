"use client";

import { useState } from "react";
import { ReasoningHop, ReasoningTrace } from "@/lib/api";
import { hopStateLabel, hopTitle } from "@/lib/labels";

function hopVisible(hop: ReasoningHop, hideSemantic: boolean) {
  if (hop.id === "cevap" || hop.question === "Ne dendi?") return false;
  if (hideSemantic && (hop.id === "vektor" || /anlamsal|semantic/i.test(`${hop.title ?? ""} ${hop.question ?? ""}`))) {
    return false;
  }
  return true;
}

function hopWhy(why?: string | null) {
  if (!why) return null;
  if (/rota:|hibrit|bm25|rrf|semantic/i.test(why)) return null;
  return why;
}

export function ReasoningPanel({
  reasoning,
  hideSemantic,
  collapsible,
}: {
  reasoning?: ReasoningTrace | null;
  hideSemantic?: boolean;
  collapsible?: boolean;
}) {
  const [open, setOpen] = useState(!collapsible);
  const hops = (reasoning?.hops ?? []).filter((hop) => hopVisible(hop, Boolean(hideSemantic)));
  if (!hops.length) {
    return <p className="muted evrak-hint">Önce evrakı çözün. Adımlar burada sıralanır.</p>;
  }

  return (
    <article className={`reasoning-panel${collapsible && !open ? " collapsed" : ""}`}>
      {collapsible ? (
        <button
          type="button"
          className="reasoning-toggle"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          <span>Akıl Yürütme</span>
          <em>{open ? "Kapat" : `${hops.length} adım`}</em>
        </button>
      ) : (
        <header className="reasoning-head">
          <h2>Akıl Yürütme</h2>
        </header>
      )}
      {open ? (
        <>
          <ol className="reasoning-hops">
            {hops.map((hop, index) => {
              const title = hopTitle(hop.id, hop.title || hop.question);
              const answer = (hop.answer || "").trim();
              const showAnswer = answer && answer !== title;
              return (
                <li key={hop.id || hop.n} className={hop.state}>
                  <span className="hop-n">{index + 1}</span>
                  <div className="hop-body">
                    <div className="hop-line">
                      <p className="hop-q">{title}</p>
                      <span className="hop-state">{hopStateLabel(hop.state)}</span>
                    </div>
                    {showAnswer ? <p className="hop-a">{answer}</p> : null}
                    {hopWhy(hop.why) ? <p className="hop-why">{hopWhy(hop.why)}</p> : null}
                  </div>
                </li>
              );
            })}
          </ol>
          {reasoning?.conclusion ? <p className="reasoning-end">{reasoning.conclusion}</p> : null}
        </>
      ) : null}
    </article>
  );
}
