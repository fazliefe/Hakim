import { ReasoningTrace } from "@/lib/api";

const STATE_WORD: Record<string, string> = {
  done: "emin",
  warn: "üst adıma bağlı",
  skip: "bu türde yok",
  error: "hata",
};

export function ReasoningPanel({ reasoning }: { reasoning?: ReasoningTrace | null }) {
  if (!reasoning?.hops?.length) {
    return <p className="muted evrak-hint">Önce evrakı çözün veya senaryoyu çalıştırın. Adımlar burada sıralanır.</p>;
  }
  return (
    <article className="reasoning-panel">
      <header className="reasoning-head">
        <h2>Akıl yürütme</h2>
        <span className={`reasoning-status ${reasoning.status}`}>
          {reasoning.status === "solid" ? "zincir sağlam" : reasoning.status === "broken" ? "zincir kırık" : "zincir kırılgan"}
        </span>
      </header>
      <ol className="reasoning-hops">
        {reasoning.hops.map((hop) => (
          <li key={hop.id} className={hop.state}>
            <span className="hop-n">{hop.n}</span>
            <div>
              <p className="hop-q">{hop.question}</p>
              <p className="hop-a">
                <strong>{hop.title}</strong>
                <span className="hop-answer-body">{hop.answer}</span>
              </p>
              {hop.why ? <p className="hop-why">{hop.why}</p> : null}
              <span className="hop-state">{STATE_WORD[hop.state] ?? hop.state}</span>
            </div>
          </li>
        ))}
      </ol>
      {reasoning.conclusion ? <p className="reasoning-end">{reasoning.conclusion}</p> : null}
    </article>
  );
}
