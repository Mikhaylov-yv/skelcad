import { useCallback, useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  api,
  attachmentUrl,
  type AgentTask,
  type Attachment,
  type ProjectOverview,
  type ProvidersResponse,
  type TaskEvent,
} from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.svg,.pdf,.excalidraw,image/png,image/jpeg,image/webp,image/svg+xml";

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
  const [files, setFiles] = useState<Attachment[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  // провайдер и модель (D29): пусто — провайдер по умолчанию и его модель
  const [providers, setProviders] = useState<ProvidersResponse | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const chosen = providers?.providers.find((p) => p.id === (provider || providers.default)) ?? null;

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
  const loadFiles = useCallback(
    () =>
      api
        .attachments(project)
        .then((r) => setFiles(r.items))
        .catch(() => undefined),
    [project],
  );
  useEffect(() => {
    load();
    loadFiles();
    api
      .projects()
      .then((r) => setInfo(r.projects.find((p) => p.name === project) ?? null))
      .catch(() => undefined);
    api
      .providers()
      .then(setProviders)
      .catch(() => setProviders(null));
  }, [project, load, loadFiles]);
  useEffect(() => {
    if (!active) return;
    const h = window.setInterval(load, 3000);
    return () => window.clearInterval(h);
  }, [active, load]);

  /** Загрузить файлы по одному: каждый — коммит конструктора; новые сразу отмечаются «к задаче». */
  const upload = (list: File[]) => {
    if (!list.length) return;
    setUploading(true);
    setErr(null);
    (async () => {
      for (const f of list) {
        const r = await api.attachmentUpload(project, f);
        setPicked((p) => new Set(p).add(r.item.path));
      }
    })()
      .catch((e: Error) => setErr(e.message))
      .finally(() => {
        setUploading(false);
        loadFiles();
      });
  };
  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    upload(Array.from(e.target.files ?? []));
    e.target.value = "";
  };
  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const pasted = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
    if (!pasted.length || active) return;
    e.preventDefault();
    upload(
      pasted.map((f, i) =>
        f.name && f.name !== "image.png" ? f : new File([f], `paste-${i + 1}.png`, { type: f.type }),
      ),
    );
  };
  const toggle = (path: string) =>
    setPicked((p) => {
      const n = new Set(p);
      if (n.has(path)) n.delete(path);
      else n.add(path);
      return n;
    });
  const remove = (f: Attachment) => {
    if (!window.confirm(S.agent.deleteConfirm(f.name))) return;
    setErr(null);
    api
      .attachmentDelete(project, f.name)
      .then(() => {
        setPicked((p) => {
          const n = new Set(p);
          n.delete(f.path);
          return n;
        });
        loadFiles();
      })
      .catch((e: Error) => setErr(e.message));
  };

  const run = () => {
    setBusy(true);
    setErr(null);
    api
      .taskCreate(project, text, variant || undefined, [...picked], provider || undefined, model.trim() || undefined)
      .then((t) => {
        setText("");
        setPicked(new Set());
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
          {info && info.variants.length === 0 && (
            <p className="callout small" role="note">
              {S.agent.emptyProject}
            </p>
          )}
          <textarea
            aria-label={S.agent.textLabel}
            rows={5}
            value={text}
            placeholder={S.agent.placeholder}
            onChange={(e) => setText(e.target.value)}
            onPaste={onPaste}
            disabled={!!active}
          />
          <section className="attachments" aria-label={S.agent.attachments}>
            <div className="commit__actions">
              <strong className="small">{S.agent.attachments}</strong>
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                disabled={!!active || uploading}
                aria-busy={uploading}
              >
                {uploading ? S.agent.uploading : S.agent.upload}
              </button>
              <input
                ref={fileInput}
                type="file"
                multiple
                accept={ACCEPT}
                aria-label={S.agent.upload}
                onChange={onPick}
                disabled={!!active || uploading}
                style={{ display: "none" }}
              />
              <span className="muted small">{S.agent.pasteHint}</span>
            </div>
            <p className="muted small" style={{ margin: 0 }}>
              {S.agent.attachmentsHint} {S.agent.accept}
            </p>
            {files.length === 0 ? (
              <p className="muted small" style={{ margin: 0 }}>
                {S.agent.noAttachments}
              </p>
            ) : (
              <ul className="attachments__list">
                {files.map((f) => (
                  <li key={f.path} className={"attachments__item" + (picked.has(f.path) ? " selected" : "")}>
                    <label>
                      <input
                        type="checkbox"
                        checked={picked.has(f.path)}
                        onChange={() => toggle(f.path)}
                        disabled={!!active}
                        aria-label={S.agent.attach(f.name)}
                      />
                      {f.kind === "image" || f.kind === "svg" ? (
                        <img src={attachmentUrl(project, f)} alt="" loading="lazy" />
                      ) : (
                        <span className="attachments__icon">{S.agent.kinds[f.kind] ?? f.kind}</span>
                      )}
                      <span className="attachments__text">
                        <span className="attachments__name mono small" title={f.path}>
                          {f.name}
                        </span>
                        <span className="attachments__meta">
                          {f.width ? `${f.width}×${f.height} · ` : ""}
                          {Math.max(1, Math.round(f.bytes / 1024))} КБ
                          {f.author ? ` · ${f.author}` : ""}
                        </span>
                      </span>
                    </label>
                    <a className="small" href={attachmentUrl(project, f)} target="_blank" rel="noreferrer">
                      {S.variant.showAll}
                    </a>
                    <button
                      type="button"
                      className="link small"
                      onClick={() => remove(f)}
                      disabled={!!active}
                      aria-label={S.agent.deleteFile(f.name)}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
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
            {providers && providers.providers.length > 0 && (
              <>
                <label className="small">
                  {S.agent.provider}:{" "}
                  <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={!!active}>
                    <option value="">
                      {S.agent.defaultProvider}
                      {providers.default
                        ? ` (${providers.providers.find((p) => p.id === providers.default)?.title ?? providers.default})`
                        : ""}
                    </option>
                    {providers.providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </label>
                {chosen?.kind === "openai" && (
                  <label className="small">
                    {S.agent.model}:{" "}
                    <input
                      list="task-models"
                      value={model}
                      placeholder={chosen.model || "—"}
                      onChange={(e) => setModel(e.target.value)}
                      disabled={!!active}
                      style={{ width: 220 }}
                    />
                    <datalist id="task-models">
                      {chosen.models.map((m) => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                  </label>
                )}
              </>
            )}
            {providers && providers.providers.length === 0 && (
              <span className="muted small">{S.agent.noProviders}</span>
            )}
            <button onClick={run} disabled={!text.trim() || busy || !!active} aria-busy={busy}>
              {busy ? S.agent.starting : S.agent.run}
            </button>
            {picked.size > 0 && <span className="muted small">{S.agent.withTask(picked.size)}</span>}
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
                <button
                  className={"tree__item" + (selected === t.id ? " selected" : "")}
                  onClick={() => setSelected(t.id)}
                >
                  <span>
                    <span className={"badge status-" + t.status}>{S.agent.status[t.status]}</span> {t.text.slice(0, 70)}
                    {t.attachments?.length ? (
                      <span className="muted small"> · {S.agent.withTask(t.attachments.length)}</span>
                    ) : null}
                    {t.model ? <span className="muted small"> · {t.model}</span> : null}
                  </span>
                  <span className="muted small">{relativeTime(t.created)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="agent__log" aria-label={S.agent.log}>
          {selected ? (
            <TaskLog key={selected} id={selected} project={project} onChange={load} />
          ) : (
            <p className="muted">{S.agent.noSelected}</p>
          )}
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
  const latest = useRef<AgentTask | null>(null); // статус из последнего опроса — для остановки опроса без замыкания на старом state
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    next.current = 0;
    latest.current = null;
    setEvents([]);
    setTask(null);
    let alive = true;
    const tick = () =>
      api
        .taskEvents(id, next.current)
        .then((r) => {
          if (!alive) return;
          if (r.events.length) setEvents((e) => [...e, ...r.events]);
          next.current = r.next;
          latest.current = r.task;
          setTask(r.task);
        })
        .catch(() => undefined);
    tick();
    const h = window.setInterval(() => {
      const t = latest.current;
      if (t && !["queued", "running"].includes(t.status) && next.current >= 1) {
        // задача завершена: дочитать хвост событий ещё раз и остановиться
        tick();
        window.clearInterval(h);
        return;
      }
      tick();
    }, 2000);
    return () => {
      alive = false;
      window.clearInterval(h);
    };
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
        {task?.model && <span className="mono small muted">{task.model}</span>}
        {task?.usage && <span className="muted small">{S.agent.usage(task.usage)}</span>}
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
      {task?.attachments?.length ? (
        <p className="chips small" aria-label={S.agent.taskAttachments}>
          <span className="muted">{S.agent.taskAttachments}:</span>
          {task.attachments.map((a) => (
            <a key={a} className="mono" href={attachmentUrl(project, a)} target="_blank" rel="noreferrer">
              {a.replace(/^attachments\//, "")}
            </a>
          ))}
        </p>
      ) : null}
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
            {e.type === "attachment" && (
              <p className="muted small">
                {S.agent.sentAttachment(e.path ?? "", e.images ?? 0)}
                {e.path ? (
                  <>
                    {" "}
                    <a href={attachmentUrl(project, e.path)} target="_blank" rel="noreferrer">
                      {S.variant.showAll}
                    </a>
                  </>
                ) : null}
              </p>
            )}
            {e.type === "images" && <p className="muted small">{S.agent.sentImages(e.count ?? 1)}</p>}
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
                {e.provider ? ` · ${e.provider}` : ""}
                {e.model ? ` · ${e.model}` : ""}
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
