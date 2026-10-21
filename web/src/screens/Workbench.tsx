import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type ProjectOverview, type ProjectsResponse, type StageId, type ThreadResponse } from "../api";
import { S } from "../strings";
import { fmtNum } from "../ui/format";
import { NewProjectForm } from "../ui/NewProjectForm";
import { Conversation, type ThreadLine } from "../ui/wb/Conversation";
import { BriefPane } from "../ui/wb/BriefPane";
import { KitPane } from "../ui/wb/KitPane";
import { NextCard } from "../ui/wb/NextCard";
import { KIND_DOT, ProductTree, type TreeRow } from "../ui/wb/ProductTree";
import { STAGE_IDS, Stepper } from "../ui/wb/Stepper";
import { Variant } from "./Variant";
import { Compare } from "./Compare";
import { Params } from "./Params";
import { Feed } from "./Feed";

type DesignTab = "3d" | "sketch" | "compare" | "params";
const STAGE_SET = new Set<string>(STAGE_IDS);

/** Рабочее место проекта (M2.5, D32): слева состав изделия, в шапке этапы, в центре картинка этапа,
 *  справа разговор с агентом и закреплённый следующий шаг. Старые экраны встроены как содержимое этапов. */
export function Workbench() {
  const { project = "", stage: stageParam } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [all, setAll] = useState<ProjectsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [threads, setThreads] = useState<Record<string, ThreadResponse>>({});
  const [threadBusy, setThreadBusy] = useState(false);
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actErr, setActErr] = useState<string | null>(null);
  const [newNode, setNewNode] = useState(false);
  const [toast, setToast] = useState<{ text: string; undo?: () => void } | null>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [scopeChoice, setScopeChoice] = useState<"node" | "all" | null>(null);

  const refresh = useCallback(() => {
    api
      .projects()
      .then((r) => {
        setAll(r);
        setErr(null);
      })
      .catch((e: Error) => setErr(e.message));
  }, []);
  const p = all?.projects.find((x) => x.name === project) ?? null;
  const active = !!p?.task;
  useEffect(() => {
    refresh();
    const h = window.setInterval(refresh, active ? 2500 : 6000);
    return () => window.clearInterval(h);
  }, [refresh, active, project]);
  useEffect(() => {
    setSpec(null);
    api
      .projectRead(project)
      .then((r) => setSpec(r.spec))
      .catch(() => setSpec(null));
  }, [project, p?.last_commit?.hash]);

  // дерево изделия: корень — проект без родителя; строки — обход в глубину
  const byName = useMemo(() => new Map((all?.projects ?? []).map((x) => [x.name, x])), [all]);
  const root = useMemo(() => {
    let r = p;
    const seen = new Set<string>();
    while (r?.parent && byName.has(r.parent) && !seen.has(r.parent)) {
      seen.add(r.parent);
      r = byName.get(r.parent) ?? r;
    }
    return r;
  }, [p, byName]);
  const rows = useMemo(() => {
    const out: TreeRow[] = [];
    const walk = (x: ProjectOverview, depth: number) => {
      out.push({ p: x, depth });
      for (const c of x.children) {
        const cp = byName.get(c);
        if (cp && depth < 8) walk(cp, depth + 1);
      }
    };
    if (root) walk(root, 0);
    return out;
  }, [root, byName]);
  const treeNames = useMemo(() => rows.map((r) => r.p.name), [rows]);

  // этап: из адреса, иначе — где следующий шаг
  const stage: StageId = stageParam && STAGE_SET.has(stageParam) ? (stageParam as StageId) : (p?.next.stage ?? "brief");
  const setStage = (s: StageId) => navigate(`/p/${encodeURIComponent(project)}/s/${s}${params.toString() ? "?" + params.toString() : ""}`);
  const variants = p?.variants ?? [];
  const vParam = params.get("v");
  const vsel = (vParam && variants.some((v) => v.id === vParam) ? vParam : null) ?? p?.chosen ?? variants.find((v) => v.built)?.id ?? variants[0]?.id ?? "";
  const tab = (params.get("tab") as DesignTab | null) ?? "3d";
  const setQ = (k: string, v: string | null) => {
    const q = new URLSearchParams(params);
    if (v) q.set(k, v);
    else q.delete(k);
    setParams(q, { replace: true });
  };
  const rtab = params.get("r") === "history" ? "history" : "chat";

  // разговор: по узлу или по всему изделию (по умолчанию у корня — всё изделие)
  const scope: "node" | "all" = scopeChoice ?? (p && !p.parent && p.children.length ? "all" : "node");
  const wanted = useMemo(() => (scope === "all" ? treeNames : project ? [project] : []), [scope, treeNames, project]);
  const loadThreads = useCallback(() => {
    if (!wanted.length) return;
    setThreadBusy(true);
    Promise.all(wanted.map((n) => api.thread(n).then((t) => [n, t] as const).catch(() => null)))
      .then((rs) => {
        setThreads((old) => {
          const next = { ...old };
          for (const r of rs) if (r) next[r[0]] = r[1];
          return next;
        });
      })
      .finally(() => setThreadBusy(false));
  }, [wanted]);
  useEffect(() => {
    loadThreads();
    const h = window.setInterval(loadThreads, active ? 3000 : 10000);
    return () => window.clearInterval(h);
  }, [loadThreads, active, p?.last_commit?.hash]);
  const messages: ThreadLine[] = useMemo(() => {
    const out: ThreadLine[] = [];
    for (const n of wanted) {
      const t = threads[n];
      const title = byName.get(n)?.title || n;
      if (t) out.push(...t.messages.map((m) => ({ ...m, project: n, projectTitle: title })));
    }
    out.sort((a, b) => (a.at ?? "").localeCompare(b.at ?? ""));
    return out;
  }, [wanted, threads, byName]);

  const showToast = (text: string, undo?: () => void) => {
    setToast({ text, undo });
    window.setTimeout(() => setToast((t) => (t?.text === text ? null : t)), undo ? 9000 : 4000);
  };

  // действия по следующему шагу
  const act = async (a: string) => {
    if (!p || !all) return;
    setActErr(null);
    try {
      if (a === "say") {
        composer.current?.focus();
        return;
      }
      if (a.startsWith("open:")) {
        navigate(`/p/${encodeURIComponent(a.slice(5))}`);
        return;
      }
      if (a === "choose") {
        setStage("design");
        return;
      }
      if (a === "download") {
        window.location.href = api.kitZipUrl(p.name);
        return;
      }
      setBusy(a);
      if (a === "stop" && p.task) await api.taskStop(p.task.id);
      else if (a === "approve") await api.layoutApprove(p.name);
      else if (a === "run:kit") {
        await api.kitBuild(p.name);
        setStage("kit");
      } else if (a.startsWith("run:")) {
        const text = all.task_texts[a.slice(4)];
        if (text) await api.taskCreate(p.name, text);
      }
      refresh();
      loadThreads();
    } catch (e) {
      setActErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const send = async (text: string, attachments: string[], provider?: string, model?: string) => {
    if (!p) return;
    await api.taskCreate(p.name, text, undefined, attachments, provider, model);
    refresh();
    loadThreads();
  };
  const choose = (vid: string) => {
    if (!p) return;
    setBusy("choose:" + vid);
    api
      .choose(p.name, vid)
      .then(() => {
        setQ("v", vid);
        refresh();
        loadThreads();
      })
      .catch((e: Error) => setActErr(e.message))
      .finally(() => setBusy(null));
  };
  const remove = () => {
    if (!p) return;
    const title = p.title || p.name;
    const back = p.parent ? `/p/${encodeURIComponent(p.parent)}` : "/";
    api
      .projectDelete(p.name)
      .then((r) => {
        navigate(back);
        showToast(S.wb.deleted(title), () =>
          api
            .trashRestore(r.id)
            .then(() => navigate(`/p/${encodeURIComponent(r.name)}`))
            .catch((e: Error) => setActErr(e.message)),
        );
      })
      .catch((e: Error) => setActErr(e.message));
  };

  const header = document.getElementById("topbar-center");
  if (err && !all)
    return (
      <main className="page">
        <div className="callout callout--error" role="alert">
          <p>
            {S.errors.load}: {err}
          </p>
          <button onClick={refresh}>{S.errors.retry}</button>
        </div>
      </main>
    );
  if (!all || !p || !root)
    return (
      <main className="page">
        <p className="muted" aria-live="polite">
          {all ? S.wb.noProject : S.projects.loading}
        </p>
      </main>
    );

  const folderTitle = all.folders.find((f) => f.id === root.folder)?.title;
  const crumbs: { to?: string; text: string }[] = [];
  if (folderTitle) crumbs.push({ to: `/?f=${encodeURIComponent(root.folder ?? "")}`, text: folderTitle });
  if (root.name !== p.name) crumbs.push({ to: `/p/${encodeURIComponent(root.name)}`, text: root.title || root.name });
  if (p.parent && p.parent !== root.name) {
    const par = byName.get(p.parent);
    if (par) crumbs.push({ to: `/p/${encodeURIComponent(par.name)}`, text: par.title || par.name });
  }
  crumbs.push({ text: p.title || p.name });
  const locked = !!p.task;
  const stageName = (p.aggregate ? S.wb.aggStages : S.wb.stages)[stage];

  return (
    <div className="wb">
      {header &&
        createPortal(
          <>
            <nav className="crumbs" aria-label="Путь">
              {crumbs.map((c, i) => (
                <span key={i}>
                  {i > 0 && <span className="crumbs__sep">›</span>}
                  {c.to ? (
                    <a href={c.to} onClick={(e) => { e.preventDefault(); navigate(c.to!); }}>
                      {c.text}
                    </a>
                  ) : (
                    <b>{c.text}</b>
                  )}
                </span>
              ))}
            </nav>
            <Stepper p={p} stage={stage} onStage={setStage} />
          </>,
          header,
        )}
      <aside className="wb__tree">
        <ProductTree rows={rows} current={p.name} onOpen={(n) => navigate(`/p/${encodeURIComponent(n)}`)} onNewNode={() => setNewNode(true)} />
        {newNode && (
          <div className="wb__dialog">
            <NewProjectForm
              templates={all.templates}
              folders={all.folders}
              parent={p.aggregate || !p.parent ? p.name : p.parent}
              parentTitle={(p.aggregate || !p.parent ? p : byName.get(p.parent))?.title}
              onCancel={() => setNewNode(false)}
              onCreated={(n) => {
                setNewNode(false);
                refresh();
                navigate(`/p/${encodeURIComponent(n)}`);
              }}
            />
          </div>
        )}
      </aside>
      <section className="wb__center" aria-label={stageName}>
        <div className="wb__bar">
          {stage === "design" && !p.aggregate && variants.length > 0 && (
            <div className="tabs" role="tablist">
              {(["3d", "sketch", "compare", "params"] as DesignTab[]).map((t) => (
                <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "cur" : ""} onClick={() => setQ("tab", t === "3d" ? null : t)} disabled={t === "compare" && variants.length < 2}>
                  {t === "3d" ? S.wb.tabs3d : t === "sketch" ? S.wb.tabsSketch : t === "compare" ? S.wb.tabsCompare : S.wb.tabsParams}
                </button>
              ))}
            </div>
          )}
          {p.aggregate && (stage === "design" || stage === "kit") && (
            <div className="tabs" role="tablist">
              <button type="button" role="tab" aria-selected className="cur">
                {S.wb.tabsLayout}
              </button>
              <button type="button" role="tab" disabled title={S.wb.tabsAssemblyHint}>
                {S.wb.tabsAssembly}
              </button>
            </div>
          )}
          {p.aggregate && p.summary && (
            <div className="facts">
              <div>
                <span className="k">{S.wb.summary.nodes}</span>
                <span className="v">{p.summary.nodes}</span>
              </div>
              <div>
                <span className="k">{S.wb.summary.done}</span>
                <span className="v">{p.summary.done}</span>
              </div>
              <div>
                <span className="k">{S.wb.summary.mass}</span>
                <span className="v">{fmtNum(p.summary.mass_kg)}</span>
              </div>
              <div>
                <span className="k">{S.wb.summary.kmin}</span>
                <span className={"v" + (p.summary.k_min !== null && p.summary.k_min < 1.5 ? " level-error" : "")}>{p.summary.k_min === null ? "—" : fmtNum(p.summary.k_min)}</span>
              </div>
            </div>
          )}
          <span className="spacer" />
          <span className="muted small">{stageName}</span>
          <button type="button" className="quiet small" onClick={remove} disabled={locked} data-act={"delete:" + p.name}>
            {p.parent ? S.wb.deleteNode : S.wb.deleteProject}
          </button>
        </div>
        {actErr && (
          <p className="level-error small wb__err" role="alert">
            {actErr}
          </p>
        )}
        <div className="wb__stage">
          {stage === "brief" && (
            <BriefPane
              project={p.name}
              purpose={String((spec?.requirements as { purpose?: string } | undefined)?.purpose ?? "")}
              description={String(spec?.description ?? "")}
              messages={messages.filter((m) => m.project === p.name)}
              locked={locked}
            />
          )}
          {stage === "layout" && <Variant key={"layout:" + p.name} project={p.name} variant={variants[0]?.id ?? ""} embedded mode="layout" />}
          {(stage === "design" || stage === "kit") && p.aggregate && <Variant key={"agg:" + p.name} project={p.name} variant={variants[0]?.id ?? ""} embedded mode="layout" />}
          {stage === "design" && !p.aggregate && variants.length === 0 && (
            <div className="empty page">
              <p>{p.layout?.state === "approved" ? S.agent.emptyProject : S.wb.stageHint.design}</p>
            </div>
          )}
          {stage === "design" && !p.aggregate && variants.length > 0 && tab === "compare" && <Compare key={"cmp:" + p.name} project={p.name} embedded />}
          {stage === "design" && !p.aggregate && variants.length > 0 && tab === "params" && vsel && <Params key={"par:" + p.name + vsel} project={p.name} variant={vsel} embedded />}
          {stage === "design" && !p.aggregate && variants.length > 0 && (tab === "3d" || tab === "sketch") && vsel && (
            <Variant key={"v:" + p.name + vsel} project={p.name} variant={vsel} embedded mode={tab === "sketch" ? "sketch" : "3d"} />
          )}
          {stage === "kit" && !p.aggregate && <KitPane p={p} onAct={act} busy={busy} />}
        </div>
        {stage === "design" && !p.aggregate && variants.length > 1 && (
          <div className="strip" aria-label={S.wb.variantsOf}>
            {variants.map((v) => (
              <div key={v.id} className={"strip__it" + (v.id === vsel ? " cur" : "")} onClick={() => setQ("v", v.id)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setQ("v", v.id)}>
                <div className="strip__t">
                  <span className="mono">{v.id}</span> {v.title}
                </div>
                <div className="strip__f">
                  {v.built ? (
                    <>
                      <span>{fmtNum(v.mass_kg)} кг</span>
                      <span className={v.k_min !== undefined && v.k_min !== null && v.k_min < 1.5 ? "level-error" : ""}>K {v.k_min === undefined || v.k_min === null ? "—" : fmtNum(v.k_min)}</span>
                      {(v.errors ?? 0) > 0 ? <span className="level-error">{v.errors} ош.</span> : (v.warnings ?? 0) > 0 ? <span className="level-warning">{v.warnings} пред.</span> : null}
                    </>
                  ) : (
                    <span className="muted">{S.projects.notBuilt}</span>
                  )}
                  {p.chosen === v.id && <span className="ok">✓ {S.wb.chosen}</span>}
                </div>
                {p.chosen !== v.id && v.built && !(v.errors ?? 0) && (
                  <button type="button" className="small" disabled={locked || !!busy} aria-busy={busy === "choose:" + v.id} onClick={(e) => { e.stopPropagation(); choose(v.id); }} data-act={"choose:" + v.id}>
                    {S.wb.choose}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {p.aggregate && (stage === "design" || stage === "kit") && (
          <div className="strip" aria-label={S.wb.nodes}>
            {p.children.map((c) => byName.get(c)).filter((c): c is ProjectOverview => !!c).map((c) => (
              <div key={c.name} className="strip__it" onClick={() => navigate(`/p/${encodeURIComponent(c.name)}`)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && navigate(`/p/${encodeURIComponent(c.name)}`)}>
                {c.thumb ? <img className="strip__img" src={c.thumb} alt="" /> : <div className="strip__img strip__img--empty" />}
                <div className="strip__t">{c.title || c.name}</div>
                <span className={"pill pill--" + KIND_DOT[c.next.kind]}>{c.next.short}</span>
              </div>
            ))}
          </div>
        )}
      </section>
      <div className="wb__side">
        <div className="wb__sidetabs" role="tablist">
          <button type="button" role="tab" aria-selected={rtab === "chat"} className={rtab === "chat" ? "cur" : ""} onClick={() => setQ("r", null)}>
            {S.wb.conversation}
          </button>
          <button type="button" role="tab" aria-selected={rtab === "history"} className={rtab === "history" ? "cur" : ""} onClick={() => setQ("r", "history")}>
            {S.wb.history}
            {p.unreviewed ? <span className="badge badge--warn">{p.unreviewed}</span> : null}
          </button>
        </div>
        {rtab === "chat" ? (
          <Conversation
            p={p}
            messages={messages}
            loading={threadBusy}
            scope={scope}
            canScope={rows.length > 1}
            onScope={setScopeChoice}
            onAct={act}
            busy={busy}
            composer={composer}
            onSend={send}
            onChanged={() => {
              refresh();
              loadThreads();
            }}
            taskTexts={all.task_texts}
          />
        ) : (
          <div className="wb__history">
            <NextCard p={p} onAct={act} busy={busy} stack />
            <Feed key={"feed:" + p.name} project={p.name} embedded />
          </div>
        )}
      </div>
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
    </div>
  );
}
