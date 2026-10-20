import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, type ProjectOverview, type SearchResponse } from "../api";
import { S } from "../strings";
import { NumbersRow } from "../ui/NumbersRow";
import { CommitLine } from "../ui/CommitLine";
import { relativeTime } from "../ui/format";
import { entityUrl, kindLabel } from "../ui/Links";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; projects: ProjectOverview[] };
type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "off" }
  | { kind: "error"; message: string }
  | { kind: "ok"; data: SearchResponse };

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

  // поиск по всем проектам (M2.2): запрос живёт в адресе (?q=), чтобы ссылку можно было передать
  const [params, setParams] = useSearchParams();
  const q0 = params.get("q") ?? "";
  const [q, setQ] = useState(q0);
  const [search, setSearch] = useState<SearchState>({ kind: "idle" });
  const runSearch = useCallback((text: string) => {
    setSearch({ kind: "loading" });
    api
      .graphSearch(text)
      .then((data) => setSearch({ kind: "ok", data }))
      .catch((e: Error) => {
        if (e instanceof ApiError && e.status === 503) setSearch({ kind: "off" });
        else setSearch({ kind: "error", message: e.message });
      });
  }, []);
  useEffect(() => {
    setQ(q0);
    if (q0.trim().length >= 2) runSearch(q0.trim());
    else setSearch({ kind: "idle" });
  }, [q0, runSearch]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const p = new URLSearchParams(params);
    if (q.trim()) p.set("q", q.trim());
    else p.delete("q");
    setParams(p);
  };
  const firstVariant = (project: string): string | null =>
    st.kind === "ok" ? (st.projects.find((p) => p.name === project)?.variants[0]?.id ?? null) : null;

  return (
    <main className="page">
      <h1>{S.projects.title}</h1>
      <form className="search" role="search" onSubmit={submit}>
        <label htmlFor="search-q" className="small muted">
          {S.graph.search}
        </label>
        <input
          id="search-q"
          type="search"
          value={q}
          placeholder={S.graph.searchPlaceholder}
          onChange={(e) => setQ(e.target.value)}
          title={S.graph.searchHint}
        />
        <button type="submit">{S.graph.searchButton}</button>
      </form>
      {search.kind === "loading" && (
        <p className="muted small" aria-live="polite">
          {S.graph.searching}
        </p>
      )}
      {search.kind === "off" && <p className="muted small">{S.graph.off}</p>}
      {search.kind === "error" && (
        <p className="level-error small" role="alert">
          {search.message}
        </p>
      )}
      {search.kind === "ok" && (
        <section className="search__results" aria-label={S.graph.search}>
          <p className="muted small">
            {S.graph.hits(search.data.hits.length)}
            {search.data.truncated ? ` · ${S.graph.truncated}` : ""}
          </p>
          {search.data.hits.length === 0 ? (
            <p className="empty">{S.graph.noHits(search.data.query)}</p>
          ) : (
            <ul className="search__list">
              {search.data.hits.map((h) => (
                <li key={h.project + "|" + h.variant + "|" + h.ref}>
                  <Link to={entityUrl(h.project, h.variant || firstVariant(h.project), h)}>
                    <span className="mono">{h.ref}</span>
                  </Link>
                  {h.name && <span className="muted"> — {h.name}</span>}
                  <span className="muted small">
                    {" "}
                    · {kindLabel(h.kind)} · {h.project}
                    {h.variant ? `/${h.variant}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {st.kind === "loading" && (
        <p className="muted" aria-live="polite">
          {S.projects.loading}
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
                    {v.built ? <NumbersRow n={v} compact /> : <span className="muted">{S.projects.notBuilt}</span>}
                  </td>
                  <td className="muted small">
                    {v.built_at ? `${S.numbers.builtAt} ${relativeTime(v.built_at)}` : ""}
                  </td>
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
          <Link
            to={
              p.variants.length > 0
                ? `/p/${encodeURIComponent(p.name)}/${encodeURIComponent(p.variants[0].id)}?mode=layout`
                : `/p/${encodeURIComponent(p.name)}/layout`
            }
          >
            {S.projects.layout}
          </Link>
          {p.layout && (
            <span
              className={"badge " + (p.layout.state === "approved" ? "badge--ok" : "badge--warn")}
              title={p.layout.by ? S.layout.approvedBy(p.layout.by, relativeTime(p.layout.at ?? "")) : undefined}
            >
              {S.layout.state[p.layout.state]}
            </span>
          )}
          <Link to={`/p/${encodeURIComponent(p.name)}/commits`}>{S.feed.tab}</Link>
          {p.unreviewed ? <span className="badge badge--warn">{p.unreviewed}</span> : null}
          {p.variants.length > 1 && <Link to={`/p/${encodeURIComponent(p.name)}/compare`}>{S.compare.tab}</Link>}
          <Link to={`/p/${encodeURIComponent(p.name)}/agent`}>{S.agent.tab}</Link>
        </span>
      </footer>
    </article>
  );
}
