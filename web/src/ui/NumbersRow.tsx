import { S } from "../strings";
import { fmtNum } from "./format";

export interface Numbers {
  mass_kg?: number;
  k_min?: number;
  k_min_item?: string;
  errors?: number;
  warnings?: number;
}

/** Одна и та же строка чисел на всех экранах: масса, K min, ошибки, предупреждения. */
export function NumbersRow({ n, compact = false }: { n: Numbers; compact?: boolean }) {
  const kBad = n.k_min !== undefined && n.k_min < 1.5;
  return (
    <dl className={"numbers" + (compact ? " numbers--compact" : "")}>
      <div>
        <dt>{S.numbers.mass}</dt>
        <dd>
          {fmtNum(n.mass_kg)} <span className="unit">{S.numbers.kg}</span>
        </dd>
      </div>
      <div title={n.k_min_item}>
        <dt>{S.numbers.kmin}</dt>
        <dd className={kBad ? "bad" : undefined}>{fmtNum(n.k_min)}</dd>
      </div>
      <div>
        <dt>{S.numbers.errors}</dt>
        <dd className={n.errors ? "level-error" : undefined}>{n.errors ?? 0}</dd>
      </div>
      <div>
        <dt>{S.numbers.warnings}</dt>
        <dd className={n.warnings ? "level-warning" : undefined}>{n.warnings ?? 0}</dd>
      </div>
    </dl>
  );
}
