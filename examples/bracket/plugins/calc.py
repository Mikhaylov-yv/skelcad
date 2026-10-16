"""Оценочные расчёты кронштейна с явными формулами + метрики для сравнения вариантов.

Это не проверочный расчёт: упругая стадия, простые расчётные схемы, допущения выписаны в отчёт.
Единицы: силы в Н внутри формул (кН ×1000), напряжения в МПа (Н/мм²), длины в мм.
"""

from __future__ import annotations

import math

import build123d as bd

from skelcad.context import Context
from skelcad.core.findings import CalcItem, calc_item
from skelcad.core.model import PlatePart, Project
from skelcad.core.vec import dist_point_segment
from skelcad.geom.generator import Geometry
from skelcad.rules import Metric


def base_plate(m: Project) -> PlatePart:
    return m.parts_by_role("base_plate")[0]


def at_base(m: Project):
    return [w for w in m.welds if "at_base" in w.tags]


def wall_section(m: Project, g: Geometry, dy: float = 1.0) -> dict:
    """Сечение несущих элементов у опорной плиты (срез слоем dy мм сразу над плитой)."""
    tb = base_plate(m).thickness
    slab = bd.Box(2000, dy, 2000).moved(bd.Location((0, tb + 0.5 + dy / 2, 0)))
    pieces = []
    for pid, s in g.parts.items():
        if pid == "base_plate":
            continue
        r = s & slab
        pieces += r.solids() if r else []
    A = sum(p.volume for p in pieces) / dy
    zc = sum(p.volume * p.center().Z for p in pieces) / (A * dy)
    I = sum(p.matrix_of_inertia[0][0] + p.volume * (p.center().Z - zc) ** 2 for p in pieces) / dy  # noqa: E741
    zmax = max(max(abs(p.bounding_box().max.Z - zc), abs(p.bounding_box().min.Z - zc)) for p in pieces)
    return {"A": A, "I": I, "zc": zc, "zmax": zmax, "W": I / zmax}


def calc_bracket(m: Project, g: Geometry, ctx: Context) -> list[CalcItem]:
    req = m.requirements
    mat = ctx.material(m.units[0].material or base_plate(m).material)
    Ry, Run = mat["Ry"], mat["Run"]
    gd, kreq = req.factors.get("gamma_dyn", 1.0), req.safety_required
    Fv, Fh = gd * req.loads.get("Fv", 0) * 1e3, gd * req.loads.get("Fh", 0) * 1e3  # Н, расчётные
    axle = m.skeleton.interface("axle")
    offset = float(axle.params["offset"])
    d = float(axle.params["d"])
    bp = base_plate(m)
    tb = bp.thickness
    lever = offset - tb  # плечо от лица плиты до оси
    items: list[CalcItem] = []

    # 1. Изгиб несущих элементов у плиты
    sec = wall_section(m, g)
    M = Fv * lever
    sigma = M / sec["W"] + Fh / sec["A"]
    tau = Fv / sec["A"]
    s_eq = math.sqrt(sigma**2 + 3 * tau**2)
    items.append(
        calc_item(
            "bend_wall",
            "Изгиб консоли в сечении у плиты",
            "σ = γd·Fv·(e − tb)/W + γd·Fh/A;  τ = γd·Fv/A;  σэкв = √(σ² + 3τ²) ≤ Ry/K",
            {"M, Н·мм": M, "W, мм³": sec["W"], "A, мм²": sec["A"], "I, мм⁴": sec["I"], "σ, МПа": sigma, "τ, МПа": tau},
            s_eq,
            Ry,
            "МПа",
            kreq,
            "section:wall",
        )
    )

    # 2. Смятие в посадке оси и срез кольца проушины
    seats = []
    for p in m.parts:
        if isinstance(p, PlatePart):
            seats += [(p, p.thickness, h) for h in p.holes if h.purpose == "shaft_seat"]
        elif p.bore:
            seats.append((p, p.length, p.bore))
    F_res = math.hypot(Fv, Fh)
    t_sum = sum(t for _, t, _ in seats)
    items.append(
        calc_item(
            "bearing",
            "Смятие в посадке оси",
            "σсм = γd·√(Fv² + Fh²)/(d·Σt) ≤ Ry/K",
            {"Σt, мм": t_sum, "d, мм": d},
            F_res / (d * t_sum),
            Ry,
            "МПа",
            kreq,
            "interface:axle",
        )
    )
    lugs = [(p, h) for p, _, h in seats if isinstance(p, PlatePart) and p.outline.circles]
    if lugs:
        ring = min(r - h.diameter / 2 for p, h in lugs for *_, r in p.outline.circles)
        t_l = sum(p.thickness for p, _ in lugs)
        tau_l = F_res / (2 * t_l * ring)
        items.append(
            calc_item(
                "lug_shear",
                "Срез кольца проушины",
                "τ = γd·√(Fv² + Fh²)/(2·Σt·(R − d/2)) ≤ 0,58·Ry/K",
                {"Σt, мм": t_l, "R − d/2, мм": ring},
                tau_l,
                0.58 * Ry,
                "МПа",
                kreq,
                "part:cheek",
            )
        )

    # 3. Анкеры: отрыв от момента (поворот вокруг нижней кромки плиты) + Fh, срез Fv
    us = [q[0] for q in bp.outline.points]
    z_pivot = min(us) + 0.1 * (max(us) - min(us))  # центр сжатия: 0,1·H от нижней кромки
    fs = m.fasteners
    n = len(fs)
    zs = [f.position[2] - z_pivot for f in fs]
    Mw = Fv * offset
    N_max = Fh / n + Mw * max(zs) / sum(z * z for z in zs if z > 0)
    V = Fv / n
    a_cat = ctx.anchor(fs[0].size)
    f_cat = ctx.fastener(fs[0].size)
    N_rd, V_rd = a_cat["N_Rd"] * 1e3, a_cat["V_Rd"] * 1e3
    items.append(
        calc_item(
            "anchor_N",
            "Анкер: отрыв по бетону (верхний ряд)",
            "N = γd·Fh/n + γd·Fv·e·z_i/Σz_j² (поворот вокруг точки 0,1·H от низа плиты) ≤ N_Rd/K",
            {"n": n, "z_max, мм": max(zs), "e, мм": offset, "N_Rd, кН": a_cat["N_Rd"]},
            N_max / 1e3,
            N_rd / 1e3,
            "кН",
            kreq,
            "fasteners",
        )
    )
    N_rs = a_cat["Rbt"] * f_cat["As"]
    items.append(
        calc_item(
            "anchor_steel",
            "Анкер: растяжение шпильки",
            "N ≤ Rbt·As/K",
            {"As, мм²": f_cat["As"], "Rbt, МПа": a_cat["Rbt"]},
            N_max / 1e3,
            N_rs / 1e3,
            "кН",
            kreq,
            "fasteners",
        )
    )
    inter = (N_max / N_rd) ** 1.5 + (V / V_rd) ** 1.5
    items.append(
        calc_item(
            "anchor_NV",
            "Анкер: совместное действие N и V",
            "(N/N_Rd)^1,5 + (V/V_Rd)^1,5 ≤ 1; запас K = 1/η^(1/1,5)",
            {"N, кН": N_max / 1e3, "V, кН": V / 1e3, "η": inter},
            inter ** (1 / 1.5),
            1.0,
            "—",
            kreq,
            "fasteners",
        )
    )

    # 4. Опорная плита: изгиб консоли от анкера до ближайшего шва
    top = max(fs, key=lambda f: f.position[2])
    p2 = (top.position[0], top.position[2])
    c = min(
        dist_point_segment(p2, (s.start[0], s.start[2]), (s.end[0], s.end[2])) for w in at_base(m) for s in w.segments
    )
    e_edge = min(abs(top.position[2] - u) for u in us)
    b_eff = c + min(c, e_edge)
    sig_p = 6 * N_max * c / (b_eff * tb**2)
    items.append(
        calc_item(
            "plate_bend",
            "Опорная плита: изгиб у анкера",
            "σ = 6·N·c/(b_eff·t²), b_eff = c + min(c, e) ≤ Ry/K",
            {"c, мм": c, "e до кромки, мм": e_edge, "b_eff, мм": b_eff, "t, мм": tb},
            sig_p,
            Ry,
            "МПа",
            kreq,
            "part:base_plate",
        )
    )

    # 5. Группа швов у плиты: по металлу шва (βf) и по границе сплавления (βz)
    wc = ctx.welds()
    Rwf, Rwz = wc["Rwf"], 0.45 * Run
    segs = [(s, w.leg) for w in at_base(m) for s in w.segments]

    def group(beta):
        A = sum(beta * k * s.length for s, k in segs)
        zc = sum(beta * k * s.length * (s.start[2] + s.end[2]) / 2 for s, k in segs) / A
        I = sum(  # noqa: E741
            beta * k * s.length * ((s.end[2] - s.start[2]) ** 2 / 12 + ((s.start[2] + s.end[2]) / 2 - zc) ** 2)
            for s, k in segs
        )
        zmax = max(max(abs(s.start[2] - zc), abs(s.end[2] - zc)) for s, _ in segs)
        tau = math.hypot(M * zmax / I + Fh / A, Fv / A)
        return A, I, tau

    Af, If, tf = group(wc["beta_f"])
    Az, Iz, tz = group(wc["beta_z"])
    k_wall = max(k for _, k in segs)
    K_f, K_z = Rwf / tf, Rwz / tz
    gov = ("металлу шва", tf, Rwf) if K_f < K_z else ("границе сплавления", tz, Rwz)
    item = calc_item(
        "weld_wall",
        f"Швы к плите (по {gov[0]})",
        "τ = √((M·z/Iw + γd·Fh/Aw)² + (γd·Fv/Aw)²), Aw = Σβ·k·l ≤ R/K; Rwf, Rwz = 0,45·Run",
        {
            "Σl, мм": sum(s.length for s, _ in segs),
            "k, мм": k_wall,
            "Aw(βf), мм²": Af,
            "Iw(βf), мм⁴": If,
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
    item.values["k_треб, мм"] = round(k_wall * kreq / item.K, 1)
    items.append(item)
    return items


def metrics_bracket(m: Project, g: Geometry, items: list[CalcItem], ctx: Context) -> list[Metric]:
    fs = m.fasteners
    return [Metric(id="anchors", title="Число анкеров", value=f"{len(fs)} × {fs[0].size}" if fs else "—")]


CALCS = [calc_bracket]
METRICS = [metrics_bracket]
