import { useState } from "react";
import type { Finding, Level } from "../api";
import { S } from "../strings";

const ORDER: Level[] = ["error", "warning", "info"];

export function Findings({
  items,
  onRef,
  activeRef,
}: {
  items: Finding[];
  onRef: (ref: string) => void;
  activeRef: string | null;
}) {
  const [showInfo, setShowInfo] = useState(false);
  if (items.length === 0) return <p className="muted">{S.variant.noFindings}</p>;
  const groups = ORDER.map((l) => [l, items.filter((f) => f.level === l)] as const).filter(([, v]) => v.length);
  return (
    <div className="findings">
      {groups.map(([level, list]) => (
        <section key={level} className={"findings__group level-" + level}>
          <h4>
            {S.variant.level[level]} · {list.length}
            {level === "info" && (
              <button className="link" onClick={() => setShowInfo((v) => !v)} aria-expanded={showInfo}>
                {showInfo ? S.variant.hide : S.variant.showAll}
              </button>
            )}
          </h4>
          {(level !== "info" || showInfo) && (
            <ul>
              {list.map((f, i) => (
                <li key={f.code + f.ref + i} className={activeRef === f.ref ? "active" : undefined}>
                  <button className="ref" onClick={() => onRef(f.ref)} title={f.ref}>
                    {f.ref}
                  </button>
                  <span className="finding__msg">{f.message}</span>
                  <span className="muted small finding__why" title="код правила · источник">
                    {f.code}
                    {f.source ? ` · ${f.source}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
