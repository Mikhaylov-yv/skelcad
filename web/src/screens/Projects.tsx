import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, type ProjectOverview, type SearchResponse, type TemplateInfo } from "../api";
import { S } from "../strings";
import { CommitLine } from "../ui/CommitLine";
import { fmtNum, relativeTime } from "../ui/format";
import { entityUrl, kindLabel } from "../ui/Links";
import { NAME_RE, slug } from "../ui/translit";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; projects: ProjectOverview[]; templates: TemplateInfo[] };
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
      .then((r) => setSt({ kind: "ok", projects: r.projects, templates: r.templates }))
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

  const [creating, setCreating] = useState(false);

  return (
    <main className="page">
      <div className="projects__head">
        <h1>{S.projects.title}</h1>
        {st.kind === "ok" && !creating && (
          <button type="button" onClick={() => setCreating(true)}>
            {S.projects.newProject}
          </button>
        )}
      </div>
      {st.kind === "ok" && creating && <NewProject templates={st.templates} onCancel={() => setCreating(false)} />}
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

/** Форма «Новый проект»: название изделия, код (подставляется транслитерацией, можно поправить), основа —
 *  пустой проект или копия примера. Создаётся коммитом конструктора; дальше — экран «Агент» этого проекта. */
function NewProject({ templates, onCancel }: { templates: TemplateInfo[]; onCancel: () => void }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [name, setName] = useState<string | null>(null); // null — код ещё не правили руками
  const [template, setTemplate] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const code = name ?? slug(title);
  const valid = NAME_RE.test(code);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setErr(null);
    api
      .projectCreate({ name: code, title: title.trim() || undefined, template: template || undefined })
      .then((r) => navigate(`/p/${encodeURIComponent(r.project.name)}/agent`))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  return (
    <form className="projects__new" onSubmit={submit} aria-label={S.projects.newProject}>
      <h3>{S.projects.newProject}</h3>
      <p className="muted small" style={{ margin: 0 }}>
        {S.projects.newHint}
      </p>
      <label>
        {S.projects.newTitle}
        <input
          autoFocus
          value={title}
          placeholder={S.projects.newTitlePlaceholder}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy}
        />
      </label>
      <label>
        {S.projects.newName}
        <input
          className="mono"
          value={code}
          placeholder={S.projects.newNamePlaceholder}
          onChange={(e) => setName(e.target.value.trim())}
          aria-invalid={code !== "" && !valid}
          disabled={busy}
        />
        <span className="small">{S.projects.newNameHint}</span>
      </label>
      <label>
        {S.projects.newTemplate}
        <select value={template} onChange={(e) => setTemplate(e.target.value)} disabled={busy}>
          <option value="">{S.projects.newTemplateEmpty}</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {S.projects.newTemplateFrom(t.title || t.id, t.id)}
            </option>
          ))}
        </select>
      </label>
      {err && (
        <p className="level-error" role="alert" style={{ margin: 0 }}>
          {err}
        </p>
      )}
      <div className="commit__actions" style={{ margin: 0 }}>
        <button type="submit" disabled={!valid || busy} aria-busy={busy}>
          {busy ? S.projects.creating : S.projects.create}
        </button>
        <button type="button" className="link" onClick={onCancel} disabled={busy}>
          {S.projects.cancel}
        </button>
      </div>
    </form>
  );
}

function ProjectCard({ p }: { p: ProjectOverview }) {
  return (
    <article aria-labelledby={`p-${p.name}`}>
      <header className="card__head">
        <h2 id={`p-${p.name}`}>
          {p.title || p.name}{" "}
          <span className="muted mono small">
            {p.name}
            {p.standards.length > 0 ? ` · ${p.standards.join(", ")}` : ""}
          </span>
        </h2>
        <span className={"state state--" + p.state} title={S.projects.state[p.state]}>
          {S.projects.state[p.state]}
        </span>
      </header>
      <section>
        {p.variants.length === 0 ? (
          <p className="muted small">{S.projects.noVariants}</p>
        ) : (
          <table className="variants">
            <thead>
              <tr>
                <th scope="col">{S.projects.variants}</th>
                <th scope="col" className="num">
                  {S.numbers.mass}, {S.numbers.kg}
                </th>
                <th scope="col" className="num">
                  {S.numbers.kmin}
                </th>
                <th scope="col" className="num">
                  {S.numbers.errors}
                </th>
                <th scope="col" className="num">
                  {S.numbers.warnings}
                </th>
                <th scope="col">{S.numbers.builtAt}</th>
              </tr>
            </thead>
            <tbody>
              {p.variants.map((v) => (
                <tr key={v.id}>
                  <th scope="row">
                    <Link to={`/p/${encodeURIComponent(p.name)}/${encodeURIComponent(v.id)}`} className="mono">
                      {v.id}
                    </Link>
                    {v.title && <span className="muted">{v.title}</span>}
                  </th>
                  {v.built ? (
                    <>
                      <td className="num">{fmtNum(v.mass_kg)}</td>
                      <td
                        className={"num" + (v.k_min !== undefined && v.k_min < 1.5 ? " bad" : "")}
                        title={v.k_min_item}
                      >
                        {fmtNum(v.k_min)}
                      </td>
                      <td className={"num" + (v.errors ? " level-error" : "")}>{v.errors ?? 0}</td>
                      <td className={"num" + (v.warnings ? " level-warning" : "")}>{v.warnings ?? 0}</td>
                      <td className="muted small when">{v.built_at ? relativeTime(v.built_at) : ""}</td>
                    </>
                  ) : (
                    <td className="muted small" colSpan={5}>
                      {S.projects.notBuilt}
                    </td>
                  )}
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
          {p.layout && p.layout.state !== "approved" && (
            <span className="badge badge--warn" title={S.layout.state[p.layout.state]}>
              {S.layout.state[p.layout.state]}
            </span>
          )}
          <Link to={`/p/${encodeURIComponent(p.name)}/commits`}>{S.feed.tab}</Link>
          {p.unreviewed ? (
            <span className="badge badge--warn" title={S.feed.unreviewed(p.unreviewed)}>
              {p.unreviewed}
            </span>
          ) : null}
          {p.variants.length > 1 && <Link to={`/p/${encodeURIComponent(p.name)}/compare`}>{S.compare.tab}</Link>}
          <Link to={`/p/${encodeURIComponent(p.name)}/agent`}>{S.agent.tab}</Link>
        </span>
      </footer>
    </article>
  );
}
