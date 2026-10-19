"""Измерения на геометрии — «заземление» агента: масса, центр тяжести, габарит, расстояние,
зазор, пересечение, сечение, сводка по детали.

Ссылки на тела: `part:<id>` (деталь), `fastener:<id>` (крепёж), `body:<id>` (опорное тело
интерфейса), `assembly` (все детали), `assembly+` (детали, крепёж и тела). Голый `<id>` ищется
среди деталей, затем крепежа и тел.
"""

from __future__ import annotations

import build123d as bd

from skelcad.context import Context, MissingStandardError
from skelcad.core.model import Project, text
from skelcad.geom.generator import Geometry

OPS = ("mass", "cog", "bbox", "distance", "clearance", "interference", "section", "part", "list")


def _r(v, n=2):
    return [round(float(x), n) for x in v]


def shape_by_ref(m: Project, g: Geometry, ref: str) -> bd.Shape:
    kind, _, ident = ref.partition(":")
    if ref == "assembly":
        return g.assembly(m, with_purchased=False)
    if ref == "assembly+":
        return g.assembly(m, with_purchased=True)
    if not ident:
        ident, kind = kind, ""
    pools = {"part": g.parts, "fastener": g.fasteners, "body": g.bodies}
    if kind:
        if kind not in pools:
            raise KeyError(f"неизвестный вид ссылки «{kind}»: part | fastener | body | assembly")
        if ident not in pools[kind]:
            raise KeyError(f"нет {kind}:{ident}; есть: {', '.join(pools[kind])}")
        return pools[kind][ident]
    for pool in pools.values():
        if ident in pool:
            return pool[ident]
    have = f"детали: {', '.join(g.parts)}; крепёж: {', '.join(g.fasteners)}; тела: {', '.join(g.bodies)}"
    raise KeyError(f"нет тела «{ident}»; {have}")


def bbox(s: bd.Shape) -> dict:
    bb = s.bounding_box()
    return {"min": _r(bb.min), "max": _r(bb.max), "size": _r(bb.size)}


def masses(m: Project, g: Geometry, ctx: Context) -> dict[str, float]:
    try:
        return g.masses(m, ctx)
    except MissingStandardError as e:
        raise MissingStandardError(f"масса не вычислена — {e}") from e


def measure(m: Project, g: Geometry, ctx: Context, op: str, args: dict | None = None) -> dict:
    args = args or {}
    a, b = args.get("a"), args.get("b")
    if op == "list":
        return {
            "parts": {p.id: text(p.name, m.lang) for p in m.parts},
            "fasteners": list(g.fasteners),
            "bodies": list(g.bodies),
            "note": "ссылки: part:<id> | fastener:<id> | body:<id> | assembly | assembly+",
        }
    if op == "mass":
        ms = masses(m, g, ctx)
        if a:
            pid = a.split(":")[-1]
            if pid not in ms:
                raise KeyError(f"масса считается только для деталей; есть: {', '.join(ms)}")
            return {"ref": a, "mass_kg": round(ms[pid], 3)}
        return {"total_kg": round(sum(ms.values()), 3), "parts_kg": {k: round(v, 3) for k, v in ms.items()}}
    if op == "cog":
        ms = masses(m, g, ctx)
        if a:
            s = shape_by_ref(m, g, a)
            return {"ref": a, "cog": _r(s.center(bd.CenterOf.MASS))}
        tot, acc = 0.0, [0.0, 0.0, 0.0]
        for p in m.parts:
            c = g.parts[p.id].center(bd.CenterOf.MASS)
            w = ms[p.id]
            tot += w
            acc = [acc[0] + c.X * w, acc[1] + c.Y * w, acc[2] + c.Z * w]
        return {"ref": "assembly", "cog": _r([x / tot for x in acc]) if tot else None, "mass_kg": round(tot, 3)}
    if op == "bbox":
        s = shape_by_ref(m, g, a or "assembly")
        return {"ref": a or "assembly", **bbox(s)}
    if op in ("distance", "clearance"):
        if not (a and b):
            raise ValueError(f"{op}: нужны a и b (ссылки на тела)")
        sa, sb = shape_by_ref(m, g, a), shape_by_ref(m, g, b)
        d = float(sa.distance_to(sb))
        out = {"a": a, "b": b, "distance_mm": round(d, 3)}
        if d < 1e-6:
            inter = _common(sa, sb)
            out["touching" if inter <= 1.0 else "interference_mm3"] = True if inter <= 1.0 else round(inter, 1)
        else:
            try:
                _, pa, pb = sa.distance_to_with_closest_points(sb)
                out["closest_points"] = [_r(pa), _r(pb)]
            except Exception:  # noqa: BLE001 — точки не обязательны
                pass
        return out
    if op == "interference":
        if not (a and b):
            raise ValueError("interference: нужны a и b")
        v = _common(shape_by_ref(m, g, a), shape_by_ref(m, g, b))
        return {"a": a, "b": b, "volume_mm3": round(v, 1), "interferes": v > 1.0}
    if op == "section":
        origin, normal = args.get("origin"), args.get("normal")
        if not (origin and normal):
            raise ValueError("section: нужны origin [x,y,z] и normal [nx,ny,nz]")
        s = shape_by_ref(m, g, a or "assembly")
        faces = s.intersect(bd.Plane(origin=tuple(origin), z_dir=tuple(normal)))
        fl = faces.faces() if hasattr(faces, "faces") else []
        area = sum(f.area for f in fl)
        out = {"ref": a or "assembly", "origin": origin, "normal": normal, "area_mm2": round(area, 1), "faces": len(fl)}
        if fl:
            out["bbox"] = bbox(bd.Compound(children=list(fl)))
        return out
    if op == "part":
        if not a:
            raise ValueError("part: нужен a — id детали")
        pid = a.split(":")[-1]
        p = m.part(pid)
        s = g.parts[pid]
        ms = {}
        try:
            ms = masses(m, g, ctx)
        except MissingStandardError:
            pass
        return {
            "id": pid,
            "name": text(p.name, m.lang),
            "kind": p.kind,
            "role": p.role,
            "material": p.material,
            "volume_mm3": round(s.volume, 1),
            "mass_kg": round(ms[pid], 3) if pid in ms else None,
            "cog": _r(s.center(bd.CenterOf.MASS)),
            **bbox(s),
            "faces": len(s.faces()),
            "valid": bool(s.is_valid),
            "model": p.model_dump(mode="json", exclude_defaults=True),
        }
    raise ValueError(f"неизвестная операция «{op}»; есть: {', '.join(OPS)}")


def _common(sa: bd.Shape, sb: bd.Shape) -> float:
    from skelcad.rules.geometric import common_volume

    return sum(common_volume(x, y) for x in sa.solids() for y in sb.solids())
