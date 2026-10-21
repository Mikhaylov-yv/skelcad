import { api, type ProjectOverview } from "../../api";
import { S } from "../../strings";

function size(n: number): string {
  if (n < 1024) return `${n} Б`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} КБ`;
  return `${(n / 1024 / 1024).toFixed(1)} МБ`;
}

/** Комплект: файлы последней сборки с экспортом по выбранному варианту; «Выдать комплект» — сборка с экспортом. */
export function KitPane({ p, onAct, busy }: { p: ProjectOverview; onAct: (act: string) => void; busy?: string | null }) {
  const files = p.kit.files;
  const ready = files.some((f) => f.kind === "step");
  return (
    <div className="kit">
      {!files.length && (
        <p className="empty">
          {p.aggregate ? S.wb.kitAggregate : p.kit.variant ? S.wb.kitEmpty(p.kit.variant) : S.wb.kitNoVariant}
        </p>
      )}
      {files.length > 0 && (
        <>
          <div className="kit__head">
            <span>
              {S.wb.kitOf} <b className="mono">{p.kit.variant}</b>
            </span>
            {ready && (
              <a className="button" href={api.kitZipUrl(p.name)} download>
                {S.wb.kitDownloadAll}
              </a>
            )}
          </div>
          <ul className="files" aria-label={S.wb.kitFiles}>
            {files.map((f) => (
              <li key={f.name} className="file">
                <span className="file__ext">{f.kind.toUpperCase().replace("-SVG", "")}</span>
                <a className="file__n" href={f.url} download={f.kind === "step" || f.kind === "glb" || undefined} target={f.kind === "step" ? undefined : "_blank"} rel="noreferrer">
                  {f.name}
                </a>
                <span className="file__s muted small">
                  {f.title} · {size(f.size)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {!p.aggregate && p.kit.variant && (
        <div className="kit__actions">
          <button type="button" onClick={() => onAct("run:kit")} disabled={!!busy} aria-busy={busy === "run:kit"}>
            {busy === "run:kit" ? S.wb.kitBuilding : ready ? S.wb.kitRebuild : S.wb.kitBuild}
          </button>
          <span className="muted small">{S.wb.kitHint}</span>
        </div>
      )}
    </div>
  );
}
