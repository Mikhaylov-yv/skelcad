import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type CompareResponse } from "../api";
import { S } from "../strings";
import { fmtNum } from "../ui/format";
import { Viewer, type ViewName } from "../three/Viewer";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: CompareResponse };

export function Compare() {
  const { project = "" } = useParams();
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [view, setView] = useState<{ name: ViewName; nonce: number }>({ name: "iso", nonce: 0 });
  const load = useCallback(() => {
    setSt({ kind: "loading" });
    api
      .compare(project)
      .then((data) => setSt({ kind: "ok", data }))
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  }, [project]);
  useEffect(load, [load]);

  const data = st.kind === "ok" ? st.data : null;
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
                        <td key={v.id} className={"num" + (best ? " best" : "")} title={best ? S.compare.best : undefined}>
                          {typeof val === "number" ? fmtNum(val) : (val ?? "—")}
                          {best && <span className="sr-only"> ({S.compare.best})</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {data.variants.length > 1 && (
              <section aria-label={S.compare.models}>
                <div className="toolbar">
                  <span className="muted small">{S.variant.viewsLabel}:</span>
                  {(["main", "left", "top", "iso"] as ViewName[]).map((v) => (
                    <button key={v} onClick={() => setView({ name: v, nonce: view.nonce + 1 })} aria-pressed={view.name === v}>
                      {S.variant.views[v]}
                    </button>
                  ))}
                </div>
                <div className="cmp__models" style={{ gridTemplateColumns: `repeat(${Math.min(data.variants.length, 3)}, 1fr)` }}>
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
                          <Viewer url={v.glb} selected={[]} dim={false} clip={{ on: false, axis: "x", pos: 0.5 }} view={view} />
                        ) : (
                          <p className="muted">{S.compare.noGlb}</p>
                        )}
                      </div>
                    </figure>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </main>
  );
}
