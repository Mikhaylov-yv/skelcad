import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type AgentTask, type ProjectOverview, type TaskEvent } from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";

export function Agent() {
  const { project = "" } = useParams();
  const [params] = useSearchParams();
  const [info, setInfo] = useState<ProjectOverview | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [active, setActive] = useState<AgentTask | null>(null);
  const [text, setText] = useState("");
  const [variant, setVariant] = useState(params.get("variant") ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .tasks(project)
      .then((r) => {
        setTasks(r.tasks);
        setActive(r.active);
        setSelected((s) => s ?? r.active?.id ?? r.tasks[0]?.id ?? null);
      })
      .catch((e: Error) => setErr(e.message));
  }, [project]);
  useEffect(() => {
    load();
    api
      .projects()
      .then((r) => setInfo(r.projects.find((p) => p.name === project) ?? null))
      .catch(() => undefined);
  }, [project, load]);
  useEffect(() => {
    if (!active) return;
    const h = window.setInterval(load, 3000);
    return () => window.clearInterval(h);
  }, [active, load]);

  const run = () => {
    setBusy(true);
    setErr(null);
    api
      .taskCreate(project, text, variant || undefined)
      .then((t) => {
        setText("");
        setSelected(t.id);
        load();
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };

  return (
    <main className="agent">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span> <strong>{S.agent.title}</strong>
        </nav>
        <h1>
          {info?.title || project} · {S.agent.title}
        </h1>
        <div className="variant__numbers">
          <Link className="small" to={`/p/${encodeURIComponent(project)}/commits`}>
            {S.feed.tab}
          </Link>
        </div>
      </header>
      <div className="page agent__body">
        <section className="agent__form" aria-label={S.agent.title}>
          <p className="muted small">{S.agent.hint}</p>
          <textarea
            aria-label={S.agent.textLabel}
            rows={5}
            value={text}
            placeholder={S.agent.placeholder}
            onChange={(e) => setText(e.target.value)}
            disabled={!!active}
          />
          <div className="commit__actions">
            <label className="small">
              {S.agent.variant}:{" "}
              <select value={variant} onChange={(e) => setVariant(e.target.value)} disabled={!!active}>
                <option value="">{S.agent.anyVariant}</option>
                {info?.variants.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.id}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={run} disabled={!text.trim() || busy || !!active} aria-busy={busy}>
              {busy ? S.agent.starting : S.agent.run}
            </button>
            {active && (
              <span className="badge badge--warn" role="status">
                {S.agent.busy(active.id)} · {S.agent.status[active.status]}
              </span>
            )}
          </div>
          {err && (
            <p className="level-error" role="alert">
              {err}
            </p>
          )}
          <h3>{S.agent.history}</h3>
          {tasks.length === 0 && <p className="muted small">{S.agent.none}</p>}
          <ul className="tasks">
            {tasks.map((t) => (
              <li key={t.id}>
                <button className={"tree__item" + (selected === t.id ? " selected" : "")} onClick={() => setSelected(t.id)}>
                  <span>
                    <span className={"badge status-" + t.status}>{S.agent.status[t.status]}</span> {t.text.slice(0, 70)}
                  </span>
                  <span className="muted small">{relativeTime(t.created)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="agent__log" aria-label={S.agent.log}>
          {selected ? <TaskLog id={selected} project={project} onChange={load} /> : <p className="muted">{S.agent.noSelected}</p>}
        </section>
      </div>
    </main>
  );
}

function TaskLog({ id, project, onChange }: { id: string; project: string; onChange: () => void }) {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [task, setTask] = useState<AgentTask | null>(null);
  const [stopping, setStopping] = useState(false);
  const next = useRef(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    next.current = 0;
    setEvents([]);
    let alive = true;
    const tick = () =>
      api
        .taskEvents(id, next.current)
        .then((r) => {
          if (!alive) return;
          if (r.events.length) setEvents((e) => [...e, ...r.events]);
          next.current = r.next;
          setTask(r.task);
        })
        .catch(() => undefined);
    tick();
    const h = window.setInterval(() => {
      if (task && !["queued", "running"].includes(task.status)) return;
      tick();
    }, 2000);
    return () => {
      alive = false;
      window.clearInterval(h);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => {
    box.current?.scrollTo?.({ top: box.current.scrollHeight });
  }, [events.length]);

  const stop = () => {
    setStopping(true);
    api
      .taskStop(id)
      .then(() => onChange())
      .finally(() => setStopping(false));
  };
  const live = task && ["queued", "running"].includes(task.status);
  return (
    <>
      <div className="commit__actions">
        <h3 style={{ margin: 0 }}>{S.agent.log}</h3>
        {task && (
          <span className={"badge status-" + task.status} aria-live="polite">
            {S.agent.status[task.status]}
            {task.steps !== undefined ? ` · ${S.agent.steps(task.steps, task.max_steps)}` : ""}
          </span>
        )}
        {task && <span className="muted small">{S.agent.byUser(task.user)}</span>}
        {live && (
          <button className="danger" onClick={stop} disabled={stopping || task?.stop_requested} aria-busy={stopping}>
            {stopping || task?.stop_requested ? S.agent.stopping : S.agent.stop}
          </button>
        )}
        {task && !live && (
          <Link className="small" to={`/p/${encodeURIComponent(project)}/commits`}>
            {S.agent.toFeed}
          </Link>
        )}
      </div>
      <div className="log" ref={box}>
        {events.length === 0 && <p className="muted small">{S.agent.noEvents}</p>}
        {events.map((e, i) => (
          <div key={i} className={"log__line log__line--" + e.type}>
            {e.type === "tool_call" && (
              <>
                <span className="mono small muted">{S.agent.call}</span> <strong className="mono">{e.name}</strong>{" "}
                <span className="mono small muted">{JSON.stringify(e.args ?? {}).slice(0, 300)}</span>
              </>
            )}
            {e.type === "tool_result" && <pre className="small">{brief(e.text ?? "")}</pre>}
            {e.type === "assistant" && (
              <p>
                <span className="muted small">{S.agent.said}: </span>
                {e.text}
              </p>
            )}
            {e.type === "done" && (
              <div className="callout">
                <strong>{S.agent.result}</strong>
                <p style={{ whiteSpace: "pre-wrap" }}>{e.text}</p>
              </div>
            )}
            {e.type === "error" && (
              <p className="level-error" role="alert">
                {S.agent.error}: {e.text}
              </p>
            )}
            {(e.type === "stopped" || e.type === "limit") && <p className="level-warning">{S.agent.status[e.type]}</p>}
            {e.type === "start" && (
              <p className="muted small">
                {e.runner}
                {e.tools ? ` · инструментов ${e.tools}` : ""}
              </p>
            )}
          </div>
        ))}
      </div>
      {task?.error && !events.some((e) => e.type === "error") && (
        <p className="level-error" role="alert">
          {S.agent.error}: {task.error}
        </p>
      )}
    </>
  );
}

/** Результат инструмента: если это JSON со сводкой — показываем сводку, иначе начало текста. */
function brief(text: string, n = 500): string {
  try {
    const d = JSON.parse(text);
    if (d && typeof d === "object" && typeof d.summary === "string") return d.summary.slice(0, n);
  } catch {
    /* не JSON */
  }
  return text.slice(0, n);
}
