"""Генератор геометрии: проектная модель -> тела build123d.

Геометрия не содержит собственных размеров: всё берётся из модели и таблиц контекста.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import build123d as bd

from skelcad.context import Context
from skelcad.core.model import Cylinder, Fastener, PlatePart, Project, TubePart, text

BIG = 5000.0
C_FASTENER = "#5b5f66"
C_BODY = "#3f8f5a"
AXIAL = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)  # от торца вдоль оси


@dataclass
class Geometry:
    parts: dict[str, bd.Solid]  # изготавливаемые детали по id
    fasteners: dict[str, bd.Compound] = field(default_factory=dict)  # крепёж: стержень + шайба + гайка
    bodies: dict[str, bd.Solid] = field(default_factory=dict)  # опорные тела интерфейсов (вал, ось)

    def assembly(self, project: Project, with_purchased: bool = True) -> bd.Compound:
        children = []
        for p in project.parts:
            s = self.parts[p.id]
            s.label, s.color = p.id, bd.Color(p.color)
            children.append(s)
        if with_purchased:
            for fid, f in self.fasteners.items():
                f.label = fid
                children.append(f)
            for bid, b in self.bodies.items():
                b.label, b.color = bid, bd.Color(C_BODY)
                children.append(b)
        return bd.Compound(children=children, label=project.variant or project.id)

    def masses(self, project: Project, ctx: Context) -> dict[str, float]:
        return {p.id: self.parts[p.id].volume * ctx.material(p.material)["density"] * 1e-9 for p in project.parts}


def plane(origin, u, normal) -> bd.Plane:
    return bd.Plane(origin=origin, x_dir=u, z_dir=normal)


def any_perp(n) -> tuple:
    return (0, 0, 1) if abs(n[2]) < 0.9 else (1, 0, 0)


def single_solid(shape) -> bd.Solid:
    solids = shape.solids()
    if len(solids) != 1:
        raise ValueError(f"ожидалось одно тело, получено {len(solids)}")
    return solids[0]


def plate_solid(p: PlatePart) -> bd.Solid:
    o = p.outline
    if o.circles:
        edges = (
            [bd.Edge.make_line(o.points[i], o.points[(i + 1) % len(o.points)]) for i in range(len(o.points))]
            if len(o.points) > 1
            else []
        )
        edges += [bd.Edge.make_circle(r).moved(bd.Location((cu, cv, 0))) for cu, cv, r in o.circles]
        face = bd.make_hull(edges).face()
    else:
        face = bd.Face(bd.Wire.make_polygon([(*pt, 0) for pt in o.points], close=True))
        if o.corner_radius > 0:
            face = face.fillet_2d(o.corner_radius, face.vertices())
    for h in p.holes:
        face = face - bd.Face(bd.Wire.make_circle(h.diameter / 2)).moved(bd.Location((*h.center, 0)))
    face = face if isinstance(face, bd.Face) else face.faces()[0]
    # направление задаём явно: нормаль грани зависит от обхода контура
    solid = bd.extrude(face, amount=p.thickness, dir=(0, 0, 1))
    pl = p.placement
    solid = solid.moved(bd.Location(plane(pl.origin, pl.u, pl.normal)))
    for t in p.trims:
        half = bd.Box(BIG, BIG, BIG).moved(
            bd.Location(
                plane(tuple(t.point[i] + t.normal[i] * BIG / 2 for i in range(3)), any_perp(t.normal), t.normal)
            )
        )
        solid = solid & half
    return single_solid(solid)


def tube_solid(t: TubePart) -> bd.Solid:
    inner = t.bore.diameter if t.bore else t.od - 2 * t.wall
    s = bd.Cylinder(t.od / 2, t.length) - bd.Cylinder(inner / 2, t.length)
    return single_solid(s.moved(bd.Location(plane(t.center, any_perp(t.axis), t.axis))))


def cylinder_solid(c: Cylinder) -> bd.Solid:
    s = bd.Cylinder(c.diameter / 2, c.length).moved(bd.Location(plane(c.center, any_perp(c.axis), c.axis)))
    return single_solid(s)


def fastener_solid(f: Fastener, ctx: Context) -> bd.Compound:
    """Стержень (шпилька/болт), шайба и гайка вдоль оси крепежа от точки `position`."""
    c = ctx.fastener(f.size)
    embed = ctx.anchor(f.size)["hef"] if f.fastener_type == "anchor" else 0.0
    ax = f.axis
    base = f.position
    pl = lambda s: plane(tuple(base[i] + ax[i] * s for i in range(3)), any_perp(ax), ax)
    y0 = f.clamp_depth
    washer = (
        bd.Cylinder(c["washer_d"] / 2, c["washer_s"], align=AXIAL)
        - bd.Cylinder(c["d"] / 2 + 0.5, c["washer_s"], align=AXIAL)
    ).moved(bd.Location(pl(y0)))
    nut_y = y0 + c["washer_s"]
    nut = bd.extrude(bd.RegularPolygon(c["nut_e"] / 2, 6), amount=c["nut_m"]) - bd.Cylinder(
        c["d"] / 2, c["nut_m"], align=AXIAL
    )
    nut = nut.moved(bd.Location(pl(nut_y)))
    rod_top = nut_y + c["nut_m"] + 2 * c["pitch"]
    rod = bd.Cylinder(c["d"] / 2, rod_top + embed, align=AXIAL).moved(bd.Location(pl(-embed)))
    parts = []
    for name, s in (("rod", rod), ("washer", washer), ("nut", nut)):
        s = single_solid(s)
        s.label, s.color = f"{f.id}_{name}", bd.Color(C_FASTENER)
        parts.append(s)
    return bd.Compound(children=parts)


def generate(project: Project, ctx: Context) -> Geometry:
    parts = {}
    for p in project.parts:
        try:
            parts[p.id] = plate_solid(p) if isinstance(p, PlatePart) else tube_solid(p)
        except Exception as e:  # noqa: BLE001 — ошибку ядра OCCT привязываем к детали
            raise ValueError(f"деталь {p.id} ({text(p.name)}): {e}") from e
    fasteners = {f.id: fastener_solid(f, ctx) for f in project.fasteners}
    bodies = {i.id: cylinder_solid(i.body) for i in project.skeleton.interfaces if i.body}
    return Geometry(parts=parts, fasteners=fasteners, bodies=bodies)
