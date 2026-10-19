import type { Calc } from "../api";
import { fmtNum } from "./format";

export function KTable({
  calc,
  onRef,
  activeRef,
}: {
  calc: Calc[];
  onRef: (ref: string) => void;
  activeRef: string | null;
}) {
  return (
    <table className="ktable">
      <thead>
        <tr>
          <th scope="col">Проверка</th>
          <th scope="col">K</th>
          <th scope="col">K треб.</th>
        </tr>
      </thead>
      <tbody>
        {calc.map((c) => (
          <tr key={c.id} className={(c.ok ? "" : "bad") + (activeRef === c.ref ? " active" : "")}>
            <th scope="row">
              {c.ref ? (
                <button className="link" onClick={() => onRef(c.ref!)} title={c.formula}>
                  {c.title}
                </button>
              ) : (
                <span title={c.formula}>{c.title}</span>
              )}
            </th>
            <td className="num">{fmtNum(c.K)}</td>
            <td className="num muted">{fmtNum(c.K_req)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
