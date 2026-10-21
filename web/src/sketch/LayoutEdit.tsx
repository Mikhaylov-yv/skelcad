// Панель правки компоновки (M2.3 шаг 2): точные значения полей выбранной сущности, размер числом,
// «Применить» — коммит от имени конструктора через POST /layout/edit.
import { useState } from "react";
import { api, type LayoutDim, type LayoutEntity } from "../api";
import { S } from "../strings";
import { changedFields, fieldsOf, fieldValue, geomKind, withField, type Geom, type Vec3 } from "./edit";

export interface LayoutEditPanelProps {
  project: string;
  variant?: string;
  entity: LayoutEntity | null;
  base: Geom | null; // геометрия из layout.json
  draft: Geom | null; // черновик после ручек или полей
  onDraft: (g: Geom | null) => void;
  dim: LayoutDim | null; // выбранный размер (клик по размеру на эскизе)
  onDimDone: () => void;
  onApplied: (summary: string) => void;
  onSelectRef?: (ref: string) => void;
  locked: boolean;
}

const num = (x: number) => (Math.abs(x - Math.round(x)) < 1e-9 ? String(Math.round(x)) : x.toFixed(2));

export function LayoutEditPanel({
  project,
  variant,
  entity,
  base,
  draft,
  onDraft,
  dim,
  onDimDone,
  onApplied,
  onSelectRef,
  locked,
}: LayoutEditPanelProps) {
  const geom = draft ?? base;
  let note: string | null = null;
  const fields = entity && geom ? fieldsOf(entity, geom) : [];
  if (locked) note = S.layout.editLocked;
  else if (!entity && !dim) note = S.layout.editNoSelection;
  else if (entity && geomKind(entity) === "interface" && !(geom as Geom | null)?.body) {
    note = S.layout.editViaDatum(`datum:${(geom as Geom | null)?.datum ?? "?"}`);
  } else if (entity && fields.length === 0) note = S.layout.editNoGeom;

  return (
    <section className="edit" aria-label={S.layout.editTitle}>
      <strong className="small">{S.layout.editTitle}</strong>
      <p className="muted small" style={{ margin: 0 }}>
        {S.layout.editHint}
      </p>
      {dim && (
        <DimForm
          key={dim.id}
          project={project}
          variant={variant}
          dim={dim}
          locked={locked}
          onDone={onDimDone}
          onApplied={onApplied}
        />
      )}
      {note && !dim && (
        <p className="muted small" style={{ margin: 0 }}>
          {note}
          {entity && geomKind(entity) === "interface" && (geom as Geom | null)?.datum && onSelectRef ? (
            <>
              {" "}
              <button type="button" className="link small" onClick={() => onSelectRef(`datum:${(geom as Geom).datum}`)}>
                datum:{(geom as Geom).datum}
              </button>
            </>
          ) : null}
        </p>
      )}
      {entity && geom && fields.length > 0 && !dim && !locked && (
        <EntityForm
          key={entity.ref}
          project={project}
          variant={variant}
          entity={entity}
          base={base ?? geom}
          draft={draft}
          onDraft={onDraft}
          onApplied={onApplied}
        />
      )}
    </section>
  );
}

/** Размер числом: вторая сущность размера сдвигается по его оси (коммит). */
function DimForm({
  project,
  variant,
  dim,
  locked,
  onDone,
  onApplied,
}: {
  project: string;
  variant?: string;
  dim: LayoutDim;
  locked: boolean;
  onDone: () => void;
  onApplied: (summary: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [dimValue, setDimValue] = useState(dim.value != null ? num(dim.value) : "");
  const applyDim = () => {
    const v = Number(dimValue.replace(",", "."));
    if (!Number.isFinite(v) || v <= 0) {
      setErr(S.layout.dimNew + ": " + S.layout.needNumber);
      return;
    }
    setBusy(true);
    setErr(null);
    api
      .layoutEdit(project, { dim: dim.id, value: v, message: msg.trim() || undefined, variant })
      .then((r) => {
        setMsg("");
        onDone();
        onApplied(r.summary);
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  return (
    <form
      className="edit__fields"
      onSubmit={(e) => {
        e.preventDefault();
        applyDim();
      }}
    >
      <strong className="small">{S.layout.dimTitle(dim.id)}</strong>
      <span className="muted small">{S.layout.dimHint(dim.refs[0] ?? "?", dim.refs[1] ?? "?", dim.axis)}</span>
      <div className="edit__field">
        <label htmlFor="dim-value">{S.layout.dimNew}</label>
        <input
          id="dim-value"
          type="text"
          inputMode="decimal"
          value={dimValue}
          onChange={(e) => setDimValue(e.target.value)}
          disabled={locked || busy}
        />
      </div>
      <input
        className="edit__msg"
        type="text"
        aria-label={S.layout.message}
        placeholder={S.layout.messagePlaceholder}
        value={msg}
        onChange={(e) => setMsg(e.target.value)}
        disabled={locked || busy}
      />
      <div className="commit__actions">
        <button type="submit" disabled={locked || busy} aria-busy={busy}>
          {busy ? S.layout.applying : S.layout.apply}
        </button>
        <button type="button" className="link" onClick={onDone} disabled={busy}>
          {S.feed.cancel}
        </button>
      </div>
      {err && (
        <p className="level-error small" role="alert">
          {err}
        </p>
      )}
    </form>
  );
}

/** Поля выбранной сущности: черновик правится ручками и числами, «Применить» — коммит. */
function EntityForm({
  project,
  variant,
  entity,
  base,
  draft,
  onDraft,
  onApplied,
}: {
  project: string;
  variant?: string;
  entity: LayoutEntity;
  base: Geom;
  draft: Geom | null;
  onDraft: (g: Geom | null) => void;
  onApplied: (summary: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const geom = draft ?? base;
  const locked = false;
  const fields = fieldsOf(entity, geom);
  const changes = draft ? changedFields(entity, base, draft) : {};
  const nChanged = Object.keys(changes).length;
  const setField = (path: string, value: number | Vec3) => onDraft(withField(geom, path, value));
  const apply = () => {
    if (nChanged === 0) return;
    setBusy(true);
    setErr(null);
    api
      .layoutEdit(project, { edits: [{ ref: entity.ref, set: changes }], message: msg.trim() || undefined, variant })
      .then((r) => {
        setMsg("");
        setDone(S.layout.applied(r.applied.length));
        onDraft(null);
        onApplied(r.summary);
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(false));
  };
  return (
    <>
      {
        <form
          className="edit__fields"
          onSubmit={(e) => {
            e.preventDefault();
            apply();
          }}
        >
          <span className="small">
            <span className="mono">{entity.ref}</span>
            {entity.name && entity.name !== entity.id ? <span className="muted"> — {entity.name}</span> : null}
          </span>
          {fields.map((f) => {
            const v = fieldValue(geom!, f.path) ?? f.value;
            const changed = f.path in changes;
            return (
              <div className="edit__field" key={f.path}>
                <label className={changed ? "level-warning" : undefined}>{f.label}</label>
                {Array.isArray(v) ? (
                  <span className="edit__vec">
                    {(v as Vec3).map((c, i) => (
                      <input
                        key={i}
                        type="number"
                        step={1}
                        aria-label={`${f.label} ${"xyz"[i]}`}
                        value={num(c)}
                        onChange={(e) => {
                          const n = Number(e.target.value);
                          if (!Number.isFinite(n)) return;
                          const nv = [...(v as Vec3)] as Vec3;
                          nv[i] = n;
                          setField(f.path, nv);
                        }}
                        disabled={locked || busy}
                      />
                    ))}
                  </span>
                ) : (
                  <input
                    type="number"
                    step={1}
                    aria-label={f.label}
                    value={num(v as number)}
                    onChange={(e) => {
                      const n = Number(e.target.value);
                      if (Number.isFinite(n)) setField(f.path, n);
                    }}
                    disabled={locked || busy}
                  />
                )}
              </div>
            );
          })}
          <input
            className="edit__msg"
            type="text"
            aria-label={S.layout.message}
            placeholder={S.layout.messagePlaceholder}
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            disabled={locked || busy}
          />
          <div className="commit__actions">
            <button type="submit" disabled={locked || busy || nChanged === 0} aria-busy={busy}>
              {busy ? S.layout.applying : S.layout.apply}
            </button>
            {nChanged > 0 && (
              <>
                <span className="muted small">{S.layout.changed(nChanged)}</span>
                <button type="button" className="link" onClick={() => onDraft(null)} disabled={busy}>
                  {S.layout.discard}
                </button>
              </>
            )}
            {nChanged === 0 && done && <span className="ok small">{done}</span>}
          </div>
        </form>
      }
      {err && (
        <p className="level-error small" role="alert">
          {err}
        </p>
      )}
    </>
  );
}
