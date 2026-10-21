import type { ProjectOverview } from "../../api";
import { S } from "../../strings";

export const KIND_DOT: Record<string, string> = { you: "wait", agent: "todo", running: "agent", done: "done" };

export interface TreeRow {
  p: ProjectOverview;
  depth: number;
}

/** Состав изделия: корневой проект и узлы (проекты с parent); у каждого точка состояния и строка «что дальше». */
export function ProductTree({
  rows,
  current,
  onOpen,
  onNewNode,
}: {
  rows: TreeRow[];
  current: string;
  onOpen: (name: string) => void;
  onNewNode: () => void;
}) {
  return (
    <nav className="ntree" aria-label={S.wb.tree}>
      <div className="ntree__tools">
        <span className="ntree__h">{S.wb.tree}</span>
        <button type="button" className="small" onClick={onNewNode} title={S.wb.newNodeHint}>
          {S.wb.newNode}
        </button>
      </div>
      <ul className="ntree__list">
        {rows.map(({ p, depth }) => (
          <li key={p.name}>
            <button
              type="button"
              className={"nrow" + (p.name === current ? " sel" : "") + (depth === 0 ? " root" : "")}
              style={{ paddingLeft: 12 + depth * 16 }}
              onClick={() => onOpen(p.name)}
              aria-current={p.name === current ? "page" : undefined}
              title={p.next.title}
              data-node={p.name}
            >
              <i className={"dot dot--" + KIND_DOT[p.next.kind]} aria-hidden="true" />
              <span className="nrow__name">
                {p.title || p.name}
                {p.purchased && <span className="tag">{S.wb.purchased}</span>}
              </span>
              <span className="nrow__st">{p.next.short}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
