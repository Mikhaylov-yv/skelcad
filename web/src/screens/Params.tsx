import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type DraftResponse, type ParamField } from "../api";
import { S } from "../strings";
import { NumbersRow } from "../ui/NumbersRow";
import { DeltaRow } from "../ui/DeltaRow";
import { Viewer, type ViewName } from "../three/Viewer";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; fields: ParamField[]; file: string };

function same(a: ParamField["value"], b: string | number | boolean): boolean {
  if (typeof a === "number") return Number(b) === a;
  if (typeof a === "boolean") return Boolean(b) === a;
  return String(a ?? "") === String(b);
}

export function Params() {
  const { project = "", variant = "" } = useParams();
  const nav = useNavigate();
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [values, setValues] = useState<Record<string, string | number | boolean>>({});
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [draftFor, setDraftFor] = useState<string>("");
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [mix, setMix] = useState(0.7);
  const [view, setView] = useState<{ name: ViewName; nonce: number }>({ name: "iso", nonce: 0 });
  const timer = useRef<number | null>(null);

  const load = useCallback(() => {
    setSt({ kind: "loading" });
    api
      .params(project, variant)
      .then((r) => {
        setSt({ kind: "ok", fields: r.fields, file: r.file });
        setValues(Object.fromEntries(r.fields.map((f) => [f.path, f.value ?? ""])) as Record<string, string | number | boolean>);
      })
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  }, [project, variant]);
  useEffect(load, [load]);

  const fields = st.kind === "ok" ? st.fields : [];
  const changes = useMemo(() => {
    const out: Record<string, string | number | boolean> = {};
    for (const f of fields) {
      const v = values[f.path];
      if (v !== undefined && !same(f.value, v)) out[f.path] = v;
    }
    return out;
  }, [fields, values]);
  const changesKey = JSON.stringify(changes);
  const invalid = useMemo(() => {
    const bad: Record<string, string> = {};
    for (const f of fields) {
      if (f.type !== "number") continue;
      const v = String(values[f.path] ?? "").replace(",", ".");
      if (v.trim() === "" || Number.isNaN(Number(v))) bad[f.path] = S.params.invalid;
      else if (Number(v) < 0 && typeof f.value === "number" && f.value >= 0) bad[f.path] = S.params.negative;
    }
    return bad;
  }, [fields, values]);
  const hasChanges = Object.keys(changes).length > 0;
  const draftFresh = draft !== null && draftFor === changesKey;

  const buildDraft = () => {
    setErr(null);
    setBusy(0);
    const t0 = Date.now();
    timer.current = window.setInterval(() => setBusy(Math.round((Date.now() - t0) / 1000)), 1000);
    api
      .draft(project, variant, changes)
      .then((d) => {
        setDraft(d);
        setDraftFor(changesKey);
        if (!message) setMessage(defaultMessage(changes, fields));
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => {
        if (timer.current) window.clearInterval(timer.current);
        setBusy(null);
      });
  };

  const save = () => {
    setErr(null);
    setSaving(true);
    api
      .saveParams(project, variant, changes, message, draftFresh ? draft!.draft : null)
      .then(() => nav(`/p/${encodeURIComponent(project)}/${encodeURIComponent(variant)}`))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setSaving(false));
  };

  const groups = useMemo(() => {
    const g = new Map<string, ParamField[]>();
    for (const f of fields) {
      const head = f.path.includes(".") ? f.path.split(".")[0] : "";
      g.set(head, [...(g.get(head) ?? []), f]);
    }
    return [...g.entries()];
  }, [fields]);

  const changedNodes = useMemo(() => {
    if (!draft) return [];
    const ids = new Set<string>();
    for (const [name, d] of Object.entries(draft.diff.entities)) {
      if (!["parts", "fasteners"].includes(name)) continue;
      for (const id of [...(d.added ?? []), ...(d.removed ?? []), ...Object.keys(d.changed ?? {})]) ids.add(id);
    }
    return [...ids];
  }, [draft]);

  return (
    <main className="params">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span>{" "}
          <Link to={`/p/${encodeURIComponent(project)}/${encodeURIComponent(variant)}`} className="mono">
            {variant}
          </Link>{" "}
          <span className="muted">/</span> <strong>{S.params.title}</strong>
        </nav>
        <h1>
          {S.params.title} · <span className="mono">{variant}</span>
        </h1>
        <div className="variant__numbers">
          <span className="muted small">{S.params.hint}</span>
        </div>
      </header>
      <div className="page params__body">
        {st.kind === "loading" && <p className="muted">{S.params.loading}</p>}
        {st.kind === "error" && (
          <div className="callout callout--error" role="alert">
            <p>
              {S.errors.load}: {st.message}
            </p>
            <button onClick={load}>{S.errors.retry}</button>
          </div>
        )}
        {st.kind === "ok" && (
          <div className="params__grid">
            <form
              className="params__form"
              onSubmit={(e) => {
                e.preventDefault();
                if (hasChanges && Object.keys(invalid).length === 0) buildDraft();
              }}
            >
              {groups.map(([head, list]) => (
                <fieldset key={head || "_"}>
                  <legend className="mono">{head || "—"}</legend>
                  {list.map((f) => {
                    const changed = f.path in changes;
                    const id = "p-" + f.path.replace(/\./g, "-");
                    return (
                      <div key={f.path} className={"field" + (changed ? " field--changed" : "") + (invalid[f.path] ? " field--bad" : "")}>
                        <label htmlFor={id}>
                          <span className="mono">{f.path.includes(".") ? f.path.slice(head.length + 1) : f.path}</span>
                          <span className={"badge badge--src small " + f.source} title={S.params.source[f.source]}>
                            {S.params.source[f.source]}
                          </span>
                        </label>
                        {f.type === "boolean" ? (
                          <input
                            id={id}
                            type="checkbox"
                            checked={Boolean(values[f.path])}
                            onChange={(e) => setValues({ ...values, [f.path]: e.target.checked })}
                          />
                        ) : (
                          <input
                            id={id}
                            type={f.type === "number" ? "text" : "text"}
                            inputMode={f.type === "number" ? "decimal" : undefined}
                            value={String(values[f.path] ?? "")}
                            aria-invalid={!!invalid[f.path]}
                            aria-describedby={invalid[f.path] ? id + "-err" : undefined}
                            onChange={(e) => setValues({ ...values, [f.path]: e.target.value })}
                          />
                        )}
                        {changed && (
                          <span className="muted small">
                            {S.params.was} {String(f.value)}
                          </span>
                        )}
                        {invalid[f.path] && (
                          <span id={id + "-err"} className="level-error small">
                            {invalid[f.path]}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </fieldset>
              ))}
              <div className="commit__actions">
                <button type="submit" disabled={!hasChanges || Object.keys(invalid).length > 0 || busy !== null} aria-busy={busy !== null}>
                  {S.params.draft}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setValues(Object.fromEntries(fields.map((f) => [f.path, f.value ?? ""])) as Record<string, string | number | boolean>);
                    setDraft(null);
                  }}
                  disabled={!hasChanges}
                >
                  {S.params.reset}
                </button>
                {busy !== null && (
                  <span className="muted" aria-live="polite">
                    {S.params.drafting(busy)}
                  </span>
                )}
                {!hasChanges && <span className="muted small">{S.params.noChanges}</span>}
              </div>
              {err && (
                <p className="level-error" role="alert">
                  {err}
                </p>
              )}
            </form>

            <section className="params__draft" aria-label={S.params.compareTitle}>
              {!draft && hasChanges && <p className="muted">{S.params.needDraft}</p>}
              {draft && (
                <>
                  <p className={draftFresh ? "ok" : "level-warning"} aria-live="polite">
                    {draftFresh ? S.params.draftReady : S.params.draftStale}
                  </p>
                  <h3>{S.params.draftLabel}</h3>
                  <NumbersRow n={draft.numbers} />
                  <h3>{S.params.compareTitle}</h3>
                  <DeltaRow d={draft.diff} />
                  {draft.diff.findings.added.length > 0 && (
                    <div className="findings-lines">
                      <h4 className="level-warning">{S.feed.findingsAdded}</h4>
                      <ul>
                        {draft.diff.findings.added.map((l) => (
                          <li key={l}>{l}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {draft.diff.findings.removed.length > 0 && (
                    <div className="findings-lines">
                      <h4 className="ok">{S.feed.findingsRemoved}</h4>
                      <ul>
                        {draft.diff.findings.removed.map((l) => (
                          <li key={l}>{l}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {draft.urls.glb && (
                    <div className="overlay">
                      <div className="toolbar">
                        <span className="small">{S.feed.was}</span>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={mix}
                          aria-label={`${S.feed.was} ↔ ${S.params.draftLabel}`}
                          onChange={(e) => setMix(Number(e.target.value))}
                        />
                        <span className="small">{S.params.draftLabel}</span>
                        {(["main", "left", "top", "iso"] as ViewName[]).map((v) => (
                          <button key={v} type="button" onClick={() => setView({ name: v, nonce: view.nonce + 1 })} aria-pressed={view.name === v}>
                            {S.variant.views[v]}
                          </button>
                        ))}
                      </div>
                      <div className="canvas canvas--overlay">
                        <Viewer
                          url={draft.urls.glb}
                          selected={[]}
                          dim={false}
                          clip={{ on: false, axis: "x", pos: 0.5 }}
                          view={view}
                          overlay={draft.urls.head_glb ? { baseUrl: draft.urls.head_glb, changed: changedNodes, mix } : undefined}
                        />
                      </div>
                    </div>
                  )}
                  <div className="save">
                    <label htmlFor="msg">{S.params.message}</label>
                    <input id="msg" value={message} placeholder={S.params.messageHint} onChange={(e) => setMessage(e.target.value)} />
                    <button type="button" onClick={save} disabled={!draftFresh || !message.trim() || saving} aria-busy={saving}>
                      {saving ? S.params.saving : S.params.save}
                    </button>
                  </div>
                </>
              )}
            </section>
          </div>
        )}
      </div>
    </main>
  );
}

function defaultMessage(changes: Record<string, string | number | boolean>, fields: ParamField[]): string {
  const by = Object.fromEntries(fields.map((f) => [f.path, f.value]));
  return Object.entries(changes)
    .map(([k, v]) => `${k} ${String(by[k])} → ${String(v)}`)
    .join(", ");
}
