"""Генератор опоры под трубопровод: параметры варианта + скелет -> узел «опора».

Стойка (труба или две пластины) — отдельная функция; общая часть (опорная плита с анкерами,
верхняя плита, направляющие, опорное тело трубы) — одна для всех вариантов.
Система координат: X — вдоль трубы, Y — поперёк, Z — вверх, Z=0 — пол.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from skelcad.context import Context
from skelcad.core.model import (
    Assumption,
    Cylinder,
    Fastener,
    Hole,
    Outline,
    Placement,
    PlatePart,
    Project,
    TubePart,
    Unit,
    Weld,
    WeldSegment,
)
from skelcad.core.vec import ceil_to
from skelcad.rules import GenResult

X: tuple = (1.0, 0.0, 0.0)
Y: tuple = (0.0, 1.0, 0.0)
Z: tuple = (0.0, 0.0, 1.0)
C_PLATE = "#7f93a8"
C_POST = "#c58b3c"
C_GUIDE = "#6f9e6a"
AT_BASE = ["at_base"]


class PlateParams(BaseModel):
    thickness: float = 12
    edge: float = 35
    corner_radius: float = 8


class TopParams(BaseModel):
    thickness: float = 12
    length: float = 160
    width: float = 160


class GuideParams(BaseModel):
    thickness: float = 8
    height: float = 60
    length: float = 160


class AnchorParams(BaseModel):
    clearance: float = 3


class WeldParams(BaseModel):
    leg_base: float = 6
    leg_other: float = 5


class TubePost(BaseModel):
    kind: Literal["tube"]
    tube: str


class PlatesPost(BaseModel):
    kind: Literal["plates"]
    thickness: float
    width: float
    gap: float


class Params(BaseModel):
    material: str = "St3sp"
    base_plate: PlateParams = PlateParams()
    top_plate: TopParams = TopParams()
    guides: GuideParams = GuideParams()
    anchors: AnchorParams = AnchorParams()
    welds: WeldParams = WeldParams()
    post: TubePost | PlatesPost


@dataclass
class Frame:
    """Общие отметки: пол, низ/верх стойки, верх верхней плиты."""

    tb: float
    z_post0: float
    z_post1: float
    z_top: float
    r_pipe: float
    material: str


@dataclass
class Post:
    parts: list
    welds: list
    half_x: float  # след стойки на плите
    half_y: float
    derived: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)


def seg(a, b) -> WeldSegment:
    return WeldSegment(start=tuple(map(float, a)), end=tuple(map(float, b)))


def ring_xy(z: float, r: float, n: int = 24) -> list[WeldSegment]:
    pts = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n + 1)]
    return [seg(pts[i], pts[i + 1]) for i in range(n)]


def post_tube(p: Params, f: Frame, ctx: Context) -> Post:
    t = ctx.tube(p.post.tube)
    od, wall = t["od"], t["wall"]
    std = ctx.table("tubes").get("standard", "")
    length = f.z_post1 - f.z_post0
    part = TubePart(
        id="post",
        name=f"Стойка, труба {p.post.tube.replace('x', '×')} {std} L={length:g}",
        role="post",
        material=f.material,
        color=C_POST,
        tube_size=p.post.tube,
        od=od,
        wall=wall,
        length=length,
        center=(0.0, 0.0, (f.z_post0 + f.z_post1) / 2),
        axis=Z,
    )
    welds = [
        Weld(
            id="w_post_base",
            parts=("base_plate", "post"),
            leg=p.welds.leg_base,
            tags=AT_BASE,
            segments=ring_xy(f.z_post0, od / 2),
            note="кольцевой шов стойки к опорной плите",
        ),
        Weld(
            id="w_post_top",
            parts=("top_plate", "post"),
            leg=p.welds.leg_other,
            segments=ring_xy(f.z_post1, od / 2),
            note="кольцевой шов стойки к верхней плите",
        ),
    ]
    return Post(
        parts=[part],
        welds=welds,
        half_x=od / 2,
        half_y=od / 2,
        derived={"труба стойки": p.post.tube, "длина стойки, мм": length},
    )


def post_plates(p: Params, f: Frame, ctx: Context) -> Post:
    pp = p.post
    tp, w, g = pp.thickness, pp.width, pp.gap
    length = f.z_post1 - f.z_post0
    parts, welds = [], []
    for side, x0 in (("L", -(g / 2 + tp)), ("R", g / 2)):
        pid = f"post_{side}"
        parts.append(
            PlatePart(
                id=pid,
                name=f"Пластина стойки {'левая' if side == 'L' else 'правая'} δ{tp:g}",
                role="post",
                material=f.material,
                color=C_POST,
                thickness=tp,
                outline=Outline(points=[(-w / 2, 0.0), (w / 2, 0.0), (w / 2, length), (-w / 2, length)]),
                placement=Placement(origin=(x0, 0.0, f.z_post0), u=Y, normal=X),
                free_edges={"боковая": length},
            )
        )
        x_out, x_in = (x0, x0 + tp) if side == "L" else (x0 + tp, x0)
        for plate, z, leg, tag in (
            ("base_plate", f.z_post0, p.welds.leg_base, AT_BASE),
            ("top_plate", f.z_post1, p.welds.leg_other, []),
        ):
            welds += [
                Weld(
                    id=f"w_{pid}_{plate}_out",
                    parts=(plate, pid),
                    leg=leg,
                    tags=tag,
                    segments=[seg((x_out, -w / 2, z), (x_out, w / 2, z))],
                    note="снаружи",
                ),
                Weld(
                    id=f"w_{pid}_{plate}_in",
                    parts=(plate, pid),
                    leg=leg,
                    tags=tag,
                    segments=[seg((x_in, -w / 2, z), (x_in, w / 2, z))],
                    access_gap=g,
                    access_depth=length,
                    note="между пластинами стойки",
                ),
            ]
    return Post(
        parts=parts,
        welds=welds,
        half_x=g / 2 + tp,
        half_y=w / 2,
        derived={"пластины стойки, мм": f"{w:g}×{length:g}×{tp:g}", "щель между пластинами, мм": g},
        assumptions=["Внутренние швы стойки варятся до установки верхней плиты (щель открыта сверху)."],
    )


POSTS = {"tube": post_tube, "plates": post_plates}


def generate(project: Project, params: dict, ctx: Context) -> GenResult:
    p = Params.model_validate(params)
    sk, req = project.skeleton, project.requirements
    pipe_if, floor_if = sk.interface("pipe"), sk.interface("floor")
    axis = next(d for d in sk.datums if d.id == pipe_if.datum)
    H = axis.origin[2]
    r_pipe = float(pipe_if.params["od"]) / 2
    gap_lat = float(pipe_if.params.get("lateral_gap", 3))
    anchor_size = str(floor_if.params["anchor_size"])
    tb, tt = p.base_plate.thickness, p.top_plate.thickness
    f = Frame(tb=tb, z_post0=tb, z_post1=H - r_pipe - tt, z_top=H - r_pipe, r_pipe=r_pipe, material=p.material)
    an = ctx.fastener(anchor_size)
    post = POSTS[p.post.kind](p, f, ctx)

    # верхняя плита и направляющие
    tl, tw = p.top_plate.length, p.top_plate.width
    top = PlatePart(
        id="top_plate",
        name=f"Плита верхняя δ{tt:g} {tl:g}×{tw:g}",
        role="top_plate",
        material=p.material,
        color=C_PLATE,
        thickness=tt,
        outline=Outline(points=[(0, 0), (tl, 0), (tl, tw), (0, tw)]),
        placement=Placement(origin=(-tl / 2, -tw / 2, f.z_post1), u=X, normal=Z),
    )
    gd = p.guides
    guides, gwelds = [], []
    for side, y0 in (("L", -(r_pipe + gap_lat) - gd.thickness), ("R", r_pipe + gap_lat)):
        pid = f"guide_{side}"
        # u = X, normal = Y -> v = -Z: контур задаём при v в [-height, 0]
        guides.append(
            PlatePart(
                id=pid,
                name=f"Направляющая {'левая' if side == 'L' else 'правая'} δ{gd.thickness:g}",
                role="guide",
                material=p.material,
                color=C_GUIDE,
                thickness=gd.thickness,
                outline=Outline(
                    points=[
                        (-gd.length / 2, 0.0),
                        (gd.length / 2, 0.0),
                        (gd.length / 2, -gd.height),
                        (-gd.length / 2, -gd.height),
                    ]
                ),
                placement=Placement(origin=(0.0, y0, f.z_top), u=X, normal=Y),
                free_edges={"верхняя": gd.height},
            )
        )
        y_out = y0 if side == "L" else y0 + gd.thickness
        gwelds.append(
            Weld(
                id=f"w_{pid}_top",
                parts=("top_plate", pid),
                leg=p.welds.leg_other,
                segments=[
                    seg((-gd.length / 2, y_out, f.z_top), (gd.length / 2, y_out, f.z_top)),
                    seg((-gd.length / 2, y0, f.z_top), (-gd.length / 2, y0 + gd.thickness, f.z_top)),
                    seg((gd.length / 2, y0, f.z_top), (gd.length / 2, y0 + gd.thickness, f.z_top)),
                ],
                note="снаружи и по торцам; изнутри шов невозможен (зазор до трубы)",
            )
        )

    # анкеры и опорная плита: вынос за след стойки по размеру ключа
    leg = p.welds.leg_base
    ax = ceil_to(post.half_x + leg + an["socket_od"] / 2 + p.anchors.clearance, 5)
    ay = ceil_to(post.half_y + leg + an["socket_od"] / 2 + p.anchors.clearance, 5)
    bp = p.base_plate
    wx, wy = 2 * (ax + bp.edge), 2 * (ay + bp.edge)
    holes, fasteners = [], []
    for i, y in enumerate((-ay, ay)):
        for j, x in enumerate((-ax, ax)):
            hid = f"a{i}{j}"
            holes.append(
                Hole(id=hid, purpose="anchor", diameter=an["hole"], center=(x, y), note=f"под анкер {anchor_size}")
            )
            fasteners.append(
                Fastener(
                    id=f"anchor_{hid}",
                    fastener_type="anchor",
                    size=anchor_size,
                    part="base_plate",
                    hole=hid,
                    position=(x, y, 0.0),
                    axis=Z,
                    clamp_depth=tb,
                )
            )
    base = PlatePart(
        id="base_plate",
        name=f"Плита опорная δ{tb:g} {wx:g}×{wy:g}",
        role="base_plate",
        material=p.material,
        color=C_PLATE,
        thickness=tb,
        outline=Outline(
            points=[(-wx / 2, -wy / 2), (wx / 2, -wy / 2), (wx / 2, wy / 2), (-wx / 2, wy / 2)],
            corner_radius=bp.corner_radius,
        ),
        placement=Placement(origin=(0.0, 0.0, 0.0), u=X, normal=Z),
        holes=holes,
    )

    # опорное тело трубы
    pipe_if.body = Cylinder(center=(0.0, 0.0, H), axis=X, diameter=2 * r_pipe, length=float(pipe_if.params["length"]))
    pipe_if.params.update({"z_rest": f.z_top, "height": H})

    L = req.loads
    gdyn = req.factors.get("gamma_dyn", 1.0)
    assumptions = [
        Assumption(
            id="G0",
            topic="loads",
            text=(
                f"Нагрузки: Fv = {L.get('Fv', 0):g} кН вниз, Fx = {L.get('Fx', 0):g} кН вдоль трубы (трение), "
                f"Fy = {L.get('Fy', 0):g} кН поперёк на направляющую; γd = {gdyn:g}; K_треб = {req.safety_required:g}; "
                f"ось трубы на отметке {H:g} мм, труба Ø{2 * r_pipe:g}."
            ),
        )
    ]
    assumptions += [Assumption(id=f"T{i + 1}", topic="variant", text=s) for i, s in enumerate(post.assumptions)]

    unit = Unit(
        id="support",
        name="Опора",
        material=p.material,
        interfaces=["floor", "pipe"],
        parts=[base, *post.parts, top, *guides],
        joints=[*post.welds, *gwelds, *fasteners],
        derived={
            "стойка": p.post.kind,
            "отметка верха опоры, мм": f.z_top,
            "высота стойки, мм": f.z_post1 - f.z_post0,
            "анкеры по X/Y, ±мм": f"{ax:g} / {ay:g}",
            "опорная плита, мм": f"{wx:g}×{wy:g}×{tb:g}",
            **post.derived,
        },
    )
    return GenResult(units=[unit], derived=dict(unit.derived), assumptions=assumptions)
