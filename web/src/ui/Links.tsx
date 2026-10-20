// Блок «Связи» (M2.2, D27): окрестность выбранной сущности по индексу связей сервера — по типам связей, с
// переходом к связанной сущности; «Где используется» — по всем проектам (материалы, позиции каталога, базы).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type GraphNode, type LinksResponse, type WhereUsedResponse } from "../api";
import { S } from "../strings";

export interface LinksProps {
  project: string;
  variant?: string;
  reference: string; // kind:id[/kind:id]
  onPick?: (node: GraphNode) => void; // переход к связанной сущности на этом экране
}

type State =
  { kind: "loading" } | { kind: "off" } | { kind: "error"; message: string } | { kind: "ok"; data: LinksResponse };

export function kindLabel(kind: string): string {
  return S.graph.kinds[kind] ?? kind;
}

export function relationLabel(kind: string): string {
  return S.graph.relations[kind] ?? kind;
}

/** Адрес сущности в рабочем месте: деталь и крепёж — в 3D варианта, сущности скелета — в компоновке. */
export function entityUrl(
  project: string,
  variant: string | null | undefined,
  node: { ref: string; kind: string; eid: string },
): string {
  const p = encodeURIComponent(project);
  const v = variant ? encodeURIComponent(variant) : null;
  if (/^(datum|interface|envelope|surrounding|load|constraint|project|standard|review|assumption)$/.test(node.kind)) {
    return v
      ? `/p/${p}/${v}?mode=layout&ref=${encodeURIComponent(node.ref)}`
      : `/p/${p}/layout?ref=${encodeURIComponent(node.ref)}`;
  }
  if (node.kind === "variant") return `/p/${p}/${encodeURIComponent(node.eid)}`;
  if (!v) return `/p/${p}/layout`;
  if (node.kind === "part" || node.kind === "fastener") return `/p/${p}/${v}?part=${encodeURIComponent(node.eid)}`;
  if (node.kind === "hole") return `/p/${p}/${v}?part=${encodeURIComponent(node.ref.split(":")[1].split("/")[0])}`;
  if (node.kind === "dim") return `/p/${p}/${v}?mode=sketch`;
  return `/p/${p}/${v}`;
}

export function Links({ project, variant, reference, onPick }: LinksProps) {
  const [st, setSt] = useState<State>({ kind: "loading" });
  const [used, setUsed] = useState<WhereUsedResponse | null>(null);
  useEffect(() => {
    let alive = true;
    setSt({ kind: "loading" });
    setUsed(null);
    api
      .graphLinks(project, reference, { variant })
      .then((data) => {
        if (!alive) return;
        // ответ не похож на окрестность (например, в тестах подменён fetch) — показываем как ошибку, не падаем
        if (Array.isArray(data?.nodes) && Array.isArray(data?.edges)) setSt({ kind: "ok", data });
        else setSt({ kind: "error", message: S.graph.badResponse });
      })
      .catch((e: Error) => {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 503) setSt({ kind: "off" });
        else setSt({ kind: "error", message: e.message });
      });
    return () => {
      alive = false;
    };
  }, [project, variant, reference]);

  if (st.kind === "loading") return <p className="muted small">{S.graph.loading}</p>;
  if (st.kind === "off") return <p className="muted small">{S.graph.off}</p>;
  if (st.kind === "error")
    return (
      <p className="level-error small" role="alert">
        {st.message}
      </p>
    );
  const { data } = st;
  const byRef = new Map(data.nodes.map((n) => [n.ref, n]));
  const root = data.root ?? {
    ref: reference,
    kind: reference.split(":")[0],
    eid: reference,
    name: "",
    variants: [],
    depth: 0,
    data: {},
  };
  const out = new Map<string, GraphNode[]>();
  const inc = new Map<string, GraphNode[]>();
  for (const e of data.edges) {
    const other = e.src === reference ? e.dst : e.dst === reference ? e.src : null;
    if (!other) continue;
    const node = byRef.get(other) ?? {
      ref: other,
      kind: other.split(":")[0],
      eid: other,
      name: "",
      variants: [],
      depth: 1,
      data: {},
    };
    const m = e.src === reference ? out : inc;
    if (!m.has(e.kind)) m.set(e.kind, []);
    if (!m.get(e.kind)!.some((n) => n.ref === node.ref)) m.get(e.kind)!.push(node);
  }
  const groups = [
    ...Array.from(out, ([k, nodes]) => ({ key: "out:" + k, title: relationLabel(k), nodes })),
    ...Array.from(inc, ([k, nodes]) => ({ key: "in:" + k, title: `${S.graph.incoming}: ${relationLabel(k)}`, nodes })),
  ];
  const canUse = /^(material|item|standard|datum|interface|surrounding|envelope|load)$/.test(root.kind);
  const whereUsed = () =>
    api
      .graphWhereUsed(project, reference)
      .then(setUsed)
      .catch((e: Error) => setSt({ kind: "error", message: e.message }));
  return (
    <section className="links" aria-label={S.graph.title}>
      <p className="links__root">
        <span className="badge badge--kind">{kindLabel(root.kind)}</span> <span className="mono">{root.ref}</span>
        {root.name && <span className="muted"> — {root.name}</span>}
      </p>
      {groups.length === 0 && <p className="muted small">{S.graph.none}</p>}
      {groups.map((g) => (
        <div key={g.key} className="links__group">
          <span className="muted small">{g.title}:</span>
          <ul className="links__list">
            {g.nodes.map((n) => (
              <li key={n.ref}>
                <button className="links__item" onClick={() => onPick?.(n)} title={n.ref}>
                  <span className="mono">{n.ref}</span>
                  {n.name && <span className="muted"> — {n.name}</span>}
                  <span className="muted small"> · {kindLabel(n.kind)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {data.truncated && <p className="muted small">{S.graph.truncated}</p>}
      {canUse && !used && (
        <button className="link small" onClick={whereUsed}>
          {S.graph.whereUsed}
        </button>
      )}
      {used && (
        <div className="links__group">
          <span className="muted small">
            {S.graph.whereUsed}: {S.graph.usedIn(used.uses.length)}
          </span>
          {used.uses.length === 0 && <p className="muted small">{S.graph.whereUsedNone}</p>}
          <ul className="links__list">
            {used.uses.slice(0, 40).map((u, i) => (
              <li key={u.project + u.variant + u.src + i}>
                <Link
                  to={entityUrl(u.project, u.variant || null, {
                    ref: u.src,
                    kind: u.src.split(":")[0],
                    eid: u.src.split(":").pop() ?? u.src,
                  })}
                >
                  <span className="mono">{u.src}</span>
                </Link>
                {u.name && <span className="muted"> — {u.name}</span>}
                <span className="muted small">
                  {" "}
                  · {relationLabel(u.kind)} · {u.project}
                  {u.variant ? `/${u.variant}` : ""}
                </span>
              </li>
            ))}
          </ul>
          {used.uses.length > 40 && <p className="muted small">{S.graph.more(used.uses.length - 40)}</p>}
        </div>
      )}
    </section>
  );
}
