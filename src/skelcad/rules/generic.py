"""Встроенные правила над моделью, не зависящие от конкретного стандарта.

Таблицы (материалы, крепёж) берутся из контекста; если нужной таблицы нет, правило пропускается
с предупреждением MISSING-STD (см. runner в skelcad.rules).
"""

from __future__ import annotations

import math

from skelcad.context import Context
from skelcad.core.findings import Finding
from skelcad.core.model import PlatePart, Project
from skelcad.core.vec import dist_point_segment_perp

SRC = "rules.core"
F = lambda level, code, ref, msg: Finding(level=level, code=code, ref=ref, message=msg, source=SRC)


def r_bore_wall(m: Project, ctx: Context) -> list[Finding]:
    """Стенка вокруг посадки вала: пластина — кольцо R − d/2; труба — (Dн − d)/2."""
    out = []
    for p in m.parts:
        if isinstance(p, PlatePart):
            for h in p.holes:
                if h.purpose != "shaft_seat":
                    continue
                rings = [
                    r - h.diameter / 2
                    for cu, cv, r in p.outline.circles
                    if math.isclose(cu, h.center[0]) and math.isclose(cv, h.center[1])
                ]
                if not rings:
                    continue
                wall, d = rings[0], h.diameter
                ref = f"part:{p.id}/hole:{h.id}"
                if wall < 0.25 * d:
                    out.append(F("error", "R-BORE-WALL", ref, f"Кольцо проушины {wall:g} мм < 0,25·d"))
                elif wall < 0.4 * d:
                    out.append(F("warning", "R-BORE-WALL", ref, f"Кольцо проушины {wall:g} мм < 0,4·d = {0.4 * d:g}"))
                else:
                    out.append(F("info", "R-BORE-WALL", ref, f"Кольцо проушины {wall:g} мм (≥ 0,4·d)"))
        elif p.bore:
            wall = (p.od - p.bore.diameter) / 2
            lim = max(0.2 * p.bore.diameter, 8)
            lvl = "warning" if wall < lim else "info"
            out.append(
                F(
                    lvl,
                    "R-BORE-WALL",
                    f"part:{p.id}/bore",
                    f"Стенка после расточки {wall:g} мм, рекомендуется ≥ {lim:g} мм",
                )
            )
    return out


def r_free_edge(m: Project, ctx: Context) -> list[Finding]:
    """Местная устойчивость свободной кромки ребра/щеки: L/t ≤ 0,75·√(E/Ry) (оценка, AISC Design Guide)."""
    out = []
    for p in m.parts:
        if not isinstance(p, PlatePart) or not p.free_edges:
            continue
        mat = ctx.material(p.material)
        lim = 0.75 * math.sqrt(mat["E"] / mat["Ry"])
        for name, length in p.free_edges.items():
            ratio = length / p.thickness
            lvl = "warning" if ratio > lim else "info"
            out.append(
                F(
                    lvl,
                    "R-FREE-EDGE",
                    f"part:{p.id}",
                    f"Свободная {name} кромка {length:.0f} мм, L/t = {ratio:.1f} (предел {lim:.1f})",
                )
            )
    return out


def r_fit(m: Project, ctx: Context) -> list[Finding]:
    """Посадка вала в интерфейсе shaft_seat: минимальный зазор по предельным размерам."""
    out = []
    for i in m.skeleton.interfaces:
        p = i.params
        if i.kind != "shaft_seat" or "bore_min" not in p or "shaft_max" not in p:
            continue
        gap = 1000 * (float(p["bore_min"]) - float(p["shaft_max"]))
        out.append(
            F(
                "info",
                "R-FIT",
                f"interface:{i.id}",
                f"Посадка Ø{p.get('d')}{p.get('fit_hole', '')}/{p.get('fit_shaft', '')}: "
                f"минимальный зазор {gap:.0f} мкм; посадочные поверхности обрабатываются после сварки",
            )
        )
    return out


def r_wrench(m: Project, ctx: Context) -> list[Finding]:
    """Доступ торцевым ключом: от оси крепежа до ближайшего шва на его детали (с учётом катета) ≥ R головки."""
    out = []
    for f in m.fasteners:
        r_sock = ctx.fastener(f.size)["socket_od"] / 2
        segs = [(s, w.leg) for w in m.welds if f.part in w.parts for s in w.segments]
        if not segs:
            continue
        clear = min(dist_point_segment_perp(f.position, s.start, s.end, f.axis) - leg for s, leg in segs)
        lvl = "error" if clear < r_sock else "info"
        out.append(
            F(
                lvl,
                "R-WRENCH",
                f"fastener:{f.id}",
                f"Свободно от оси крепежа до шва {clear:.1f} мм, нужно ≥ {r_sock:g} мм (головка Ø{2 * r_sock:g})",
            )
        )
    return out


RULES = [r_bore_wall, r_free_edge, r_fit, r_wrench]
