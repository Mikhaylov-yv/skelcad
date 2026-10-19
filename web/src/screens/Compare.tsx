import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CompareResponse } from "../api";
import { S } from "../strings";
import { fmtNum } from "../ui/format";
import { Viewer, type ViewName } from "../three/Viewer";
import { Sketch } from "../sketch/Sketch";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: CompareResponse };
type Mode = "3d" | "sketch" | "overlay";
type SketchView = "main" | "left" | "top";

/** Объединение viewBox нескольких эскизов — один масштаб и одно начало координат (D19). */
export function unionViewBox(boxes: (number[] | undefined)[]): number[] | undefined {
  const bs = boxes.filter((b): b is number[] => !!b && b.length === 4);
  if (bs.length === 0) return undefined;
  const x0 = Math.min(...bs.map((b) => b[0]));
  const y0 = Math.min(...bs.map((b) => b[1]));
  const x1 = Math.max(...bs.map((b) => b[0] + b[2]));
  const y1 = Math.max(...bs.map((b) => b[1] + b[3]));
  return [x0, y0, x1 - x0, y1 - y0];
}

export function Compare() {
  const { project = "" } = useParams();
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<{ name: ViewName; nonce: number }>({ name: "iso", nonce: 0 });
  const [mode, setMode] = useState<Mode>("3d");
  const [sview, setSview] = useState<SketchView>("main");
  const [baseline, setBaseline] = useState<string | null>(null);
  const [other, setOther] = useState<string | null>(null);
  const load = useCallback(() => {
    setSt({ kind: "loading" });
    api
      .compare(project)
      .then((data) => setSt({ kind: "ok", data }))
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  }, [project]);
  useEffect(load, [load]);

  const data = st.kind === "ok" ? st.data : null;
  const ids = useMemo(() => data?.variants.map((v) => v.id) ?? [], [data]);
  const base = baseline && ids.includes(baseline) ? baseline : ids[0];
  const oth = other && ids.includes(other) && other !== base ? other : ids.find((i) => i !== base);
  const union = useMemo(
    () => unionViewBox((data?.variants ?? []).map((v) => v.sketch_views?.[sview]?.viewBox)),
    [data, sview],
  );
  const hasSketch = (data?.variants ?? []).some((v) => v.sketch?.[sview]);
  const dimRows = data?.dim_rows ?? [];
  const paramRows = data?.param_rows ?? [];
  const byId = (id: string | undefined) => data?.variants.find((v) => v.id === id);

  return (
    <main className="compare">
      <header className="variant__head">
        <nav aria-label="Путь">
          <Link to="/">{S.variant.back}</Link> <span className="muted">/</span> <span className="mono">{project}</span>{" "}
          <span className="muted">/</span> <strong>{S.compare.title}</strong>
        </nav>
        <h1>{S.compare.title}</h1>
        <div className="variant__numbers">
          <Link className="small" to={`/p/${encodeURIComponent(project)}/commits`}>
            {S.feed.tab}
          </Link>
        </div>
      </header>
      <div className="page compare__body">
        {st.kind === "loading" && (
          <p className="muted" aria-live="polite">
            {S.compare.loading}
          </p>
        )}
        {st.kind === "error" && (
          <div className="callout callout--error" role="alert">
            <p>
              {S.errors.load}: {st.message}
            </p>
            <button onClick={load}>{S.errors.retry}</button>
          </div>
        )}
        {data && data.variants.length === 0 && <p className="empty">{S.compare.none}</p>}
        {data && data.variants.length === 1 && <p className="empty">{S.compare.one}</p>}
        {data && data.variants.length > 0 && (
          <>
            <table className="cmp">
              <thead>
                <tr>
                  <th scope="col">{S.compare.metric}</th>
                  {data.variants.map((v) => (
                    <th scope="col" key={v.id}>
                      <Link to={`/p/${encodeURIComponent(project)}/${encodeURIComponent(v.id)}`} className="mono">
                        {v.id}
                      </Link>
                      {v.title && <div className="muted small cmp__title">{v.title}</div>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.metric}>
                    <th scope="row">{r.metric}</th>
                    {data.variants.map((v) => {
                      const val = r.values[v.id];
                      const best = r.best.includes(v.id);
                      return (
                        <td
                          key={v.id}
                          className={"num" + (best ? " best" : "")}
                          title={best ? S.compare.best : undefined}
                        >
                          {typeof val === "number" ? fmtNum(val) : (val ?? "—")}
                          {best && <span className="sr-only"> ({S.compare.best})</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {dimRows.length > 0 && (
                  <tr className="cmp__section">
                    <th scope="row" colSpan={data.variants.length + 1}>
                      {S.compare.dimsTitle}
                    </th>
                  </tr>
                )}
                {dimRows.map((r) => (
                  <tr key={"d-" + r.id}>
                    <th scope="row">
                      <span className="mono">{r.id}</span>
                      {r.axis && <span className="muted small"> ({r.axis})</span>}{" "}
                      <span className="muted small">· {S.compare.dimViews(r.views)}</span>
                    </th>
                    {data.variants.map((v) => (
                      <td key={v.id} className="num diff">
                        {r.values[v.id] ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
                {paramRows.length > 0 && (
                  <tr className="cmp__section">
                    <th scope="row" colSpan={data.variants.length + 1}>
                      {S.compare.paramsTitle}
                    </th>
                  </tr>
                )}
                {paramRows.map((r) => (
                  <tr key={"p-" + r.path}>
                    <th scope="row">
                      <span className="mono">{r.path}</span>
                    </th>
                    {data.variants.map((v) => (
                      <td key={v.id} className="num diff">
                        {r.values[v.id] === undefined || r.values[v.id] === null ? "—" : String(r.values[v.id])}
                      </td>
                    ))}
                  </tr>
                ))}
                {data.variants.length > 1 && dimRows.length === 0 && paramRows.length === 0 && (
                  <tr>
                    <td colSpan={data.variants.length + 1} className="muted">
                      {S.compare.noDiffs}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {data.variants.length > 1 && (
              <section aria-label={S.compare.models}>
                <div className="modebar" role="tablist" aria-label="Сравнение">
                  <button role="tab" aria-selected={mode === "3d"} onClick={() => setMode("3d")}>
                    {S.compare.mode3d}
                  </button>
                  <button role="tab" aria-selected={mode === "sketch"} onClick={() => setMode("sketch")}>
                    {S.compare.modeSketch}
                  </button>
                  <button role="tab" aria-selected={mode === "overlay"} onClick={() => setMode("overlay")}>
                    {S.compare.modeOverlay}
                  </button>
                </div>
                <div className="toolbar">
                  <span className="muted small">{S.variant.viewsLabel}:</span>
                  {mode === "3d"
                    ? (["main", "left", "top", "iso"] as ViewName[]).map((v) => (
                        <button
                          key={v}
                          onClick={() => setView({ name: v, nonce: view.nonce + 1 })}
                          aria-pressed={view.name === v}
                        >
                          {S.variant.views[v]}
                        </button>
                      ))
                    : (["main", "left", "top"] as SketchView[]).map((v) => (
                        <button key={v} onClick={() => setSview(v)} aria-pressed={sview === v}>
                          {S.variant.views[v]}
                        </button>
                      ))}
                  {mode === "sketch" && <span className="muted small">{S.compare.sameScale}</span>}
                  {mode === "overlay" && (
                    <>
                      <label className="small">
                        {S.compare.baseline}:{" "}
                        <select value={base ?? ""} onChange={(e) => setBaseline(e.target.value)}>
                          {ids.map((i) => (
                            <option key={i} value={i}>
                              {i}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="small">
                        {S.compare.other}:{" "}
                        <select value={oth ?? ""} onChange={(e) => setOther(e.target.value)}>
                          {ids
                            .filter((i) => i !== base)
                            .map((i) => (
                              <option key={i} value={i}>
                                {i}
                              </option>
                            ))}
                        </select>
                      </label>
                      <span className="muted small">{S.compare.overlayHint}</span>
                    </>
                  )}
                </div>
                {mode === "3d" && (
                  <div
                    className="cmp__models"
                    style={{ gridTemplateColumns: `repeat(${Math.min(data.variants.length, 3)}, 1fr)` }}
                  >
                    {data.variants.map((v) => (
                      <figure key={v.id} className="cmp__model">
                        <figcaption>
                          <span className="mono">{v.id}</span>
                          <span className="muted small">
                            {" "}
                            · {fmtNum(v.mass_kg)} {S.numbers.kg} · K min {fmtNum(v.k_min)}
                          </span>
                        </figcaption>
                        <div className="canvas canvas--cmp">
                          {v.glb ? (
                            <Viewer
                              url={v.glb}
                              selected={[]}
                              dim={false}
                              clip={{ on: false, axis: "x", pos: 0.5 }}
                              view={view}
                            />
                          ) : (
                            <p className="muted">{S.compare.noGlb}</p>
                          )}
                        </div>
                      </figure>
                    ))}
                  </div>
                )}
                {mode === "sketch" && (
                  <div
                    className="cmp__models"
                    style={{ gridTemplateColumns: `repeat(${Math.min(data.variants.length, 3)}, 1fr)` }}
                  >
                    {data.variants.map((v) => (
                      <figure key={v.id} className="cmp__model">
                        <figcaption>
                          <span className="mono">{v.id}</span>
                          <span className="muted small">
                            {" "}
                            · {fmtNum(v.mass_kg)} {S.numbers.kg} · K min {fmtNum(v.k_min)}
                          </span>
                        </figcaption>
                        <div className="cmp__sketch">
                          {v.sketch?.[sview] && v.sketch_views?.[sview] ? (
                            <Sketch url={v.sketch[sview]} view={v.sketch_views[sview]} selected={[]} viewBox={union} />
                          ) : (
                            <p className="muted canvas__empty">{S.compare.noSketch}</p>
                          )}
                        </div>
                      </figure>
                    ))}
                  </div>
                )}
                {mode === "overlay" && base && oth && (
                  <div className="cmp__overlay" aria-label={S.compare.modeOverlay}>
                    {!hasSketch && <p className="muted canvas__empty">{S.compare.noSketch}</p>}
                    {byId(base)?.sketch?.[sview] && byId(base)?.sketch_views?.[sview] && (
                      <Sketch
                        url={byId(base)!.sketch![sview]}
                        view={byId(base)!.sketch_views![sview]}
                        selected={[]}
                        viewBox={union}
                        className="sketch--was sketch--bare"
                      />
                    )}
                    {byId(oth)?.sketch?.[sview] && byId(oth)?.sketch_views?.[sview] && (
                      <Sketch
                        url={byId(oth)!.sketch![sview]}
                        view={byId(oth)!.sketch_views![sview]}
                        selected={[]}
                        viewBox={union}
                        className="sketch--now sketch--bare sketch--top"
                      />
                    )}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
