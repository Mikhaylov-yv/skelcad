"""Запросы к графу: окрестность сущности на N шагов (рекурсивный SQL) по типам связей и направлению,
«где используется» через проекты, поиск по всем проектам, сводка. Возвращают словари для API и агента."""

from __future__ import annotations

from skelcad.graph.db import Graph
from skelcad.graph.extract import KINDS, RELATIONS, kind_of

MAX_HOPS = 4
DIRECTIONS = ("both", "in", "out")

ENTITY_COLS = "project, variant, ref, kind, eid, name, data"


def _scopes(variant: str | None) -> list[str] | None:
    return ["", variant] if variant else None


def _node(row: dict | None, ref: str, depth: int) -> dict:
    if row is None:
        return {
            "ref": ref,
            "kind": kind_of(ref),
            "eid": ref.rsplit(":", 1)[-1],
            "name": "",
            "variants": [],
            "depth": depth,
            "data": {},
        }
    return {
        "ref": ref,
        "kind": row["kind"],
        "eid": row["eid"],
        "name": row["name"],
        "variants": [],
        "depth": depth,
        "data": row["data"] or {},
    }


def entity(g: Graph, project: str, ref: str, variant: str | None = None) -> dict | None:
    scopes = _scopes(variant)
    sql = f"SELECT {ENTITY_COLS} FROM graph_entity WHERE project = %s AND ref = %s"
    args: list = [project, ref]
    if scopes:
        sql += " AND variant = ANY(%s)"
        args.append(scopes)
    sql += " ORDER BY variant LIMIT 1"
    with g.connection() as c:
        return c.execute(sql, args).fetchone()


def links(
    g: Graph,
    project: str,
    ref: str,
    variant: str | None = None,
    hops: int = 1,
    kinds: list[str] | None = None,
    direction: str = "both",
    limit: int = 200,
) -> dict:
    """Окрестность: узлы на расстоянии до `hops` по связям выбранных типов; `direction`: out — от сущности
    (что она содержит, на что ссылается), in — к ней (кто на неё ссылается, где используется), both — всё.
    `variant` — ограничить уровень варианта одним вариантом (уровень проекта виден всегда)."""
    hops = max(1, min(int(hops), MAX_HOPS))
    limit = max(1, min(int(limit), 1000))
    if direction not in DIRECTIONS:
        raise ValueError("direction: both | in | out")
    bad = [k for k in kinds or [] if k not in RELATIONS]
    if bad:
        raise ValueError(f"неизвестные типы связей: {', '.join(bad)}; есть: {', '.join(RELATIONS)}")
    scopes = _scopes(variant)
    cond = "r.project = %(project)s"
    if scopes:
        cond += " AND r.variant = ANY(%(scopes)s)"
    if kinds:
        cond += " AND r.kind = ANY(%(kinds)s)"
    if direction == "out":
        step = f"SELECT r.dst, w.depth + 1 FROM walk w JOIN graph_relation r ON {cond} AND r.src = w.ref"
    elif direction == "in":
        step = f"SELECT r.src, w.depth + 1 FROM walk w JOIN graph_relation r ON {cond} AND r.dst = w.ref"
    else:
        step = (
            "SELECT CASE WHEN r.src = w.ref THEN r.dst ELSE r.src END, w.depth + 1 FROM walk w "
            f"JOIN graph_relation r ON {cond} AND (r.src = w.ref OR r.dst = w.ref)"
        )
    sql = (
        "WITH RECURSIVE walk(ref, depth) AS (SELECT %(ref)s::text, 0 UNION "
        f"{step} WHERE w.depth < %(hops)s) "
        "SELECT ref, min(depth) AS depth FROM walk GROUP BY ref ORDER BY depth, ref LIMIT %(limit)s"
    )
    params = {"project": project, "ref": ref, "hops": hops, "scopes": scopes, "kinds": kinds, "limit": limit + 1}
    with g.connection() as c:
        rows = c.execute(sql, params).fetchall()
        truncated = len(rows) > limit
        rows = rows[:limit]
        refs = [r["ref"] for r in rows]
        esql = f"SELECT {ENTITY_COLS} FROM graph_entity WHERE project = %s AND ref = ANY(%s)"
        eargs: list = [project, refs]
        rsql = (
            "SELECT src, dst, kind, variant, data FROM graph_relation "
            "WHERE project = %s AND src = ANY(%s) AND dst = ANY(%s)"
        )
        rargs: list = [project, refs, refs]
        if scopes:
            esql += " AND variant = ANY(%s)"
            eargs.append(scopes)
            rsql += " AND variant = ANY(%s)"
            rargs.append(scopes)
        if kinds:
            rsql += " AND kind = ANY(%s)"
            rargs.append(kinds)
        erows = c.execute(esql + " ORDER BY ref, variant", eargs).fetchall()
        edges = c.execute(rsql + " ORDER BY kind, src, dst, variant", rargs).fetchall()
    by_ref: dict[str, dict] = {}
    for e in erows:
        by_ref.setdefault(e["ref"], e)
    nodes = [_node(by_ref.get(r["ref"]), r["ref"], r["depth"]) for r in rows]
    variants_of: dict[str, list[str]] = {}
    for e in erows:
        if e["variant"]:
            variants_of.setdefault(e["ref"], []).append(e["variant"])
    for n in nodes:
        n["variants"] = variants_of.get(n["ref"], [])
    root = next((n for n in nodes if n["ref"] == ref), None)
    return {
        "project": project,
        "variant": variant,
        "ref": ref,
        "hops": hops,
        "direction": direction,
        "kinds": kinds or [],
        "root": root,
        "nodes": nodes,
        "edges": [
            {"src": e["src"], "dst": e["dst"], "kind": e["kind"], "variant": e["variant"], "data": e["data"] or {}}
            for e in edges
        ],
        "truncated": truncated,
    }


def where_used(g: Graph, ref: str, project: str | None = None, limit: int = 300) -> dict:
    """Все связи, ведущие к сущности (по всем проектам, если проект не задан): кто и как её использует."""
    limit = max(1, min(int(limit), 2000))
    sql = "SELECT project, variant, src, kind FROM graph_relation WHERE dst = %s"
    args: list = [ref]
    if project:
        sql += " AND project = %s"
        args.append(project)
    sql += " ORDER BY project, variant, kind, src LIMIT %s"
    args.append(limit + 1)
    with g.connection() as c:
        rows = c.execute(sql, args).fetchall()
        truncated = len(rows) > limit
        rows = rows[:limit]
        names: dict[tuple[str, str], str] = {}
        if rows:
            projects = sorted({r["project"] for r in rows})
            srcs = sorted({r["src"] for r in rows})
            for e in c.execute(
                "SELECT project, ref, name FROM graph_entity "
                "WHERE project = ANY(%s) AND ref = ANY(%s) ORDER BY variant",
                (projects, srcs),
            ).fetchall():
                names.setdefault((e["project"], e["ref"]), e["name"])
    uses = [
        {
            "project": r["project"],
            "variant": r["variant"],
            "src": r["src"],
            "kind": r["kind"],
            "name": names.get((r["project"], r["src"]), ""),
        }
        for r in rows
    ]
    by_project: dict[str, int] = {}
    for u in uses:
        by_project[u["project"]] = by_project.get(u["project"], 0) + 1
    return {"ref": ref, "project": project, "uses": uses, "by_project": by_project, "truncated": truncated}


def search(g: Graph, q: str, project: str | None = None, kind: str | None = None, limit: int = 50) -> dict:
    """Поиск по всем проектам: подстрока в id, имени, роли, примечании, тегах; точное совпадение id — первым."""
    q = (q or "").strip()
    if len(q) < 2:
        raise ValueError("запрос — не короче двух знаков")
    if kind and kind not in KINDS:
        raise ValueError(f"неизвестный вид «{kind}»; есть: {', '.join(KINDS)}")
    limit = max(1, min(int(limit), 500))
    sql = f"SELECT {ENTITY_COLS} FROM graph_entity WHERE text ILIKE %(pat)s"
    params: dict = {"pat": "%" + q.replace("%", r"\%").replace("_", r"\_") + "%", "q": q, "limit": limit + 1}
    if project:
        sql += " AND project = %(project)s"
        params["project"] = project
    if kind:
        sql += " AND kind = %(kind)s"
        params["kind"] = kind
    sql += (
        " ORDER BY (lower(eid) = lower(%(q)s)) DESC, (eid ILIKE %(pat)s) DESC, (name ILIKE %(pat)s) DESC, "
        "kind, project, variant, ref LIMIT %(limit)s"
    )
    with g.connection() as c:
        rows = c.execute(sql, params).fetchall()
    truncated = len(rows) > limit
    hits = [
        {
            "project": r["project"],
            "variant": r["variant"],
            "ref": r["ref"],
            "kind": r["kind"],
            "eid": r["eid"],
            "name": r["name"],
            "data": r["data"] or {},
        }
        for r in rows[:limit]
    ]
    return {"query": q, "hits": hits, "truncated": truncated}


def stats(g: Graph, project: str | None = None) -> dict:
    """Сводка индекса: сущности по видам, связи по типам, что и когда проиндексировано."""
    cond, args = ("WHERE project = %s", [project]) if project else ("", [])
    with g.connection() as c:
        kinds = {
            r["kind"]: r["n"]
            for r in c.execute(f"SELECT kind, count(*) AS n FROM graph_entity {cond} GROUP BY kind ORDER BY kind", args)
        }
        rels = {
            r["kind"]: r["n"]
            for r in c.execute(
                f"SELECT kind, count(*) AS n FROM graph_relation {cond} GROUP BY kind ORDER BY kind", args
            )
        }
        state = [
            {
                "project": r["project"],
                "variant": r["variant"],
                "commit": r["commit"],
                "entities": r["entities"],
                "relations": r["relations"],
                "indexed_at": r["indexed_at"].isoformat(timespec="seconds"),
            }
            for r in c.execute(f"SELECT * FROM graph_state {cond} ORDER BY project, variant", args)
        ]
    return {
        "project": project,
        "entities": sum(kinds.values()),
        "relations": sum(rels.values()),
        "kinds": kinds,
        "relation_kinds": rels,
        "state": state,
    }


def describe_links(res: dict) -> str:
    """Окрестность текстом для агента: корень, затем связи по типам с именами."""
    root = res.get("root") or {"ref": res["ref"], "kind": kind_of(res["ref"]), "name": ""}
    names = {n["ref"]: n for n in res["nodes"]}

    def label(ref: str) -> str:
        n = names.get(ref)
        nm = f" «{n['name']}»" if n and n.get("name") else ""
        vs = f" [{', '.join(n['variants'])}]" if n and n.get("variants") else ""
        return f"{ref}{nm}{vs}"

    head = f"{label(root['ref'])} ({KINDS.get(root['kind'], root['kind'])})"
    if not res["nodes"] or len(res["nodes"]) == 1 and not res["edges"]:
        return head + ": связей нет"
    out: dict[str, dict[str, None]] = {}
    inc: dict[str, dict[str, None]] = {}
    for e in res["edges"]:  # одна связь на вариант → сущность упоминается один раз, варианты в её подписи
        if e["src"] == root["ref"]:
            out.setdefault(e["kind"], {})[e["dst"]] = None
        elif e["dst"] == root["ref"]:
            inc.setdefault(e["kind"], {})[e["src"]] = None
    lines = [head]
    for k, refs in out.items():
        lines.append(f"  {RELATIONS.get(k, k)}: " + "; ".join(label(r) for r in refs))
    for k, refs in inc.items():
        lines.append(f"  ← {RELATIONS.get(k, k)} (к этой сущности): " + "; ".join(label(r) for r in refs))
    far = [n for n in res["nodes"] if n["depth"] > 1]
    if far:
        lines.append(f"  дальше ({res['hops']} шага): " + "; ".join(label(n["ref"]) for n in far[:40]))
    if res.get("truncated"):
        lines.append("  … список обрезан, сузьте kinds или direction")
    return "\n".join(lines)
