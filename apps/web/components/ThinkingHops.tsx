"use client";

import { useEffect, useState } from "react";

export type ThinkStep = { title: string; text: string };

export const RESEARCH_THINK_STEPS: ThinkStep[] = [
  { title: "Soru", text: "Soru Okunuyor…" },
  { title: "Metin Taraması", text: "Metin Taranıyor…" },
  { title: "Yakın Hüküm", text: "Yakın Hükümler Bakılıyor…" },
  { title: "Birleşim", text: "Kaynaklar Birleştiriliyor…" },
  { title: "Cevap", text: "Cevap Yazılıyor…" },
];

export const EVRAK_THINK_STEPS: ThinkStep[] = [
  { title: "Okuyucu", text: "Evrak Okunuyor…" },
  { title: "Sınıf", text: "Tür ve Nitelik Bakılıyor…" },
  { title: "Mevzuat", text: "Dayanak Maddeler Aranıyor…" },
  { title: "Süre", text: "Süre Kuralları İşleniyor…" },
  { title: "Taslak", text: "Resmi Yazı Kalıbı Seçiliyor…" },
  { title: "Havale", text: "Birim Önerisi Yazılıyor…" },
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
        <span className="reasoning-status thinking">Akıl Yürütülüyor</span>
      </header>
      {query ? <p className="thinking-query">«{query}»</p> : null}
      <ol className="reasoning-hops">
        {steps.map((step, index) => {
          const state = index < active ? "done" : index === active ? "think" : "wait";
          const line = state === "wait" ? "Sırada." : state === "think" ? step.text : step.text.replace(/…$/, ".");
          return (
            <li key={step.title} className={state}>
              <span className="hop-n">{index + 1}</span>
              <div className="hop-body">
                <div className="hop-line">
                  <p className="hop-q">{step.title}</p>
                  <span className="hop-state">
                    {state === "think" ? "işleniyor" : state === "done" ? "tamam" : "sırada"}
                  </span>
                </div>
                <p className="hop-a">{line}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </article>
  );
}
