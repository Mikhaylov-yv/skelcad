import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError, type Report, type ReviewItem } from "../api";
import { S } from "../strings";
import { NumbersRow } from "../ui/NumbersRow";
import { Findings } from "../ui/Findings";
import { KTable } from "../ui/KTable";
import { fmtNum, relativeTime } from "../ui/format";
import { Viewer, type ClipAxis, type ViewName } from "../three/Viewer";
import { indexNodes, nodesForRef } from "../three/refs";
import { useProjectState } from "../ui/useProjectState";
import { AgentBanner } from "../ui/AgentBanner";

type State =
  | { kind: "loading" }
  | { kind: "notbuilt"; message: string }
  | { kind: "error"; message: string }
  | { kind: "ok"; report: Report };

export function Variant() {
  const { project = "", variant = "" } = useParams();
  const pstate = useProjectState(project);
  const locked = pstate?.state === "agent";
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<string[]>(() => (params.get("part") ? [params.get("part")!] : []));
  const [activeRef, setActiveRef] = useState<string | null>(null);
  const [topLevel, setTopLevel] = useState<string[]>([]);
  const [dim, setDim] = useState(true);
  const [clip, setClip] = useState<{ on: boolean; axis: ClipAxis; pos: number }>({ on: false, axis: "x", pos: 0.5 });
  const [view, setView] = useState<{ name: ViewName; nonce: number }>({ name: "iso", nonce: 0 });
  const [building, setBuilding] = useState<number | null>(null);
  const [buildError, setBuildError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const load = useCallback(() => {
    setSt({ kind: "loading" });
    api
      .report(project, variant)
      .then((report) => setSt({ kind: "ok", report }))
      .catch((e: Error) => {
        if (e instanceof ApiError && e.status === 404) setSt({ kind: "notbuilt", message: e.message });
        else setSt({ kind: "error", message: e.message });
      });
  }, [project, variant]);
  useEffect(load, [load]);

  const build = () => {
    setBuildError(null);
    setBuilding(0);
    const t0 = Date.now();
    timer.current = window.setInterval(() => setBuilding(Math.round((Date.now() - t0) / 1000)), 1000);
    api
      .build(project, variant)
      .then(() => load())
      .catch((e: Error) => setBuildError(e.message))
      .finally(() => {
        if (timer.current) window.clearInterval(timer.current);
        setBuilding(null);
      });
  };

  // выделение ↔ адрес (?part=)
  useEffect(() => {
    const p = new URLSearchParams(params);
    if (selected.length === 1) p.set("part", selected[0]);
    else p.delete("part");
    if (p.toString() !== params.toString()) setParams(p, { replace: true });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  const report = st.kind === "ok" ? st.report : null;
  const idx = useMemo(() => (report ? indexNodes(report, topLevel) : null), [report, topLevel]);

  const pickRef = (ref: string) => {
    if (!report || !idx) return;
    setActiveRef(ref);
    setSelected(nodesForRef(ref, report, idx));
  };
  const toggleNode = (id: string) => {
    setActiveRef(null);
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [id]));
  };
  const onNodes = useCallback((names: string[]) => setTopLevel(names), []);
  const [glbError, setGlbError] = useState<string | null>(null);

  // замечания агенту: пометки на модели
  const [review, setReview] = useState<ReviewItem[]>([]);
  const [pinMode, setPinMode] = useState(false);
  const [pinAt, setPinAt] = useState<{ part: string | null; point: [number, number, number] } | null>(null);
  const [pinText, setPinText] = useState("");
  const [pinBusy, setPinBusy] = useState(false);
  const [pinErr, setPinErr] = useState<string | null>(null);
  const loadReview = useCallback(() => {
    api
      .review(project)
      .then((r) => setReview(Array.isArray(r.items) ? r.items : []))
      .catch(() => setReview([]));
  }, [project]);
  useEffect(loadReview, [loadReview]);

  const onPick = useCallback(
    (node: string | null, point?: [number, number, number]) => {
      if (pinMode && point) {
        setPinAt({ part: node, point });
        setPinMode(false);
        setSelected(node ? [node] : []);
        return;
      }
      setActiveRef(null);
      setSelected(node ? [node] : []);
    },
    [pinMode],
  );
  const sendPin = () => {
    if (!pinText.trim()) {
      setPinErr(S.review.needText);
      return;
    }
    setPinBusy(true);
    setPinErr(null);
    api
      .reviewAdd(project, { text: pinText, variant, part: pinAt?.part ?? null, point: pinAt?.point ?? null })
      .then(() => {
        setPinText("");
        setPinAt(null);
        loadReview();
      })
      .catch((e: Error) => setPinErr(e.message))
      .finally(() => setPinBusy(false));
  };
  const closeItem = (id: string) => {
    const answer = window.prompt(S.review.closeAnswer) ?? "";
    api
      .reviewResolve(project, id, answer)
      .then(loadReview)
      .catch((e: Error) => setPinErr(e.message));
  };
  const pins = useMemo(
    () =>
      [
        ...review.filter((r) => r.point && (!r.variant || r.variant === variant)).map((r) => ({ id: r.id, point: r.point!, resolved: r.status === "resolved" })),
        ...(pinAt ? [{ id: "_new", point: pinAt.point }] : []),
      ],
    [review, variant, pinAt],
  );

  const title = report ? `${report.project_title || project} · ${report.title || variant}` : `${project} · ${variant}`;

  return (
    <main className="variant">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span> <strong className="mono">{variant}</strong>
        </nav>
        <h1>{title}</h1>
        {report && (
          <div className="variant__numbers">
            <NumbersRow
              n={{
                mass_kg: report.summary.mass_kg,
                k_min: report.summary.K_min,
                k_min_item: report.summary.K_min_item,
                errors: report.summary.findings.error,
                warnings: report.summary.findings.warning,
              }}
            />
            <span className="muted small">
              {S.variant.builtAt} {relativeTime(report.built_at)}
            </span>
            {report.urls.step && !(report.summary.findings.error ?? 0) && (
              <a className="small" href={report.urls.step} download>
                {S.variant.download}
              </a>
            )}
            {(report.summary.findings.error ?? 0) > 0 && (
              <span className="level-error small" role="status">
                {S.gate.closed(report.summary.findings.error ?? 0)}
              </span>
            )}
            <Link className="small" to={`/p/${encodeURIComponent(project)}/commits?variant=${encodeURIComponent(variant)}`}>
              {S.feed.tab}
            </Link>
            <Link className="small" to={`/p/${encodeURIComponent(project)}/compare`}>
              {S.compare.tab}
            </Link>
            <Link className="small" to={`/p/${encodeURIComponent(project)}/${encodeURIComponent(variant)}/params`}>
              {S.params.tab}
            </Link>
            <Link className="small" to={`/p/${encodeURIComponent(project)}/agent?variant=${encodeURIComponent(variant)}`}>
              {S.agent.tab}
            </Link>
          </div>
        )}
        <div className="variant__actions">
          <button onClick={build} disabled={building !== null} aria-busy={building !== null}>
            {report ? S.variant.rebuild : S.variant.build}
          </button>
          {building !== null && (
            <span className="muted" aria-live="polite">
              {S.variant.building(building)}
            </span>
          )}
          {buildError && (
            <span className="level-error" role="alert">
              {S.variant.buildFailed}: {buildError}
            </span>
          )}
        </div>
      </header>

      <AgentBanner p={pstate} />
      {st.kind === "loading" && <p className="muted page">{S.variant.loading}</p>}
      {st.kind === "error" && (
        <div className="callout callout--error page" role="alert">
          <p>
            {S.errors.load}: {st.message}
          </p>
          <button onClick={load}>{S.errors.retry}</button>
        </div>
      )}
      {st.kind === "notbuilt" && (
        <div className="empty page">
          <p>{S.variant.notBuilt}</p>
          <p className="small">{S.variant.notBuiltHint}</p>
        </div>
      )}

      {report && idx && (
        <div className="variant__body">
          <aside className="pane pane--tree" aria-label={S.variant.tree}>
            <h3>{S.variant.parts}</h3>
            <ul className="tree">
              {report.parts.map((p) => (
                <li key={p.id}>
                  <button
                    className={"tree__item" + (selected.includes(p.id) ? " selected" : "")}
                    onClick={() => toggleNode(p.id)}
                    aria-pressed={selected.includes(p.id)}
                  >
                    <span>{p.name || p.id}</span>
                    <span className="muted small">{p.mass_kg !== undefined ? `${fmtNum(p.mass_kg)} кг` : ""}</span>
                  </button>
                </li>
              ))}
            </ul>
            {report.welds.length > 0 && (
              <>
                <h3>{S.variant.welds}</h3>
                <ul className="tree">
                  {report.welds.map((w) => (
                    <li key={w.id}>
                      <button className="tree__item" onClick={() => pickRef("weld:" + w.id)} title={w.note}>
                        <span className="mono">{w.id}</span>
                        <span className="muted small">
                          {w.leg !== undefined ? `к${fmtNum(w.leg)} · ` : ""}
                          {w.length !== undefined ? `${fmtNum(w.length)} мм` : ""}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {idx.fasteners.length > 0 && (
              <>
                <h3>{S.variant.fasteners}</h3>
                <ul className="tree">
                  {idx.fasteners.map((id) => (
                    <li key={id}>
                      <button
                        className={"tree__item" + (selected.includes(id) ? " selected" : "")}
                        onClick={() => toggleNode(id)}
                        aria-pressed={selected.includes(id)}
                      >
                        <span className="mono">{id}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {idx.other.length > 0 && (
              <>
                <h3>{S.variant.other}</h3>
                <ul className="tree">
                  {idx.other.map((id) => (
                    <li key={id}>
                      <button
                        className={"tree__item" + (selected.includes(id) ? " selected" : "")}
                        onClick={() => toggleNode(id)}
                        aria-pressed={selected.includes(id)}
                      >
                        <span className="mono">{id}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </aside>

          <section className="pane pane--3d" aria-label="3D">
            <div className="toolbar">
              <span className="muted small">{S.variant.viewsLabel}:</span>
              {(["main", "left", "top", "iso"] as ViewName[]).map((v) => (
                <button key={v} onClick={() => setView({ name: v, nonce: view.nonce + 1 })} aria-pressed={view.name === v}>
                  {S.variant.views[v]}
                </button>
              ))}
              <button onClick={() => setView((v) => ({ ...v, nonce: v.nonce + 1 }))}>{S.variant.fit}</button>
              <label className="small">
                <input type="checkbox" checked={dim} onChange={(e) => setDim(e.target.checked)} /> {S.variant.dim}
              </label>
              <label className="small">
                <input type="checkbox" checked={clip.on} onChange={(e) => setClip({ ...clip, on: e.target.checked })} />{" "}
                {S.variant.clip}
              </label>
              {clip.on && (
                <>
                  <select
                    aria-label={S.variant.clipAxis}
                    value={clip.axis}
                    onChange={(e) => setClip({ ...clip, axis: e.target.value as ClipAxis })}
                  >
                    <option value="x">X</option>
                    <option value="y">Y</option>
                    <option value="z">Z</option>
                  </select>
                  <input
                    type="range"
                    aria-label={S.variant.clipPos}
                    min={0}
                    max={1}
                    step={0.01}
                    value={clip.pos}
                    onChange={(e) => setClip({ ...clip, pos: Number(e.target.value) })}
                  />
                </>
              )}
              {selected.length > 0 && (
                <button className="link" onClick={() => onPick(null)}>
                  {S.variant.clear} ({selected.length})
                </button>
              )}
            </div>
            <div className={"canvas" + (pinMode ? " canvas--pinning" : "")}>
              {report.urls.glb ? (
                <>
                  {topLevel.length === 0 && !glbError && <p className="canvas__note muted">{S.variant.glbLoading}</p>}
                  {glbError && (
                    <p className="canvas__note level-error" role="alert">
                      {glbError}
                    </p>
                  )}
                  <Viewer
                    url={report.urls.glb}
                    selected={selected}
                    dim={dim}
                    clip={clip}
                    view={view}
                    pins={pins}
                    onNodes={onNodes}
                    onPick={onPick}
                    onError={setGlbError}
                  />
                </>
              ) : (
                <p className="muted">{S.variant.glbMissing}</p>
              )}
            </div>
          </section>

          <aside className="pane pane--info">
            <h3>{S.review.title}</h3>
            <section className="review" aria-label={S.review.title}>
              <div className="commit__actions">
                {!pinMode && !pinAt && (
                  <button onClick={() => setPinMode(true)} aria-pressed={pinMode} disabled={locked}>
                    {S.review.pin}
                  </button>
                )}
                {pinMode && (
                  <>
                    <span className="muted small" aria-live="polite">
                      {S.review.pinning}
                    </span>
                    <button className="link" onClick={() => setPinMode(false)}>
                      {S.review.cancelPin}
                    </button>
                  </>
                )}
              </div>
              {pinAt && (
                <form
                  className="review__form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    sendPin();
                  }}
                >
                  <p className="small muted">
                    {S.review.at(pinAt.part ?? "—")} · {S.review.atPoint(pinAt.point)}
                  </p>
                  <textarea
                    aria-label={S.review.textLabel}
                    value={pinText}
                    placeholder={S.review.placeholder}
                    rows={3}
                    onChange={(e) => setPinText(e.target.value)}
                  />
                  <div className="commit__actions">
                    <button type="submit" disabled={pinBusy} aria-busy={pinBusy}>
                      {pinBusy ? S.review.sending : S.review.send}
                    </button>
                    <button type="button" className="link" onClick={() => setPinAt(null)}>
                      {S.review.cancelPin}
                    </button>
                  </div>
                </form>
              )}
              {pinErr && (
                <p className="level-error small" role="alert">
                  {pinErr}
                </p>
              )}
              {review.length === 0 && !pinAt && <p className="muted small">{S.review.empty}</p>}
              {review.length > 0 && (
                <ul className="review__list">
                  {review.map((r) => (
                    <li key={r.id} className={"review__item review__item--" + r.status}>
                      <button
                        className="ref"
                        onClick={() => {
                          setActiveRef(null);
                          if (r.part) setSelected([r.part]);
                        }}
                        title={r.point ? S.review.atPoint(r.point) : undefined}
                      >
                        {r.id}
                      </button>{" "}
                      <span>{r.text}</span>
                      {r.part && <span className="muted small"> · {r.part}</span>}
                      {r.answer && (
                        <div className="small ok">
                          {S.review.answer}: {r.answer}
                        </div>
                      )}
                      {r.status === "open" && (
                        <button className="link small" onClick={() => closeItem(r.id)}>
                          {S.review.close}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <h3>{S.variant.findings}</h3>
            <Findings items={report.findings} onRef={pickRef} activeRef={activeRef} />
            <h3>{S.variant.calc}</h3>
            <KTable calc={report.calc} onRef={pickRef} activeRef={activeRef} />
            {report.derived && Object.keys(report.derived).length > 0 && (
              <details>
                <summary>{S.variant.derived}</summary>
                <dl className="kv">
                  {Object.entries(report.derived).map(([k, v]) => (
                    <div key={k}>
                      <dt>{k}</dt>
                      <dd>{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
            {report.assumptions.length > 0 && (
              <details>
                <summary>
                  {S.variant.assumptions} · {report.assumptions.length}
                </summary>
                <ul className="assumptions">
                  {report.assumptions.map((a) => (
                    <li key={a.id}>
                      <span className="mono muted">{a.id}</span> {a.text}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}
