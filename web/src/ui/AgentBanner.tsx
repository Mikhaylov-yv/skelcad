import { Link } from "react-router-dom";
import type { ProjectOverview } from "../api";
import { S } from "../strings";

/** Полоса «проект у агента» — на экранах, где есть правки (D6: очерёдность). */
export function AgentBanner({ p }: { p: ProjectOverview | null }) {
  if (!p || p.state !== "agent" || !p.task) return null;
  return (
    <div className="banner banner--agent" role="status">
      <strong>{S.agent.busy(p.task.id)}</strong> · {S.agent.status[p.task.status]} · «{p.task.text.slice(0, 80)}»
      <span className="muted"> — {S.agent.busyHint} </span>
      <Link to={`/p/${encodeURIComponent(p.name)}/agent`}>{S.agent.tab}</Link>
    </div>
  );
}
