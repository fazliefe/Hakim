"use client";

import { useEffect, useState } from "react";

export type ThinkStep = { title: string; text: string };

export const RESEARCH_THINK_STEPS: ThinkStep[] = [
  { title: "Sorgu", text: "Soru okunuyor…" },
  { title: "BM25", text: "Kelime eşleşmesi taranıyor…" },
  { title: "Vektör", text: "Anlam yakınlığı tartılıyor…" },
  { title: "Birleşim", text: "Kaynaklar birleştiriliyor…" },
  { title: "Cevap", text: "Gerekçe yazılıyor…" },
];

export const EVRAK_THINK_STEPS: ThinkStep[] = [
  { title: "Okuyucu", text: "Evrak okunuyor…" },
  { title: "Sınıf", text: "Tür ve nitelik bakılıyor…" },
  { title: "Mevzuat", text: "Dayanak maddeler aranıyor…" },
  { title: "Süre", text: "Süre kuralları işleniyor…" },
  { title: "Taslak", text: "Resmi yazı kalıbı seçiliyor…" },
  { title: "Havale", text: "Birim önerisi yazılıyor…" },
];

export function ThinkingHops({
  steps,
  query,
}: {
  steps: ThinkStep[];
  query?: string;
}) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    setActive(0);
    const id = window.setInterval(() => {
      setActive((n) => (n < steps.length - 1 ? n + 1 : n));
    }, 1700);
    return () => window.clearInterval(id);
  }, [steps, query]);

  return (
    <article className="reasoning-panel thinking-live" aria-live="polite" aria-busy="true">
      <header className="reasoning-head">
        <h2>Düşünüyor</h2>
        <span className="reasoning-status thinking">akıl yürütülüyor</span>
      </header>
      {query ? <p className="thinking-query">«{query}»</p> : null}
      <ol className="reasoning-hops">
        {steps.map((step, index) => {
          const state = index < active ? "done" : index === active ? "think" : "wait";
          const line =
            state === "wait" ? "Sırada." : state === "think" ? step.text : `${step.text.replace(/…$/, ".")} Tamam.`;
          return (
            <li key={step.title} className={state}>
              <span className="hop-n">{index + 1}</span>
              <div>
                <p className="hop-q">{step.title}</p>
                <p className="hop-a">{line}</p>
                <span className="hop-state">
                  {state === "think" ? "düşünüyor" : state === "done" ? "emin" : "sırada"}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </article>
  );
}
