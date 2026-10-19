import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ProjectOverview } from "../api";
import { S } from "../strings";
import { NumbersRow } from "../ui/NumbersRow";
import { CommitLine } from "../ui/CommitLine";
import { relativeTime } from "../ui/format";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; projects: ProjectOverview[] };

export function Projects() {
  const [st, setSt] = useState<State>({ kind: "loading" });
  const load = () => {
    setSt({ kind: "loading" });
    api
      .projects()
      .then((r) => setSt({ kind: "ok", projects: r.projects }))
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  };
  useEffect(load, []);

  return (
    <main className="page">
      <h1>{S.projects.title}</h1>
      {st.kind === "loading" && <p className="muted" aria-live="polite">{S.projects.loading}</p>}
      {st.kind === "error" && (
        <div className="callout callout--error" role="alert">
          <p>
            {S.errors.load}: {st.message}
          </p>
          <button onClick={load}>{S.errors.retry}</button>
        </div>
      )}
      {st.kind === "ok" && st.projects.length === 0 && <p className="empty">{S.projects.empty}</p>}
      {st.kind === "ok" && (
        <ul className="cards" aria-label={S.projects.title}>
          {st.projects.map((p) => (
            <li key={p.name} className="card">
              <ProjectCard p={p} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function ProjectCard({ p }: { p: ProjectOverview }) {
  return (
    <article aria-labelledby={`p-${p.name}`}>
      <header className="card__head">
        <h2 id={`p-${p.name}`}>
          {p.title || p.name} <span className="muted mono">{p.name}</span>
        </h2>
        <span className={"state state--" + p.state} title={S.projects.state[p.state]}>
          {S.projects.state[p.state]}
        </span>
      </header>
      {p.standards.length > 0 && (
        <p className="muted">
          {S.projects.standards}: {p.standards.join(", ")}
        </p>
      )}
      <section>
        <h3 className="muted">{S.projects.variants}</h3>
        {p.variants.length === 0 ? (
          <p className="muted">{S.projects.noVariants}</p>
        ) : (
          <table className="variants">
            <tbody>
              {p.variants.map((v) => (
                <tr key={v.id}>
                  <th scope="row">
                    <Link to={`/p/${encodeURIComponent(p.name)}/${encodeURIComponent(v.id)}`} className="mono">
                      {v.id}
                    </Link>
                    {v.title && <span className="muted"> — {v.title}</span>}
                  </th>
                  <td>
                    {v.built ? (
                      <NumbersRow n={v} compact />
                    ) : (
                      <span className="muted">{S.projects.notBuilt}</span>
                    )}
                  </td>
                  <td className="muted small">{v.built_at ? `${S.numbers.builtAt} ${relativeTime(v.built_at)}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <footer className="card__foot">
        <span className="muted">{S.projects.lastChange}: </span>
        {p.last_commit ? <CommitLine c={p.last_commit} /> : <span className="muted">{S.projects.noCommits}</span>}
        <span className="card__links">
          <Link to={`/p/${encodeURIComponent(p.name)}/commits`}>{S.feed.tab}</Link>
          {p.unreviewed ? <span className="badge badge--warn">{p.unreviewed}</span> : null}
          {p.variants.length > 1 && <Link to={`/p/${encodeURIComponent(p.name)}/compare`}>{S.compare.tab}</Link>}
          <Link to={`/p/${encodeURIComponent(p.name)}/agent`}>{S.agent.tab}</Link>
        </span>
      </footer>
    </article>
  );
}
