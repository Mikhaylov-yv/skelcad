import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type CommitDiff, type FeedCommit, type ProjectOverview } from "../api";
import { S } from "../strings";
import { humanAuthor, relativeTime } from "../ui/format";
import { DeltaRow } from "../ui/DeltaRow";
import { Viewer, type ViewName } from "../three/Viewer";
import { AgentBanner } from "../ui/AgentBanner";

type State =
  { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; commits: FeedCommit[]; unreviewed: number };

export function Feed() {
  const { project = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [info, setInfo] = useState<ProjectOverview | null>(null);
  const variant = params.get("variant") ?? info?.variants[0]?.id ?? "";

  const load = useCallback(() => {
    api
      .commits(project)
      .then((r) => setSt({ kind: "ok", commits: r.commits, unreviewed: r.unreviewed }))
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  }, [project]);
  useEffect(() => {
    setSt({ kind: "loading" });
    load();
    api
      .projects()
      .then((r) => setInfo(r.projects.find((p) => p.name === project) ?? null))
      .catch(() => setInfo(null));
  }, [project, load]);

  return (
    <main className="feed">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span> <strong>{S.feed.title}</strong>
        </nav>
        <h1>
          {info?.title || project} · {S.feed.title}
        </h1>
        <div className="variant__numbers">
          {st.kind === "ok" && (
            <span className={st.unreviewed ? "badge badge--warn" : "muted small"} aria-live="polite">
              {S.feed.unreviewed(st.unreviewed)}
            </span>
          )}
          {info && info.variants.length > 0 && (
            <label className="small">
              {S.feed.variantForDiff}:{" "}
              <select
                value={variant}
                onChange={(e) => {
                  const p = new URLSearchParams(params);
                  p.set("variant", e.target.value);
                  setParams(p, { replace: true });
                }}
              >
                {info.variants.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.id}
                  </option>
                ))}
              </select>
            </label>
          )}
          {variant && (
            <Link className="small" to={`/p/${encodeURIComponent(project)}/${encodeURIComponent(variant)}`}>
              {S.feed.toVariant(variant)}
            </Link>
          )}
          <Link className="small" to={`/p/${encodeURIComponent(project)}/compare`}>
            {S.compare.tab}
          </Link>
          <Link className="small" to={`/p/${encodeURIComponent(project)}/agent`}>
            {S.agent.tab}
          </Link>
        </div>
      </header>
      <AgentBanner p={info} />
      <div className="page feed__body">
        {st.kind === "loading" && <p className="muted">{S.feed.loading}</p>}
        {st.kind === "error" && (
          <div className="callout callout--error" role="alert">
            <p>
              {S.errors.load}: {st.message}
            </p>
            <button onClick={load}>{S.errors.retry}</button>
          </div>
        )}
        {st.kind === "ok" && st.commits.length === 0 && <p className="empty">{S.feed.empty}</p>}
        {st.kind === "ok" && (
          <ol className="commits" aria-label={S.feed.title}>
            {st.commits.map((c) => (
              <li key={c.hash}>
                <CommitCard
                  c={c}
                  project={project}
                  variant={variant}
                  onChanged={load}
                  locked={info?.state === "agent"}
                />
              </li>
            ))}
          </ol>
        )}
      </div>
    </main>
  );
}

function CommitCard({
  c,
  project,
  variant,
  onChanged,
  locked = false,
}: {
  c: FeedCommit;
  project: string;
  variant: string;
  onChanged: () => void;
  locked?: boolean;
}) {
  const a = humanAuthor(c.author);
  const [open, setOpen] = useState(false);
  const [diff, setDiff] = useState<CommitDiff | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [revertOpen, setRevertOpen] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [revertErr, setRevertErr] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(c.reviewed);
  const [three, setThree] = useState<{ now: string; was: string } | null>(null);
  const [threeErr, setThreeErr] = useState<string | null>(null);
  const [threeBusy, setThreeBusy] = useState(false);
  const [mix, setMix] = useState(0.6);
  const [view, setView] = useState<{ name: ViewName; nonce: number }>({ name: "iso", nonce: 0 });

  useEffect(() => setReviewed(c.reviewed), [c.reviewed]);

  const showDiff = () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (diff || !variant) return;
    setBusy(true);
    setDiffErr(null);
    api
      .commitDiff(project, c.hash, variant)
      .then(setDiff)
      .catch((e: Error) => setDiffErr(e.message))
      .finally(() => setBusy(false));
  };

  const show3d = () => {
    if (three) {
      setThree(null);
      return;
    }
    if (!diff?.a) return;
    setThreeBusy(true);
    setThreeErr(null);
    Promise.all([api.commitModel(project, c.hash, variant), api.commitModel(project, diff.a, variant)])
      .then(([now, was]) => setThree({ now: now.url, was: was.url }))
      .catch((e: Error) => setThreeErr(e.message))
      .finally(() => setThreeBusy(false));
  };

  const toggleReviewed = (v: boolean) => {
    setReviewed(v ? { by: "…", at: null } : null);
    api
      .setReviewed(project, c.hash, v)
      .then((r) => {
        setReviewed(r.reviewed);
        onChanged();
      })
      .catch(() => setReviewed(c.reviewed));
  };

  const doRevert = () => {
    setReverting(true);
    setRevertErr(null);
    api
      .revert(project, c.hash)
      .then(() => {
        setRevertOpen(false);
        onChanged();
      })
      .catch((e: Error) => setRevertErr(e.message))
      .finally(() => setReverting(false));
  };

  const changed = useMemo(() => {
    if (!diff) return [];
    const ids = new Set<string>();
    for (const [name, d] of Object.entries(diff.entities)) {
      if (!["parts", "fasteners"].includes(name)) continue;
      for (const id of [...(d.added ?? []), ...(d.removed ?? []), ...Object.keys(d.changed ?? {})]) ids.add(id);
    }
    return [...ids];
  }, [diff]);

  return (
    <article className={"commit commit--" + c.kind} aria-label={c.message}>
      <header className="commit__head">
        <span className={"author author--" + (c.kind === "agent" ? "agent" : "human")}>{a.label}</span>
        <span className="muted small">
          {S.feed.kind[c.kind]} · {relativeTime(c.date)}
        </span>
        {c.is_head && <span className="badge">{S.feed.head}</span>}
        {reviewed && <span className="badge badge--ok">{S.feed.reviewedBy(reviewed.by)}</span>}
        <span className="mono muted small commit__hash" title={c.hash}>
          {c.commit}
        </span>
      </header>
      <p className="commit__message">{c.message}</p>
      {c.files.length > 0 && (
        <p className="muted small mono commit__files">
          {S.feed.files}: {c.files.join(", ")}
        </p>
      )}
      <div className="commit__actions">
        <button onClick={showDiff} aria-expanded={open} disabled={!variant}>
          {open ? S.feed.hideDiff : S.feed.diff}
        </button>
        {c.kind === "agent" && (
          <label className="small">
            <input type="checkbox" checked={!!reviewed} onChange={(e) => toggleReviewed(e.target.checked)} />{" "}
            {S.feed.reviewed}
          </label>
        )}
        {c.kind !== "system" && (
          <button className="danger" onClick={() => setRevertOpen(true)} disabled={locked}>
            {S.feed.revert}
          </button>
        )}
      </div>

      {open && (
        <section className="commit__diff" aria-label={S.feed.diff}>
          {busy && (
            <p className="muted" aria-live="polite">
              {S.feed.diffLoading}
            </p>
          )}
          {diffErr && (
            <p className="level-error" role="alert">
              {diffErr}
            </p>
          )}
          {diff && !diff.a && <p className="muted">{S.feed.first}</p>}
          {diff && diff.a && (
            <>
              <p className="muted small">
                {S.feed.diffFor} <span className="mono">{diff.variant}</span>
              </p>
              <DeltaRow d={diff} />
              <Entities d={diff} />
              {diff.findings.added.length > 0 && (
                <div className="findings-lines">
                  <h4 className="level-warning">{S.feed.findingsAdded}</h4>
                  <ul>
                    {diff.findings.added.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              {diff.findings.removed.length > 0 && (
                <div className="findings-lines">
                  <h4 className="ok">{S.feed.findingsRemoved}</h4>
                  <ul>
                    {diff.findings.removed.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="commit__actions">
                <button onClick={show3d} disabled={threeBusy} aria-busy={threeBusy}>
                  {three ? S.feed.hide3d : S.feed.diff3d}
                </button>
                {threeBusy && (
                  <span className="muted small" aria-live="polite">
                    {S.feed.model3dLoading}
                  </span>
                )}
                {threeErr && (
                  <span className="level-error" role="alert">
                    {threeErr}
                  </span>
                )}
              </div>
              {three && (
                <div className="overlay">
                  <div className="toolbar">
                    <span className="small">{S.feed.was}</span>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={mix}
                      aria-label={`${S.feed.was} ↔ ${S.feed.now}`}
                      onChange={(e) => setMix(Number(e.target.value))}
                    />
                    <span className="small">{S.feed.now}</span>
                    {(["main", "left", "top", "iso"] as ViewName[]).map((v) => (
                      <button
                        key={v}
                        onClick={() => setView({ name: v, nonce: view.nonce + 1 })}
                        aria-pressed={view.name === v}
                      >
                        {S.variant.views[v]}
                      </button>
                    ))}
                    <span className="muted small">{S.feed.legend}</span>
                  </div>
                  <div className="canvas canvas--overlay">
                    <Viewer
                      url={three.now}
                      selected={[]}
                      dim={false}
                      clip={{ on: false, axis: "x", pos: 0.5 }}
                      view={view}
                      overlay={{ baseUrl: three.was, changed, mix }}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </section>
      )}

      {revertOpen && (
        <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={`rv-${c.commit}`}>
          <div className="dialog__box">
            <h2 id={`rv-${c.commit}`}>{S.feed.revertTitle}</h2>
            <p>
              <strong>{c.message}</strong> — {a.label}, {relativeTime(c.date)}
            </p>
            <p className="small muted">{S.feed.revertHint}</p>
            {c.files.length > 0 && (
              <p className="small">
                {S.feed.revertFiles}: <span className="mono">{c.files.join(", ")}</span>
              </p>
            )}
            {diff && diff.a && (
              <div className="small">
                <span className="muted">{S.feed.diff}: </span>
                <DeltaRow d={diff} />
              </div>
            )}
            {revertErr && (
              <p className="level-error" role="alert">
                {revertErr}
              </p>
            )}
            <div className="dialog__actions">
              <button onClick={() => setRevertOpen(false)} disabled={reverting}>
                {S.feed.cancel}
              </button>
              <button className="danger" onClick={doRevert} disabled={reverting} aria-busy={reverting}>
                {reverting ? S.feed.reverting : S.feed.revertConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function Entities({ d }: { d: CommitDiff }) {
  const rows = Object.entries(d.entities);
  if (rows.length === 0) return <p className="muted small">{S.feed.nothing}</p>;
  return (
    <dl className="kv entities">
      {rows.map(([name, e]) => (
        <div key={name}>
          <dt className="mono">{name}</dt>
          <dd>
            {e.added?.length ? `${S.feed.added}: ${e.added.join(", ")}; ` : ""}
            {e.removed?.length ? `${S.feed.removed}: ${e.removed.join(", ")}; ` : ""}
            {e.changed && Object.keys(e.changed).length
              ? `${S.feed.changed}: ${Object.entries(e.changed)
                  .map(
                    ([id, f]) =>
                      `${id} (${Array.isArray(f) ? f.join("→") : typeof f === "object" && f ? Object.keys(f).join(", ") : String(f)})`,
                  )
                  .join(", ")}`
              : ""}
          </dd>
        </div>
      ))}
    </dl>
  );
}
