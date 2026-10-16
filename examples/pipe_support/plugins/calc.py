"""Оценочные расчёты опоры под трубопровод и метрики для сравнения вариантов.

Упругая стадия, простые схемы; все силы в Н внутри формул, напряжения в МПа, длины в мм.
"""

from __future__ import annotations

import math

import build123d as bd

from skelcad.context import Context
from skelcad.core.findings import CalcItem, calc_item
from skelcad.core.model import PlatePart, Project
from skelcad.geom.generator import Geometry
from skelcad.rules import Metric


def base_plate(m: Project) -> PlatePart:
    return m.parts_by_role("base_plate")[0]


def post_section(m: Project, g: Geometry, dz: float = 1.0) -> dict:
    """Сечение стойки сразу над опорной плитой: площадь и моменты инерции относительно X и Y."""
    z0 = base_plate(m).thickness + 0.5
    slab = bd.Box(2000, 2000, dz).moved(bd.Location((0, 0, z0 + dz / 2)))
    pieces = []
    for p in m.parts_by_role("post"):
        r = g.parts[p.id] & slab
        pieces += r.solids() if r else []
    A = sum(p.volume for p in pieces) / dz
    xc = sum(p.volume * p.center().X for p in pieces) / (A * dz)
    yc = sum(p.volume * p.center().Y for p in pieces) / (A * dz)
    Ix = sum(p.matrix_of_inertia[0][0] + p.volume * (p.center().Y - yc) ** 2 for p in pieces) / dz
    Iy = sum(p.matrix_of_inertia[1][1] + p.volume * (p.center().X - xc) ** 2 for p in pieces) / dz
    ymax = max(max(abs(p.bounding_box().max.Y - yc), abs(p.bounding_box().min.Y - yc)) for p in pieces)
    xmax = max(max(abs(p.bounding_box().max.X - xc), abs(p.bounding_box().min.X - xc)) for p in pieces)
    return {"A": A, "Ix": Ix, "Iy": Iy, "xmax": xmax, "ymax": ymax}


def calc_support(m: Project, g: Geometry, ctx: Context) -> list[CalcItem]:
    req = m.requirements
    mat = ctx.material(m.units[0].material or base_plate(m).material)
    Ry, Run = mat["Ry"], mat["Run"]
    gd, kreq = req.factors.get("gamma_dyn", 1.0), req.safety_required
    Fv, Fx, Fy = (gd * req.loads.get(k, 0) * 1e3 for k in ("Fv", "Fx", "Fy"))
    pipe = m.skeleton.interface("pipe")
    z_rest, H = float(pipe.params["z_rest"]), float(pipe.params["height"])
    bp = base_plate(m)
    tb = bp.thickness
    items: list[CalcItem] = []

    # 1. Стойка: сжатие + изгиб в двух плоскостях в сечении у опорной плиты
    sec = post_section(m, g)
    My = Fx * (z_rest - tb)  # трение вдоль X приложено на уровне опирания трубы -> момент вокруг Y
    Mx = Fy * (H - tb)  # боковая сила через направляющую на уровне оси трубы -> момент вокруг X
    sigma = Fv / sec["A"] + Mx * sec["ymax"] / sec["Ix"] + My * sec["xmax"] / sec["Iy"]
    tau = math.hypot(Fx, Fy) / sec["A"]
    items.append(
        calc_item(
            "post",
            "Стойка: сжатие с изгибом у опорной плиты",
            "σ = γd·Fv/A + Mx·y/Ix + My·x/Iy;  τ = γd·√(Fx²+Fy²)/A;  σэкв = √(σ² + 3τ²) ≤ Ry/K",
            {
                "A, мм²": sec["A"],
                "Ix, мм⁴": sec["Ix"],
                "Iy, мм⁴": sec["Iy"],
                "Mx, Н·мм": Mx,
                "My, Н·мм": My,
                "σ, МПа": sigma,
                "τ, МПа": tau,
            },
            math.sqrt(sigma**2 + 3 * tau**2),
            Ry,
            "МПа",
            kreq,
            "section:post",
        )
    )

    # 2. Анкеры: отрыв от опрокидывания в двух плоскостях (поворот вокруг точки 0,1·L от кромки) + срез
    fs = m.fasteners
    n = len(fs)
    xs_all = [q[0] for q in bp.outline.points]
    ys_all = [q[1] for q in bp.outline.points]
    px = min(xs_all) + 0.1 * (max(xs_all) - min(xs_all))
    py = min(ys_all) + 0.1 * (max(ys_all) - min(ys_all))
    xs = [f.position[0] - px for f in fs]
    ys = [f.position[1] - py for f in fs]
    N = My * max(xs) / sum(x * x for x in xs if x > 0) + Mx * max(ys) / sum(y * y for y in ys if y > 0)
    V = math.hypot(Fx, Fy) / n
    a_cat, f_cat = ctx.anchor(fs[0].size), ctx.fastener(fs[0].size)
    N_rd, V_rd = a_cat["N_Rd"] * 1e3, a_cat["V_Rd"] * 1e3
    items.append(
        calc_item(
            "anchor_N",
            "Анкер: отрыв по бетону (угловой анкер)",
            "N = My·x_i/Σx_j² + Mx·y_i/Σy_j² (поворот вокруг точки 0,1·L от кромки; "
            "сжатие Fv в запас не учтено) ≤ N_Rd/K",
            {"n": n, "x_max, мм": max(xs), "y_max, мм": max(ys), "N_Rd, кН": a_cat["N_Rd"]},
            N / 1e3,
            N_rd / 1e3,
            "кН",
            kreq,
            "fasteners",
        )
    )
    items.append(
        calc_item(
            "anchor_steel",
            "Анкер: растяжение шпильки",
            "N ≤ Rbt·As/K",
            {"As, мм²": f_cat["As"], "Rbt, МПа": a_cat["Rbt"]},
            N / 1e3,
            a_cat["Rbt"] * f_cat["As"] / 1e3,
            "кН",
            kreq,
            "fasteners",
        )
    )
    inter = (N / N_rd) ** 1.5 + (V / V_rd) ** 1.5
    items.append(
        calc_item(
            "anchor_NV",
            "Анкер: совместное действие N и V",
            "(N/N_Rd)^1,5 + (V/V_Rd)^1,5 ≤ 1; K = 1/η^(1/1,5)",
            {"N, кН": N / 1e3, "V, кН": V / 1e3, "η": inter},
            inter ** (1 / 1.5),
            1.0,
            "—",
            kreq,
            "fasteners",
        )
    )

    # 3. Швы стойки к опорной плите: группа швов в плане, изгиб в двух плоскостях + сжатие + срез
    wc = ctx.welds()
    Rwf, Rwz = wc["Rwf"], 0.45 * Run
    segs = [(s, w.leg) for w in m.welds if "at_base" in w.tags for s in w.segments]

    def group(beta):
        A = sum(beta * k * s.length for s, k in segs)
        xc = sum(beta * k * s.length * (s.start[0] + s.end[0]) / 2 for s, k in segs) / A
        yc = sum(beta * k * s.length * (s.start[1] + s.end[1]) / 2 for s, k in segs) / A
        Ix = sum(
            beta * k * s.length * ((s.end[1] - s.start[1]) ** 2 / 12 + ((s.start[1] + s.end[1]) / 2 - yc) ** 2)
            for s, k in segs
        )
        Iy = sum(
            beta * k * s.length * ((s.end[0] - s.start[0]) ** 2 / 12 + ((s.start[0] + s.end[0]) / 2 - xc) ** 2)
            for s, k in segs
        )
        ymax = max(max(abs(s.start[1] - yc), abs(s.end[1] - yc)) for s, _ in segs)
        xmax = max(max(abs(s.start[0] - xc), abs(s.end[0] - xc)) for s, _ in segs)
        return A, math.hypot(Mx * ymax / Ix + My * xmax / Iy + Fv / A, math.hypot(Fx, Fy) / A)

    Af, tf = group(wc["beta_f"])
    Az, tz = group(wc["beta_z"])
    gov = ("металлу шва", tf, Rwf) if Rwf / tf < Rwz / tz else ("границе сплавления", tz, Rwz)
    items.append(
        calc_item(
            "weld_base",
            f"Швы стойки к плите (по {gov[0]})",
            "τ = √((Mx·y/Ix + My·x/Iy + γd·Fv/Aw)² + (γd·√(Fx²+Fy²)/Aw)²), Aw = Σβ·k·l ≤ R/K",
            {
                "Σl, мм": sum(s.length for s, _ in segs),
                "Aw(βf), мм²": Af,
                "τ_f, МПа": tf,
                "τ_z, МПа": tz,
                "Rwf, МПа": Rwf,
                "Rwz, МПа": Rwz,
            },
            gov[1],
            gov[2],
            "МПа",
            kreq,
            "welds:at_base",
        )
    )

    # 4. Направляющая: изгиб консоли от боковой силы на уровне оси трубы
    guide = m.parts_by_role("guide")[0]
    lever = min(H - z_rest, max(abs(v) for _, v in guide.outline.points))
    length = max(u for u, _ in guide.outline.points) - min(u for u, _ in guide.outline.points)
    W = length * guide.thickness**2 / 6
    items.append(
        calc_item(
            "guide_bend",
            "Направляющая: изгиб у верхней плиты",
            "σ = γd·Fy·h/W, W = l·t²/6 ≤ Ry/K",
            {"h, мм": lever, "l, мм": length, "t, мм": guide.thickness, "W, мм³": W},
            Fy * lever / W,
            Ry,
            "МПа",
            kreq,
            f"part:{guide.id}",
        )
    )
    return items


def metrics_support(m: Project, g: Geometry, items: list[CalcItem], ctx: Context) -> list[Metric]:
    fs = m.fasteners
    return [
        Metric(id="anchors", title="Число анкеров", value=f"{len(fs)} × {fs[0].size}" if fs else "—"),
        Metric(id="post_height", title="Высота стойки, мм", value=m.derived.get("высота стойки, мм", "—")),
    ]


CALCS = [calc_support]
METRICS = [metrics_support]
