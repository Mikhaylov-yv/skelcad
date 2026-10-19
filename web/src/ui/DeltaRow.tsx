import type { CommitDiff, DeltaNum } from "../api";
import { S } from "../strings";
import { fmtNum } from "./format";

function num(d: DeltaNum | undefined, unit = "") {
  if (!d) return null;
  const sign = d.delta === null ? "" : d.delta > 0 ? "+" : "";
  return (
    <>
      {fmtNum(d.a ?? undefined)} → <strong>{fmtNum(d.b ?? undefined)}</strong>
      {unit && <span className="unit"> {unit}</span>}
      {d.delta !== null && (
        <span className={"delta " + (d.delta > 0 ? "up" : "down")}>
          {" "}
          ({sign}
          {fmtNum(d.delta)})
        </span>
      )}
    </>
  );
}

function levelCounts(lines: string[]) {
  const c = { error: 0, warning: 0 };
  for (const l of lines) {
    if (l.startsWith("[error]")) c.error++;
    else if (l.startsWith("[warning]")) c.warning++;
  }
  return c;
}

/** Строка дельт коммита: масса, K min, замечания — по тем же полям, что везде. */
export function DeltaRow({ d }: { d: CommitDiff }) {
  const mass = d.deltas.mass_kg as DeltaNum | undefined;
  const kmin = d.deltas.K_min as DeltaNum | undefined;
  const added = levelCounts(d.findings.added);
  const removed = levelCounts(d.findings.removed);
  const kBad = kmin && kmin.b !== null && kmin.a !== null && kmin.b < kmin.a;
  return (
    <dl className="numbers numbers--compact deltas">
      <div>
        <dt>{S.numbers.mass}</dt>
        <dd>{mass ? num(mass, S.numbers.kg) : <span className="muted">=</span>}</dd>
      </div>
      <div>
        <dt>{S.numbers.kmin}</dt>
        <dd className={kBad ? "bad" : undefined}>{kmin ? num(kmin) : <span className="muted">=</span>}</dd>
      </div>
      <div>
        <dt>{S.numbers.errors}</dt>
        <dd>
          {added.error > 0 && <span className="level-error">+{added.error}</span>}
          {removed.error > 0 && <span className="ok"> −{removed.error}</span>}
          {added.error === 0 && removed.error === 0 && <span className="muted">=</span>}
        </dd>
      </div>
      <div>
        <dt>{S.numbers.warnings}</dt>
        <dd>
          {added.warning > 0 && <span className="level-warning">+{added.warning}</span>}
          {removed.warning > 0 && <span className="ok"> −{removed.warning}</span>}
          {added.warning === 0 && removed.warning === 0 && <span className="muted">=</span>}
        </dd>
      </div>
    </dl>
  );
}
