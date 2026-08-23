import { AgentStep } from "@/lib/api";

export function AgentRail({
  agents,
}: {
  agents?: AgentStep[];
  chainStatus?: string;
  observability?: unknown;
}) {
  if (!agents?.length) return null;
  return (
    <div className="agent-rail-wrap">
      <ol className="agent-rail" aria-label="İşlem adımları">
        {agents.map((agent) => (
          <li key={agent.id} className={agent.state}>
            <span className="agent-sticker" aria-hidden>
              {agent.state === "done" ? "●" : agent.state === "warn" ? "▲" : agent.state === "error" ? "✕" : "○"}
            </span>
            <span className="agent-title">{agent.title}</span>
            <span className="agent-summary">{agent.summary}</span>
            {agent.note ? <span className="agent-note">{agent.note}</span> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
