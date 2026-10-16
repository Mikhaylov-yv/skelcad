"""Генератор кронштейна: параметры варианта + скелет проекта -> узел «кронштейн».

Топология (вилка / ступица / коробка) — отдельная функция; общая часть (опорная плита,
анкеры, опорное тело оси) — одна для всех вариантов. Все размеры деталей и их положение
вычисляются здесь; геометрия затем строится ядром по модели.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

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
    Trim,
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
C_MEMBER = "#c58b3c"
C_HUB = "#a3504a"
AT_BASE = ["at_base"]  # тег швов к опорной плите (группа швов в расчёте, доступ ключа)


# ---------- схема params ----------


class BasePlateParams(BaseModel):
    thickness: float = 16
    edge: float = 45  # расстояние от оси анкера до кромки плиты
    corner_radius: float = 10


class AnchorParams(BaseModel):
    clearance: float = 3  # зазор между головкой ключа и катетом шва


class WeldParams(BaseModel):
    leg_wall: float = 8  # катет швов к опорной плите
    leg_other: float = 6


class Params(BaseModel):
    topology: str
    material: str = "St3sp"
    height_ratio: float = 1.0
    base_plate: BasePlateParams = BasePlateParams()
    anchors: AnchorParams = AnchorParams()
    welds: WeldParams = WeldParams()
    members: dict


@dataclass
class Ctx:
    """Входы из скелета и требований, общие для всех топологий."""

    offset: float  # вылет оси от плоскости стены
    axle_d: float
    fit_hole: str
    fit_shaft: str
    overhang: float
    anchor_size: str
    tb: float  # толщина опорной плиты
    h: float  # высота элементов у стены


# ---------- вспомогательная геометрия ----------


def tangent_point(p: tuple, c: tuple, r: float, lower: bool) -> tuple:
    """Точка касания прямой из p к окружности (c, r); lower — нижняя касательная."""
    dx, dy = p[0] - c[0], p[1] - c[1]
    d = math.hypot(dx, dy)
    a, b = math.atan2(dy, dx), math.acos(r / d)
    pts = [(c[0] + r * math.cos(a + s * b), c[1] + r * math.sin(a + s * b)) for s in (1, -1)]
    return min(pts, key=lambda q: q[1]) if lower else max(pts, key=lambda q: q[1])


def line_circle_entry(p: tuple, q: tuple, c: tuple, r: float) -> tuple:
    """Первая точка входа отрезка p->q в окружность (c, r)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - c[0], p[1] - c[1]
    a, b, cc = dx * dx + dy * dy, 2 * (fx * dx + fy * dy), fx * fx + fy * fy - r * r
    t = (-b - math.sqrt(b * b - 4 * a * cc)) / (2 * a)
    return (p[0] + t * dx, p[1] + t * dy)


def seg(a, b) -> WeldSegment:
    return WeldSegment(start=tuple(map(float, a)), end=tuple(map(float, b)))


def arc_segments(center3, r: float, a0: float, a1: float, n: int = 12) -> list[WeldSegment]:
    """Дуга окружности в плоскости YZ, полилиния из n отрезков; угол отсчитывается от +Y к +Z."""
    cx, cy, cz = center3
    pts = [
        (cx, cy + r * math.cos(a0 + (a1 - a0) * i / n), cz + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)
    ]
    return [seg(pts[i], pts[i + 1]) for i in range(n)]


@dataclass
class Members:
    """Результат топологии: несущие элементы над опорной плитой."""

    parts: list
    welds: list
    half_width: float  # полуширина следа элементов на плите по X
    z_range: tuple[float, float]  # след элементов на плите по Z
    seat_span: float  # длина посадки оси вдоль X
    derived: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)


# ---------- топологии ----------


def build_fork(p: Params, c: Ctx, ctx: Context) -> Members:
    """A. Вилка: две параллельные щеки с проушинами, ось проходит через обе."""
    m, tb, h = p.members, c.tb, c.h
    g, tc, ring = m["gap"], m["cheek_thickness"], m["lug_ring"]
    uc = c.offset - tb  # центр расточки в координатах эскиза щеки
    r_lug = c.axle_d / 2 + ring
    leg = p.welds.leg_wall
    parts, welds = [], []
    top, bot = (0.0, h / 2), (0.0, -h / 2)
    free = {
        "верхняя": math.dist(top, tangent_point(top, (uc, 0), r_lug, lower=False)),
        "нижняя": math.dist(bot, tangent_point(bot, (uc, 0), r_lug, lower=True)),
    }
    for side, x0 in (("L", -(g / 2 + tc)), ("R", g / 2)):
        pid = f"cheek_{side}"
        parts.append(
            PlatePart(
                id=pid,
                name=f"Щека {'левая' if side == 'L' else 'правая'} δ{tc:g}",
                role="cheek",
                material=p.material,
                color=C_MEMBER,
                thickness=tc,
                outline=Outline(points=[bot, top], circles=[(uc, 0.0, r_lug)]),
                placement=Placement(origin=(x0, tb, 0.0), u=Y, normal=X),
                holes=[
                    Hole(
                        id="bore",
                        purpose="shaft_seat",
                        diameter=c.axle_d,
                        center=(uc, 0.0),
                        tolerance=c.fit_hole,
                        note="расточка под ось после сварки",
                    )
                ],
                free_edges=free,
            )
        )
        x_out, x_in = (x0, x0 + tc) if side == "L" else (x0 + tc, x0)
        depth = uc + r_lug
        welds += [
            Weld(
                id=f"w_{pid}_out",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x_out, tb, -h / 2), (x_out, tb, h / 2))],
                note="снаружи вилки",
            ),
            Weld(
                id=f"w_{pid}_in",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x_in, tb, -h / 2), (x_in, tb, h / 2))],
                access_gap=g,
                access_depth=depth,
                note="внутри вилки, в щели между щеками",
            ),
            Weld(
                id=f"w_{pid}_ends",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x0, tb, h / 2), (x0 + tc, tb, h / 2)), seg((x0, tb, -h / 2), (x0 + tc, tb, -h / 2))],
                note="обварка торцов щеки",
            ),
        ]
    return Members(
        parts=parts,
        welds=welds,
        half_width=g / 2 + tc,
        z_range=(-h / 2, h / 2),
        seat_span=g + 2 * tc,
        derived={"радиус проушины R, мм": r_lug, "ширина щели вилки, мм": g},
        assumptions=[
            "Щеки соединены только через опорную плиту и ось; поперечной связи нет — "
            "осевая сила Fa воспринимается изгибом щек из плоскости (не рассчитывалась)."
        ],
    )


def build_hub(p: Params, c: Ctx, ctx: Context) -> Members:
    """B. Ступица из трубы + два ребра жёсткости до опорной плиты."""
    m, tb, h = p.members, c.tb, c.h
    t = ctx.tube(m["tube"])
    std = ctx.table("tubes").get("standard", "")
    od, wall, lh = t["od"], t["wall"], m["hub_length"]
    tr, setback = m["rib_thickness"], m["rib_setback"]
    uc, r = c.offset - tb, od / 2
    leg, leg2 = p.welds.leg_wall, p.welds.leg_other
    top, bot = (0.0, h / 2), (0.0, -h / 2)
    top_end, bot_end = (uc, 0.8 * r), (uc, -0.8 * r)
    e_top = line_circle_entry(top, top_end, (uc, 0), r)
    e_bot = line_circle_entry(bot, bot_end, (uc, 0), r)
    a_top = math.atan2(e_top[1], e_top[0] - uc)
    a_bot = math.atan2(e_bot[1], e_bot[0] - uc)
    parts = [
        TubePart(
            id="hub",
            name=f"Ступица, труба {m['tube'].replace('x', '×')} {std} L={lh:g}",
            role="hub",
            material=p.material,
            color=C_HUB,
            tube_size=m["tube"],
            od=od,
            wall=wall,
            length=lh,
            center=(0.0, c.offset, 0.0),
            axis=X,
            bore=Hole(
                id="bore",
                purpose="shaft_seat",
                diameter=c.axle_d,
                center=(0.0, 0.0),
                tolerance=c.fit_hole,
                note="расточка трубы после сварки",
            ),
        )
    ]
    welds = []
    gap = lh - 2 * setback - 2 * tr
    for side in ("L", "R"):
        x_outer = (lh / 2 - setback) * (1 if side == "R" else -1)
        x0 = x_outer - tr if side == "R" else x_outer
        pid = f"rib_{side}"
        parts.append(
            PlatePart(
                id=pid,
                name=f"Ребро {'левое' if side == 'L' else 'правое'} δ{tr:g}",
                role="rib",
                material=p.material,
                color=C_MEMBER,
                thickness=tr,
                outline=Outline(points=[bot, top, top_end, bot_end]),
                placement=Placement(origin=(x0, tb, 0.0), u=Y, normal=X),
                holes=[
                    Hole(
                        id="hub_seat",
                        purpose="part_seat",
                        diameter=od,
                        center=(uc, 0.0),
                        note="вырез под трубу ступицы",
                    )
                ],
                free_edges={"верхняя": math.dist(top, e_top), "нижняя": math.dist(bot, e_bot)},
            )
        )
        x_out, x_in = (x0, x0 + tr) if side == "L" else (x0 + tr, x0)
        welds += [
            Weld(
                id=f"w_{pid}_out",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x_out, tb, -h / 2), (x_out, tb, h / 2))],
            ),
            Weld(
                id=f"w_{pid}_in",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x_in, tb, -h / 2), (x_in, tb, h / 2))],
                access_gap=gap,
                access_depth=uc,
                note="между рёбрами",
            ),
            Weld(
                id=f"w_{pid}_hub",
                parts=(pid, "hub"),
                leg=leg2,
                segments=arc_segments((x_out, c.offset, 0), r, a_top, 2 * math.pi + a_bot)
                + arc_segments((x_in, c.offset, 0), r, a_top, 2 * math.pi + a_bot),
                access_gap=gap,
                access_depth=0,
                note="ребро к трубе с двух сторон по дуге",
            ),
        ]
    return Members(
        parts=parts,
        welds=welds,
        half_width=lh / 2 - setback,
        z_range=(-h / 2, h / 2),
        seat_span=lh,
        derived={
            "труба ступицы": m["tube"],
            "длина ступицы, мм": lh,
            "щель между рёбрами, мм": gap,
            "стенка ступицы после расточки, мм": (od - c.axle_d) / 2,
        },
        assumptions=[
            f"Ступица из трубы {m['tube']} растачивается после сварки до Ø{c.axle_d:g}"
            f"{c.fit_hole} (внутренний Ø трубы {od - 2 * wall:g} мм)."
        ],
    )


def build_box(p: Params, c: Ctx, ctx: Context) -> Members:
    """C. Коробчатая консоль: две боковины + верхний и наклонный нижний пояс, бобышка из трубы."""
    m, tb, h = p.members, c.tb, c.h
    t = ctx.tube(m["boss_tube"])
    std = ctx.table("tubes").get("standard", "")
    od, wall = t["od"], t["wall"]
    b, ts, tcv, ring, prot = (
        m["width"],
        m["side_thickness"],
        m["cover_thickness"],
        m["side_ring"],
        m["boss_protrusion"],
    )
    uc = c.offset - tb
    rs = od / 2 + ring  # радиус скругления боковины вокруг бобышки
    hb = h - rs  # нижняя точка боковины у плиты (верх = rs)
    leg, leg2 = p.welds.leg_wall, p.welds.leg_other
    P = (0.0, -hb)
    T = tangent_point(P, (uc, 0.0), rs, lower=True)
    L = math.dist(P, T)
    wi = b - 2 * ts
    lb = b + 2 * prot
    parts, welds = [], []
    parts.append(
        TubePart(
            id="boss",
            name=f"Бобышка, труба {m['boss_tube'].replace('x', '×')} {std} L={lb:g}",
            role="boss",
            material=p.material,
            color=C_HUB,
            tube_size=m["boss_tube"],
            od=od,
            wall=wall,
            length=lb,
            center=(0.0, c.offset, 0.0),
            axis=X,
            bore=Hole(
                id="bore",
                purpose="shaft_seat",
                diameter=c.axle_d,
                center=(0.0, 0.0),
                tolerance=c.fit_hole,
                note="расточка после сварки",
            ),
        )
    )
    for side in ("L", "R"):
        x0 = -b / 2 if side == "L" else b / 2 - ts
        x_out = -b / 2 if side == "L" else b / 2
        pid = f"side_{side}"
        parts.append(
            PlatePart(
                id=pid,
                name=f"Боковина {'левая' if side == 'L' else 'правая'} δ{ts:g}",
                role="side",
                material=p.material,
                color=C_MEMBER,
                thickness=ts,
                outline=Outline(points=[(0.0, rs), P], circles=[(uc, 0.0, rs)]),
                placement=Placement(origin=(x0, tb, 0.0), u=Y, normal=X),
                holes=[
                    Hole(
                        id="boss_seat", purpose="part_seat", diameter=od, center=(uc, 0.0), note="отверстие под бобышку"
                    )
                ],
            )
        )
        welds += [
            Weld(
                id=f"w_{pid}_wall",
                parts=("base_plate", pid),
                leg=leg,
                tags=AT_BASE,
                segments=[seg((x_out, tb, -hb), (x_out, tb, rs))],
                note="снаружи коробки",
            ),
            Weld(
                id=f"w_{pid}_boss",
                parts=(pid, "boss"),
                leg=leg2,
                segments=arc_segments((x_out, c.offset, 0), od / 2, 0, 2 * math.pi, 24),
                note="кольцевой шов бобышки снаружи",
            ),
        ]
    vdir = (0.0, (T[0] - P[0]) / L, (T[1] - P[1]) / L)
    n_bot = (0.0, -vdir[2], vdir[1])  # u × v при u = X
    parts += [
        PlatePart(
            id="cover_top",
            name=f"Пояс верхний δ{tcv:g}",
            role="cover",
            material=p.material,
            color=C_MEMBER,
            thickness=tcv,
            outline=Outline(points=[(0, 0), (wi, 0), (wi, uc), (0, uc)]),
            placement=Placement(origin=(-wi / 2, tb, rs - tcv), u=X, normal=Z),
        ),
        PlatePart(
            id="cover_bot",
            name=f"Пояс нижний наклонный δ{tcv:g}",
            role="cover",
            material=p.material,
            color=C_MEMBER,
            thickness=tcv,
            outline=Outline(points=[(0, -2 * tcv), (wi, -2 * tcv), (wi, L), (0, L)]),
            placement=Placement(origin=(-wi / 2, tb + P[0], P[1]), u=X, normal=n_bot),
            trims=[Trim(point=(0, tb, 0), normal=Y, reason="подрезка торца по плоскости опорной плиты")],
        ),
    ]
    zt = rs
    welds += [
        Weld(
            id="w_cover_top_wall",
            parts=("base_plate", "cover_top"),
            leg=leg,
            tags=AT_BASE,
            segments=[seg((-wi / 2, tb, zt), (wi / 2, tb, zt))],
            note="сверху",
        ),
        Weld(
            id="w_cover_bot_wall",
            parts=("base_plate", "cover_bot"),
            leg=leg,
            tags=AT_BASE,
            segments=[seg((-wi / 2, tb, -hb), (wi / 2, tb, -hb))],
            note="снизу",
        ),
    ]
    for s, side in ((-1, "L"), (1, "R")):
        welds += [
            Weld(
                id=f"w_cover_top_{side}",
                parts=("cover_top", f"side_{side}"),
                leg=leg2,
                segments=[seg((s * wi / 2, tb, zt), (s * wi / 2, tb + uc, zt))],
                note="угловое соединение снаружи (тип У по ГОСТ 14771)",
            ),
            Weld(
                id=f"w_cover_bot_{side}",
                parts=("cover_bot", f"side_{side}"),
                leg=leg2,
                segments=[seg((s * wi / 2, tb + P[0], P[1]), (s * wi / 2, tb + T[0], T[1]))],
                note="угловое соединение снаружи (тип У по ГОСТ 14771)",
            ),
        ]
    return Members(
        parts=parts,
        welds=welds,
        half_width=b / 2,
        z_range=(-hb, rs),
        seat_span=lb,
        derived={
            "ширина коробки, мм": b,
            "радиус боковины у бобышки, мм": rs,
            "уклон нижнего пояса, °": round(math.degrees(math.atan2(T[1] - P[1], T[0] - P[0])), 1),
            "стенка бобышки после расточки, мм": (od - c.axle_d) / 2,
        },
        assumptions=[
            "Коробка замкнута: швы изнутри невыполнимы, все швы — только снаружи "
            "(односторонние угловые и угловые соединения).",
            f"Бобышка из трубы {m['boss_tube']} растачивается после сварки до Ø{c.axle_d:g}{c.fit_hole}.",
        ],
    )


TOPOLOGIES = {"fork": build_fork, "hub": build_hub, "box": build_box}


# ---------- общая сборка узла ----------


def generate(project: Project, params: dict, ctx: Context) -> GenResult:
    p = Params.model_validate(params)
    sk, req = project.skeleton, project.requirements
    axle_if, wall_if = sk.interface("axle"), sk.interface("wall")
    axis = next(d for d in sk.datums if d.id == axle_if.datum)
    ap = axle_if.params
    c = Ctx(
        offset=axis.origin[1],
        axle_d=float(ap["d"]),
        fit_hole=str(ap["fit_hole"]),
        fit_shaft=str(ap["fit_shaft"]),
        overhang=float(ap.get("overhang", 0)),
        anchor_size=str(wall_if.params["anchor_size"]),
        tb=p.base_plate.thickness,
        h=ceil_to(axis.origin[1] * p.height_ratio, 10),
    )
    an = ctx.fastener(c.anchor_size)
    mem = TOPOLOGIES[p.topology](p, c, ctx)

    # раскладка анкеров — из следа элементов и размера ключа
    ax = mem.half_width + p.welds.leg_wall + an["socket_od"] / 2 + p.anchors.clearance
    ax = ceil_to(ax, 5)
    z0, z1 = mem.z_range
    bp, tb = p.base_plate, c.tb
    w, z_lo, z_hi = 2 * (ax + bp.edge), z0 - bp.edge, z1 + bp.edge
    # эскиз плиты: u = Z, v = X (плоскость XZ, выдавливание по +Y)
    holes, fasteners = [], []
    for i, z in enumerate((z0, z1)):
        for j, x in enumerate((-ax, ax)):
            hid = f"a{i}{j}"
            holes.append(
                Hole(id=hid, purpose="anchor", diameter=an["hole"], center=(z, x), note=f"под анкер {c.anchor_size}")
            )
            fasteners.append(
                Fastener(
                    id=f"anchor_{hid}",
                    fastener_type="anchor",
                    size=c.anchor_size,
                    part="base_plate",
                    hole=hid,
                    position=(x, 0.0, z),
                    axis=Y,
                    clamp_depth=tb,
                )
            )
    base = PlatePart(
        id="base_plate",
        name=f"Плита опорная δ{tb:g} {w:g}×{z_hi - z_lo:g}",
        role="base_plate",
        material=p.material,
        color=C_PLATE,
        thickness=tb,
        outline=Outline(
            points=[(z_lo, -w / 2), (z_hi, -w / 2), (z_hi, w / 2), (z_lo, w / 2)], corner_radius=bp.corner_radius
        ),
        placement=Placement(origin=(0.0, 0.0, 0.0), u=Z, normal=Y),
        holes=holes,
    )

    # интерфейс оси: предельные размеры посадки и опорное тело (вал наибольшего размера)
    bore_min, shaft_max = ctx.fit_limits(c.axle_d, c.fit_hole, c.fit_shaft)
    axle_if.params.update({"bore_min": bore_min, "shaft_max": shaft_max, "offset": c.offset})
    axle_if.body = Cylinder(
        center=(0.0, c.offset, 0.0), axis=X, diameter=shaft_max, length=mem.seat_span + 2 * c.overhang
    )

    L = req.loads
    gd = req.factors.get("gamma_dyn", 1.0)
    assumptions = [
        Assumption(
            id="G0",
            topic="loads",
            text=(
                f"Нагрузки: Fv = {L.get('Fv', 0):g} кН вниз, Fh = {L.get('Fh', 0):g} кН от стены, "
                f"Fa = {L.get('Fa', 0):g} кН; "
                f"γd = {gd:g}; требуемый запас K_треб = {req.safety_required:g}; "
                f"вылет оси {c.offset:g} мм; посадка Ø{c.axle_d:g}{c.fit_hole}/{c.fit_shaft}."
            ),
        )
    ]
    assumptions += [Assumption(id=f"T{i + 1}", topic="variant", text=s) for i, s in enumerate(mem.assumptions)]

    unit = Unit(
        id="bracket",
        name="Кронштейн",
        material=p.material,
        interfaces=["wall", "axle"],
        parts=[base, *mem.parts],
        joints=[*mem.welds, *fasteners],
        derived={
            "высота элементов у стены h, мм": c.h,
            "анкеры по X, ±мм": ax,
            "анкеры по Z, мм": f"{z0:g} / {z1:g}",
            "опорная плита, мм": f"{w:g}×{z_hi - z_lo:g}×{tb:g}",
            **mem.derived,
        },
    )
    return GenResult(units=[unit], derived={"топология": p.topology, **unit.derived}, assumptions=assumptions)
