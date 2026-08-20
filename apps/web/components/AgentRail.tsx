import { AgentStep } from "@/lib/api";

const STATE_LABEL: Record<string, string> = {
  done: "emin",
  warn: "üst adıma bağlı",
  skip: "bu türde yok",
  error: "hata",
};

type Observability = {
  engine?: string;
  graph_nodes?: string[];
  langfuse_enabled?: boolean;
  langfuse_trace_id?: string | null;
  langfuse_url?: string | null;
};

export function AgentRail({
  agents,
  chainStatus,
  observability,
}: {
  agents?: AgentStep[];
  chainStatus?: string;
  observability?: Observability | null;
}) {
  if (!agents?.length) return null;
  return (
    <div className="agent-rail-wrap">
      <p className="agent-rail-legend">
        Adım teşhisi: yeşil emin · sarı üst adıma bağlı · gri bu türde yok · kırmızı hata
        {chainStatus === "fragile" ? " — zincir kırılgan (önceki adım emin değil)." : null}
        {chainStatus === "broken" ? " — zincir kırık." : null}
      </p>
      <ol className="agent-rail" aria-label="Ajan zinciri">
        {agents.map((agent) => (
          <li key={agent.id} className={agent.state}>
            <span className="agent-sticker" aria-hidden>
              {agent.state === "done" ? "●" : agent.state === "warn" ? "▲" : agent.state === "error" ? "✕" : "○"}
            </span>
            <span className="agent-title">{agent.title}</span>
            <span className="agent-ms">
              {agent.ms} ms · {STATE_LABEL[agent.state] ?? agent.state}
            </span>
            <span className="agent-summary">{agent.summary}</span>
            {agent.note ? <span className="agent-note">{agent.note}</span> : null}
          </li>
        ))}
      </ol>
      {observability?.engine ? (
        <p className="agent-obs">
          Motor: {observability.engine}
          {observability.graph_nodes?.length ? ` · ${observability.graph_nodes.join(" → ")}` : null}
          {observability.langfuse_url ? (
            <>
              {" · "}
              <a href={observability.langfuse_url} target="_blank" rel="noreferrer">
                Langfuse izi
              </a>
            </>
          ) : observability.langfuse_enabled ? (
            " · Langfuse açık (iz henüz yok)"
          ) : (
            " · Langfuse kapalı"
          )}
        </p>
      ) : null}
    </div>
  );
}
