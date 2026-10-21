import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError, type ProjectOverview, type ProjectsResponse, type SearchResponse } from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";
import { entityUrl, kindLabel } from "../ui/Links";
import { NewProjectForm } from "../ui/NewProjectForm";
import { KIND_DOT } from "../ui/wb/ProductTree";

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ok"; data: ProjectsResponse };
type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "off" }
  | { kind: "error"; message: string }
  | { kind: "ok"; data: SearchResponse };

/** Стартовый экран (M2.5): папки слева, проекты папки картинками, у каждого — что дальше; корзина с возвратом. */
export function Start() {
  const navigate = useNavigate();
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [params, setParams] = useSearchParams();
  const folder = params.get("f") ?? "";
  const load = useCallback(() => {
    api
      .projects()
      .then((data) => setSt({ kind: "ok", data }))
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  }, []);
  useEffect(() => {
    setSt({ kind: "loading" });
    load();
  }, [load]);
  const [creating, setCreating] = useState(false);
  const [newFolder, setNewFolder] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<{ text: string; undo?: () => void } | null>(null);
  const showToast = (text: string, undo?: () => void) => {
    setToast({ text, undo });
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), undo ? 9000 : 4000);
  };

  // поиск по всем проектам (M2.2): запрос живёт в адресе (?q=)
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
  const setParam = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p);
  };
  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    setParam("q", q.trim());
  };

  const data = st.kind === "ok" ? st.data : null;
  const byName = new Map((data?.projects ?? []).map((p) => [p.name, p]));
  const firstVariant = (project: string): string | null => byName.get(project)?.variants[0]?.id ?? null;
  const roots = (data?.projects ?? []).filter((p) => !p.parent);
  const shown = folder === "" ? roots : folder === "_loose" ? roots.filter((p) => !p.folder) : roots.filter((p) => p.folder === folder);
  const folderTitle = folder === "" ? S.start.all : folder === "_loose" ? S.start.loose : (data?.folders.find((f) => f.id === folder)?.title ?? S.start.all);

  const createFolder = (e: FormEvent) => {
    e.preventDefault();
    if (!newFolder?.trim()) return;
    api
      .folderCreate(newFolder.trim())
      .then((f) => {
        setNewFolder(null);
        setParam("f", f.id);
        load();
      })
      .catch((e: Error) => setErr(e.message));
  };
  const deleteFolder = (id: string, title: string) => {
    api
      .folderDelete(id)
      .then(() => {
        if (folder === id) setParam("f", "");
        showToast(S.start.folderDeleted(title));
        load();
      })
      .catch((e: Error) => setErr(e.message));
  };
  const remove = (p: ProjectOverview) => {
    api
      .projectDelete(p.name)
      .then((r) => {
        load();
        showToast(S.wb.deleted(p.title || p.name), () =>
          api
            .trashRestore(r.id)
            .then(() => {
              load();
              showToast(S.wb.restored(p.title || p.name));
            })
            .catch((e: Error) => setErr(e.message)),
        );
      })
      .catch((e: Error) => setErr(e.message));
  };
  const restore = (id: string, title: string) =>
    api
      .trashRestore(id)
      .then(() => {
        load();
        showToast(S.wb.restored(title));
      })
      .catch((e: Error) => setErr(e.message));

  return (
    <main className="start">
      <aside className="start__folders">
        <div className="ntree__tools">
          <span className="ntree__h">{S.start.folders}</span>
          <button type="button" className="small" onClick={() => setNewFolder("")} data-act="new-folder">
            {S.start.newFolder}
          </button>
        </div>
        {newFolder !== null && (
          <form className="start__newfolder" onSubmit={createFolder}>
            <input autoFocus value={newFolder} placeholder={S.start.folderName} onChange={(e) => setNewFolder(e.target.value)} aria-label={S.start.folderName} data-field="name" />
            <button type="submit" className="small primary" data-act="create">
              {S.start.create}
            </button>
            <button type="button" className="small link" onClick={() => setNewFolder(null)}>
              {S.start.cancel}
            </button>
          </form>
        )}
        <ul className="ntree__list">
          <li>
            <button type="button" className={"nrow nrow--plain" + (folder === "" ? " sel" : "")} onClick={() => setParam("f", "")} data-tree="folder:all">
              <span className="nrow__name">{S.start.all}</span>
              <span className="nrow__st">{roots.length}</span>
            </button>
          </li>
          {(data?.folders ?? []).map((f) => (
            <li key={f.id}>
              <button type="button" className={"nrow nrow--plain" + (folder === f.id ? " sel" : "")} onClick={() => setParam("f", f.id)} data-tree={"folder:" + f.id}>
                <span className="nrow__name">{f.title}</span>
                <span className="nrow__st">{f.projects.length}</span>
              </button>
              {folder === f.id && f.projects.length === 0 && (
                <button type="button" className="link small start__delfolder" onClick={() => deleteFolder(f.id, f.title)}>
                  {S.start.deleteFolder}
                </button>
              )}
            </li>
          ))}
          {(data?.loose.length ?? 0) > 0 && (data?.folders.length ?? 0) > 0 && (
            <li>
              <button type="button" className={"nrow nrow--plain" + (folder === "_loose" ? " sel" : "")} onClick={() => setParam("f", "_loose")} data-tree="folder:_loose">
                <span className="nrow__name muted">{S.start.loose}</span>
                <span className="nrow__st">{data?.loose.length}</span>
              </button>
            </li>
          )}
        </ul>
        {data && data.trash.length > 0 && (
          <details className="start__trash">
            <summary className="small muted">
              {S.start.trash} · {data.trash.length}
            </summary>
            <ul className="start__trashlist">
              {data.trash.map((t) => (
                <li key={t.id}>
                  <span>{t.title || t.name}</span>
                  <button type="button" className="link small" onClick={() => restore(t.id, t.title || t.name)}>
                    {S.wb.restore}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
      </aside>
      <section className="start__main">
        <div className="start__head">
          <h1>{folderTitle}</h1>
          <span className="muted">{shown.length}</span>
          <span className="spacer" />
          <form className="search search--compact" role="search" onSubmit={submitSearch}>
            <input id="search-q" type="search" value={q} placeholder={S.graph.searchPlaceholder} onChange={(e) => setQ(e.target.value)} title={S.graph.searchHint} aria-label={S.graph.search} />
            <button type="submit" className="small">{S.graph.searchButton}</button>
          </form>
          {data && !creating && (
            <button type="button" className="primary" onClick={() => setCreating(true)} data-act="new-project">
              {S.projects.newProject}
            </button>
          )}
        </div>
        {err && (
          <p className="level-error small" role="alert">
            {err}
          </p>
        )}
        {data && creating && (
          <NewProjectForm
            templates={data.templates}
            folders={data.folders}
            folder={folder && folder !== "_loose" ? folder : null}
            onCancel={() => setCreating(false)}
            onCreated={(n) => navigate(`/p/${encodeURIComponent(n)}`)}
          />
        )}
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
        {data && shown.length === 0 && !creating && <p className="empty">{roots.length ? S.start.empty : S.projects.empty}</p>}
        {data && shown.length > 0 && (
          <ul className="gallery" aria-label={S.projects.title}>
            {shown.map((p) => (
              <li key={p.name} className="gcard">
                <Link to={`/p/${encodeURIComponent(p.name)}`} className="gcard__link" data-tree={"project:" + p.name}>
                  {p.thumb ? <img className="gcard__img" src={p.thumb} alt="" loading="lazy" /> : <div className="gcard__img gcard__img--empty">{S.wb.stages[p.next.stage]}</div>}
                  <div className="gcard__t">{p.title || p.name}</div>
                </Link>
                <div className="gcard__row">
                  <span className={"pill pill--" + KIND_DOT[p.next.kind]} title={p.next.title}>
                    {p.next.short}
                  </span>
                  {p.children.length > 0 && <span className="muted small">{S.wb.nodesOf(p.children.length)}</span>}
                  <span className="spacer" />
                  {p.last_commit && (
                    <span className="muted small" title={p.last_commit.message}>
                      {relativeTime(p.last_commit.date)}
                    </span>
                  )}
                  <button type="button" className="link small" onClick={() => remove(p)} disabled={p.state === "agent"} data-act={"delete:" + p.name}>
                    {S.start.delete}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <aside className="start__side">
        <details className="how" open={!(data?.projects.length)}>
          <summary>{S.start.howTitle}</summary>
          <ol>
            {S.start.how.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ol>
        </details>
      </aside>
      {toast && (
        <div className="toast" role="status">
          <span>{toast.text}</span>
          {toast.undo && (
            <button type="button" onClick={() => { toast.undo?.(); setToast(null); }} data-act="undo">
              {S.wb.restore}
            </button>
          )}
        </div>
      )}
    </main>
  );
}
