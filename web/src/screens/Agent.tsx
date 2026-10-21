import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type ClipboardEvent } from "react";
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
import { buildSteps, commitsOf, nowOf, type Step } from "../ui/agentSteps";
import { Glyph } from "../ui/Glyph";
import { Markdown, firstLine } from "../ui/Markdown";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.svg,.pdf,.excalidraw,image/png,image/jpeg,image/webp,image/svg+xml";

/** Экран «Агент»: слева задача (текст, вложения, модель) и список задач, справа — ход работы словами и отчёт. */
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
  const locked = !!active;
  const layoutUrl =
    info && info.variants.length > 0
      ? `/p/${encodeURIComponent(project)}/${encodeURIComponent(info.variants[0].id)}?mode=layout`
      : `/p/${encodeURIComponent(project)}/layout`;

  return (
    <main className="agent">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span> <strong>{S.agent.tab}</strong>
        </nav>
        <h1>
          {info?.title || project} · {S.agent.tab}
        </h1>
        <div className="variant__numbers">
          <Link className="small" to={`/p/${encodeURIComponent(project)}/commits`}>
            {S.feed.tab}
          </Link>
          <Link className="small" to={layoutUrl}>
            {S.layout.tab}
          </Link>
        </div>
      </header>
      <div className="page agent__body">
        <section className="agent__side">
          <form
            className="composer card"
            aria-label={S.agent.title}
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim() && !busy && !locked) run();
            }}
          >
            {info && info.variants.length === 0 && (
              <p className="composer__empty small" role="note">
                {S.agent.emptyProject}
              </p>
            )}
            {locked && (
              <p className="composer__locked small" role="status">
                <Glyph name="wait" /> {S.agent.busyShort}
              </p>
            )}
            <textarea
              aria-label={S.agent.textLabel}
              rows={4}
              value={text}
              placeholder={S.agent.placeholder}
              onChange={(e) => setText(e.target.value)}
              onPaste={onPaste}
              disabled={locked}
            />
            <div className="composer__files" aria-label={S.agent.attachments}>
              {files.map((f) => (
                <label
                  key={f.path}
                  className={"filechip" + (picked.has(f.path) ? " selected" : "")}
                  title={`${f.name}${f.width ? ` · ${f.width}×${f.height}` : ""} · ${Math.max(1, Math.round(f.bytes / 1024))} КБ${f.author ? ` · ${f.author}` : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={picked.has(f.path)}
                    onChange={() => toggle(f.path)}
                    disabled={locked}
                    aria-label={S.agent.attach(f.name)}
                  />
                  {f.kind === "image" || f.kind === "svg" ? (
                    <img src={attachmentUrl(project, f)} alt="" loading="lazy" />
                  ) : (
                    <span className="filechip__icon">{S.agent.kinds[f.kind] ?? f.kind}</span>
                  )}
                  <span className="filechip__name">{f.name}</span>
                  <button
                    type="button"
                    className="filechip__x"
                    onClick={(e) => {
                      e.preventDefault();
                      remove(f);
                    }}
                    disabled={locked}
                    aria-label={S.agent.deleteFile(f.name)}
                  >
                    ×
                  </button>
                </label>
              ))}
              <button
                type="button"
                className="ghost"
                onClick={() => fileInput.current?.click()}
                disabled={locked || uploading}
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
                disabled={locked || uploading}
                style={{ display: "none" }}
              />
            </div>
            <div className="composer__row">
              {info && info.variants.length > 0 && (
                <label>
                  {S.agent.variant}
                  <select value={variant} onChange={(e) => setVariant(e.target.value)} disabled={locked}>
                    <option value="">{S.agent.anyVariant}</option>
                    {info.variants.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.id}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {providers && providers.providers.length > 0 && (
                <label>
                  {S.agent.provider}
                  <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={locked}>
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
              )}
              {chosen?.kind === "openai" && (
                <label>
                  {S.agent.model}
                  <input
                    list="task-models"
                    value={model}
                    placeholder={chosen.model || "—"}
                    onChange={(e) => setModel(e.target.value)}
                    disabled={locked}
                  />
                  <datalist id="task-models">
                    {chosen.models.map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                </label>
              )}
            </div>
            {providers && providers.providers.length === 0 && (
              <p className="muted small" style={{ margin: 0 }}>
                {S.agent.noProviders}
              </p>
            )}
            <div className="composer__actions">
              <button type="submit" className="primary" disabled={!text.trim() || busy || locked} aria-busy={busy}>
                {busy ? S.agent.starting : S.agent.run}
              </button>
              {picked.size > 0 && <span className="muted small">{S.agent.withTask(picked.size)}</span>}
              <details className="help">
                <summary className="small">{S.agent.help}</summary>
                <p className="small muted">{S.agent.hint}</p>
                <p className="small muted">
                  {S.agent.attachmentsHint} {S.agent.pasteHint} {S.agent.accept}
                </p>
              </details>
            </div>
            {err && (
              <p className="level-error small" role="alert" style={{ margin: 0 }}>
                {err}
              </p>
            )}
          </form>
          <h3>{S.agent.history}</h3>
          {tasks.length === 0 && <p className="muted small">{S.agent.none}</p>}
          <ul className="tasks">
            {tasks.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className={"task" + (selected === t.id ? " selected" : "")}
                  onClick={() => setSelected(t.id)}
                  aria-current={selected === t.id ? "true" : undefined}
                >
                  <StatusDot status={t.status} />
                  <span className="task__text">{t.text}</span>
                  <span className="muted small task__time">{relativeTime(t.created)}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="work card" aria-label={S.agent.work}>
          {selected ? (
            <Progress key={selected} id={selected} project={project} layoutUrl={layoutUrl} onChange={load} />
          ) : (
            <p className="muted">{S.agent.noSelected}</p>
          )}
        </section>
      </div>
    </main>
  );
}

function StatusDot({ status }: { status: AgentTask["status"] }) {
  return <span className={"dot dot--" + status} title={S.agent.status[status]} />;
}

/** Ход работы одной задачи: состояние, отчёт, шаги словами; сырые данные — по кнопке «Подробности». */
export function Progress({
  id,
  project,
  layoutUrl,
  onChange,
  compact = false,
}: {
  id: string;
  project: string;
  layoutUrl: string;
  onChange: () => void;
  compact?: boolean;
}) {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [task, setTask] = useState<AgentTask | null>(null);
  const [stopping, setStopping] = useState(false);
  const [details, setDetails] = useState(false);
  const next = useRef(0);
  const latest = useRef<AgentTask | null>(null); // статус из последнего опроса — для остановки опроса без замыкания на старом state
  const list = useRef<HTMLOListElement>(null);

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

  const live = !!task && ["queued", "running"].includes(task.status);
  const steps = useMemo(() => buildSteps(events), [events]);
  const commits = commitsOf(steps);
  const touchedLayout = steps.some((s) => s.commit && /project\.yaml/.test(s.details ?? ""));
  const done = events.find((e) => e.type === "done");
  const fail = events.find((e) => e.type === "error")?.text ?? task?.error ?? null;
  // живая задача: список прокручивается к последнему шагу, часы тикают
  useEffect(() => {
    if (live) list.current?.scrollTo?.({ top: list.current.scrollHeight });
  }, [events.length, live]);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const h = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(h);
  }, [live]);

  const stop = () => {
    setStopping(true);
    api
      .taskStop(id)
      .then(() => onChange())
      .finally(() => setStopping(false));
  };
  const took = task?.started && task?.finished ? (Date.parse(task.finished) - Date.parse(task.started)) / 1000 : null;
  const last = events[events.length - 1];
  const since = live && last ? Math.max(0, (now - Date.parse(last.t)) / 1000) : 0;
  const headline = !task
    ? ""
    : live
      ? `${task.status === "queued" ? S.agent.finished.queued : nowOf(steps)}${since >= 3 ? ` · ${S.duration(since)}` : ""}`
      : task.status === "done"
        ? S.agent.finished.done(took !== null ? S.duration(took) : "")
        : S.agent.finished[task.status];
  return (
    <>
      <div className="work__head">
        {task && !compact && (
          <span className={"pill pill--" + task.status} aria-live="polite">
            {S.agent.status[task.status]}
          </span>
        )}
        <span className="work__now" aria-live="polite">
          {headline}
        </span>
        {live && !compact && (
          <button className="danger" onClick={stop} disabled={stopping || task?.stop_requested} aria-busy={stopping}>
            {stopping || task?.stop_requested ? S.agent.stopping : S.agent.stop}
          </button>
        )}
      </div>
      {task && (
        <p className="work__meta muted small">
          {[
            task.model,
            task.steps !== undefined ? S.agent.steps(task.steps, task.max_steps) : "",
            task.usage ? S.agent.usage(task.usage) : "",
            `${S.agent.byUser(task.user)} · ${relativeTime(task.created)}`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
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
      {task && !live && task.status === "done" && !compact && (
        <section className="report" aria-label={S.agent.result}>
          <h3>{S.agent.result}</h3>
          {done?.text?.trim() ? <Markdown text={done.text} /> : <p className="muted">{S.agent.noResult}</p>}
          <p className="report__links small">
            {commits.length ? (
              <>
                {S.agent.changes(commits.length)} ·{" "}
                <Link to={`/p/${encodeURIComponent(project)}/commits`}>{S.agent.seeFeed}</Link>
              </>
            ) : (
              <span className="muted">{S.agent.noChanges}</span>
            )}
            {touchedLayout && (
              <>
                {" · "}
                {S.agent.layoutWaiting} · <Link to={layoutUrl}>{S.agent.openLayout}</Link>
              </>
            )}
          </p>
        </section>
      )}
      {fail && !compact && (
        <p className="callout callout--error" role="alert">
          <strong>{S.agent.error}:</strong> {fail}
        </p>
      )}
      {task && !live && !compact && (task.status === "stopped" || task.status === "limit") && (
        <p className="callout">{S.agent.finished[task.status]}</p>
      )}
      <div className="work__steps-head">
        <h3>{S.agent.stepsTitle(steps.filter((s) => s.kind === "call").length)}</h3>
        {steps.length > 0 && (
          <button
            type="button"
            className="link small"
            onClick={() => setDetails((d) => !d)}
            aria-pressed={details}
            title={S.agent.detailsHint}
          >
            {details ? S.agent.detailsHide : S.agent.details}
          </button>
        )}
      </div>
      <ol className="steps" ref={list}>
        {steps.length === 0 && task && (
          <li className="step step--wait">
            <Glyph name="wait" />
            <span className="muted small">{S.agent.noEvents}</span>
          </li>
        )}
        {steps.map((s) => (
          <StepRow key={s.i} s={s} id={id} project={project} details={details} />
        ))}
        {live && task?.status === "running" && !steps[steps.length - 1]?.pending && (
          <li className="step step--pending" aria-live="polite">
            <Glyph name="spin" className="spin" />
            <span className="step__text">{S.steps.thinking}</span>
          </li>
        )}
      </ol>
    </>
  );
}

function StepRow({ s, id, project, details }: { s: Step; id: string; project: string; details: boolean }) {
  if (s.kind === "note") {
    const short = s.text.length <= 160 && !s.text.includes("\n");
    return (
      <li className="step step--note">
        <Glyph name="note" />
        {short ? (
          <span className="step__text">{s.text}</span>
        ) : (
          <details className="step__note">
            <summary>{firstLine(s.text)}</summary>
            <Markdown text={s.text} className="small" />
          </details>
        )}
      </li>
    );
  }
  const cls =
    "step" +
    (s.failed ? " step--failed" : "") +
    (s.pending ? " step--pending" : "") +
    (s.kind === "start" ? " step--start" : "");
  return (
    <li className={cls}>
      <Glyph name={s.failed ? "error" : s.pending ? "spin" : s.glyph} className={s.pending ? "spin" : undefined} />
      <div className="step__body">
        <span className="step__text">{s.text}</span>
        {s.outcome && (
          <span className={"step__outcome" + (s.failed ? " level-error" : "")} title={s.outcome}>
            {s.outcome}
          </span>
        )}
        {(s.images?.length || s.url) && (
          <span className="step__images">
            {s.url && (
              <a href={attachmentUrl(project, s.url)} target="_blank" rel="noreferrer">
                <img src={attachmentUrl(project, s.url)} alt={S.agent.imageAlt} loading="lazy" />
              </a>
            )}
            {s.images?.map((f) => (
              <a key={f} href={api.taskFileUrl(id, f)} target="_blank" rel="noreferrer">
                <img src={api.taskFileUrl(id, f)} alt={S.agent.imageAlt} loading="lazy" />
              </a>
            ))}
          </span>
        )}
        {details && s.details && <pre className="step__raw small">{s.details}</pre>}
      </div>
      {s.seconds !== undefined && s.seconds >= 1 && (
        <span className="step__time muted small">{S.duration(s.seconds)}</span>
      )}
    </li>
  );
}
