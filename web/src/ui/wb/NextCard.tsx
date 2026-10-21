import type { ProjectOverview } from "../../api";
import { S } from "../../strings";

const CLS: Record<string, string> = { you: "next--wait", agent: "", running: "next--agent", done: "next--done" };

/** Единственный следующий шаг проекта: янтарная карточка — решение за конструктором, синяя — ход у агента.
 *  Одна залитая кнопка на экран — здесь (D31, D32). */
export function NextCard({
  p,
  onAct,
  busy,
  stack = false,
}: {
  p: ProjectOverview;
  onAct: (act: string) => void;
  busy?: string | null;
  stack?: boolean;
}) {
  const n = p.next;
  let button;
  if (n.kind === "running")
    button = (
      <button type="button" className="small" onClick={() => onAct("stop")} disabled={busy === "stop"}>
        {busy === "stop" ? S.agent.stopping : S.agent.stop}
      </button>
    );
  else if (n.kind === "done")
    button = (
      <button type="button" onClick={() => onAct(n.act)}>
        {n.label}
      </button>
    );
  else
    button = (
      <button
        type="button"
        className="primary"
        onClick={() => onAct(n.act)}
        disabled={!!busy}
        aria-busy={busy === n.act}
        data-act={n.act}
      >
        {busy === n.act ? S.wb.working : n.label}
      </button>
    );
  return (
    <div className={"next " + CLS[n.kind] + (stack ? " next--stack" : "")} data-next={n.act} role="status">
      <div className="next__t">
        <b>
          {n.kind === "running" && <span className="spin" aria-hidden="true" />}
          {n.title}
        </b>
        <span>{n.hint}</span>
      </div>
      {button}
    </div>
  );
}
