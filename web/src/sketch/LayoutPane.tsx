// Режим «Компоновка» экрана «Вариант»: эскиз по скелету и обстановке (без сборки), состав компоновки,
// состояние согласования и кнопка «Компоновка согласована».
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type LayoutDim, type LayoutEntity, type LayoutResponse } from "../api";
import { S } from "../strings";
import { relativeTime } from "../ui/format";
import { applyDrag, bbox3, handlesFor, viewBox, type Geom } from "./edit";
import { Sketch, type SketchPin, type SketchStroke } from "./Sketch";

const VIEWS = ["main", "left", "top"] as const;
type ViewName = (typeof VIEWS)[number];

export interface LayoutPaneProps {
  project: string;
  variant?: string;
  selected: string[];
  pins?: SketchPin[];
  pinMode?: boolean;
  reloadNonce?: number;
  onPick?: (ref: string | null, point?: [number, number, number]) => void;
  onData?: (layout: LayoutResponse | null) => void;
  // правка компоновки (M2.3 шаг 2): режим «Править», черновик геометрии выбранной сущности, клик по размеру
  editing?: boolean;
  editable?: boolean;
  onToggleEdit?: () => void;
  draft?: Geom | null;
  onDraft?: (g: Geom | null) => void;
  onDimPick?: (dim: LayoutDim) => void;
  // росчерки пометок (M2.3 шаг 3): готовые по видам и рисование нового
  strokes?: (SketchStroke & { view: string })[];
  drawMode?: boolean;
  onStroke?: (view: string, points: [number, number, number][]) => void;
}

export function LayoutPane({
  project,
  variant,
  selected,
  pins,
  pinMode,
  reloadNonce,
  onPick,
  onData,
  editing,
  editable,
  onToggleEdit,
  draft,
  onDraft,
  onDimPick,
  strokes,
  drawMode,
  onStroke,
}: LayoutPaneProps) {
  const [data, setData] = useState<LayoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewName>("main");
  const [fit, setFit] = useState(0);
  const [hover, setHover] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api
      .layout(project, variant || undefined)
      .then((d) => {
        setData(d);
        onData?.(d);
      })
      .catch((e: Error) => {
        setError(e.message);
        onData?.(null);
      });
  }, [project, variant, onData]);
  useEffect(load, [load, reloadNonce]);

  const v = data?.views[view];
  const hoverName = hover ? (data?.entities.find((e) => e.ref === hover)?.name ?? hover) : null;
  const dims = data?.dims.filter((d) => d.view === view) ?? [];

  // ручки и контур черновика у выбранной сущности (только в режиме «Править»)
  const entity = editing && selected.length === 1 ? (data?.entities.find((e) => e.ref === selected[0]) ?? null) : null;
  const base = (entity?.geom as Geom | undefined) ?? null;
  const geom = draft ?? base;
  const sceneHalf = v ? Math.max(v.viewBox[2], v.viewBox[3]) / 2 : 500;
  const handles = useMemo(
    () => (entity && geom && v ? handlesFor(entity, geom, v, sceneHalf) : []),
    [entity, geom, v, sceneHalf],
  );
  const ghost = useMemo(() => {
    if (!entity || !draft || !v) return null;
    const bb = bbox3(entity, draft, sceneHalf);
    return bb ? viewBox(v, bb[0], bb[1]) : null;
  }, [entity, draft, v, sceneHalf]);
  const onHandleDrag = useCallback(
    (id: string, du: number, dv: number) => {
      if (!entity || !base || !v) return;
      onDraft?.(applyDrag(entity, base, v, id, du, dv));
    },
    [entity, base, v, onDraft],
  );
  const viewStrokes = useMemo(() => (strokes ?? []).filter((s) => s.view === view), [strokes, view]);
  const onStrokeDone = useCallback((points: [number, number, number][]) => onStroke?.(view, points), [onStroke, view]);
  const pick = useCallback(
    (ref: string | null, point?: [number, number, number]) => {
      if (editing && ref?.startsWith("dim:") && onDimPick) {
        const d = data?.dims.find((x) => "dim:" + x.id === ref);
        if (d) {
          onDimPick(d);
          return;
        }
      }
      onPick?.(ref, point);
    },
    [editing, onDimPick, data, onPick],
  );
  return (
    <>
      <div className="toolbar">
        <span className="muted small">{S.variant.viewsLabel}:</span>
        {VIEWS.map((name) => (
          <button key={name} onClick={() => setView(name)} aria-pressed={view === name}>
            {S.variant.views[name]}
          </button>
        ))}
        <button onClick={() => setFit((n) => n + 1)}>{S.layout.fit}</button>
        {onToggleEdit && (
          <button onClick={onToggleEdit} aria-pressed={!!editing} disabled={!editable} title={S.layout.editHint}>
            {S.layout.edit}
          </button>
        )}
        <span className="muted small">{editing ? S.layout.editHint : S.layout.zoomHint}</span>
        {hoverName && (
          <span className="small sketch__hover" aria-live="polite">
            {hoverName}
          </span>
        )}
      </div>
      <div className={"canvas canvas--sketch" + (pinMode ? " canvas--pinning" : "")}>
        {error && (
          <div className="canvas__empty">
            <p className="level-error" role="alert">
              {S.errors.load}: {error}
            </p>
            <button onClick={load}>{S.errors.retry}</button>
          </div>
        )}
        {!data && !error && <p className="canvas__note muted">{S.layout.loading}</p>}
        {data && v && (
          <Sketch
            url={v.svg_url}
            view={v}
            selected={selected}
            pins={pins}
            pinMode={pinMode}
            fitNonce={fit}
            onPick={pick}
            onHover={setHover}
            handles={editing ? handles : undefined}
            ghost={editing ? ghost : null}
            onHandleDrag={editing && entity ? onHandleDrag : undefined}
            strokes={viewStrokes}
            drawMode={drawMode}
            onStroke={drawMode ? onStrokeDone : undefined}
          />
        )}
        {pinMode && <p className="canvas__note muted">{S.layout.pinHere}</p>}
        {drawMode && <p className="canvas__note muted">{S.review.drawing}</p>}
      </div>
      {data && (
        <div className="sketch__foot small muted">
          {!data.parts && <span>{S.layout.noParts} </span>}
          {dims.length > 0 && (
            <span>
              {S.layout.dims}: {dims.map((d) => `${d.text} (${d.axis})`).join(", ")}.{" "}
            </span>
          )}
          {data.notes.map((n, i) => (
            <span key={i} className="level-warning">
              {n}{" "}
            </span>
          ))}
        </div>
      )}
    </>
  );
}

/** Состав компоновки: базы, интерфейсы, зоны, обстановка — клик выделяет сущность на эскизе. */
export function LayoutTree({
  entities,
  selected,
  onSelect,
}: {
  entities: LayoutEntity[];
  selected: string[];
  onSelect: (ref: string) => void;
}) {
  const groups = ["datum", "interface", "envelope", "surrounding"] as const;
  if (entities.length === 0) return <p className="muted small">{S.layout.empty}</p>;
  return (
    <>
      {groups.map((g) => {
        const items = entities.filter((e) => e.group === g);
        if (items.length === 0) return null;
        return (
          <section key={g}>
            <h3>{S.layout.groups[g]}</h3>
            <ul className="tree">
              {items.map((e) => (
                <li key={e.ref}>
                  <button
                    className={"tree__item" + (selected.includes(e.ref) ? " selected" : "")}
                    onClick={() => onSelect(e.ref)}
                    aria-pressed={selected.includes(e.ref)}
                    title={e.note || undefined}
                  >
                    <span>
                      <span className="mono">{e.id}</span>
                      {e.name && e.name !== e.id ? <span className="muted"> — {e.name}</span> : null}
                    </span>
                    <span className="muted small">{S.layout.kinds[e.kind] ?? e.kind}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </>
  );
}

/** Состояние согласования и кнопка «Компоновка согласована» (коммит от имени конструктора). */
export function ApprovalBox({
  project,
  layout,
  locked,
  onApproved,
}: {
  project: string;
  layout: LayoutResponse;
  locked: boolean;
  onApproved: () => void;
}) {
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const a = layout.approval;
  const approve = () => {
    setBusy(true);
    setErr(null);
    api
      .layoutApprove(project)
      .then(() => {
        setAsk(false);
        setDone(true);
        onApproved();
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  const cls = {
    none: "badge--warn",
    approved: "badge--ok",
    changed: "badge--warn",
    invalid: "badge--warn",
  }[a.state];
  return (
    <section className="approval" aria-label={S.layout.title}>
      <div className="commit__actions">
        <span className={"badge " + cls} role="status">
          {S.layout.title}: {S.layout.state[a.state]}
        </span>
        {a.approved && (
          <span className="muted small">{S.layout.approvedBy(a.approved.by, relativeTime(a.approved.at))}</span>
        )}
      </div>
      {a.state === "invalid" && (
        <p className="level-error small" role="alert">
          {S.layout.invalid} {a.error}
        </p>
      )}
      {a.state === "changed" && a.diff && (
        <p className="small">
          {S.layout.changedSince}{" "}
          {[
            ...a.diff.added.map((x) => `+ ${x}`),
            ...a.diff.removed.map((x) => `− ${x}`),
            ...a.diff.changed.map((x) => `~ ${x}`),
            ...(a.diff.requirements ? [S.layout.requirementsChanged] : []),
          ].join(", ")}
        </p>
      )}
      {a.state !== "invalid" && a.state !== "approved" && (
        <div className="commit__actions">
          <button onClick={() => setAsk(true)} disabled={locked || busy}>
            {a.state === "changed" ? S.layout.approveAgain : S.layout.approve}
          </button>
          {done && <span className="ok small">{S.layout.approveDone}</span>}
        </div>
      )}
      {err && (
        <p className="level-error small" role="alert">
          {err}
        </p>
      )}
      {ask && (
        <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="approve-title">
          <div className="dialog__box">
            <h2 id="approve-title">{S.layout.approveTitle}</h2>
            <p className="small">{S.layout.approveHint}</p>
            <div className="dialog__actions">
              <button className="link" onClick={() => setAsk(false)} disabled={busy}>
                {S.feed.cancel}
              </button>
              <button onClick={approve} disabled={busy} aria-busy={busy}>
                {busy ? S.layout.approving : S.layout.approveConfirm}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
