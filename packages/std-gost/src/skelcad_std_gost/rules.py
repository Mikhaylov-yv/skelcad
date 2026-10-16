"""Правила пакета ГОСТ/СП над проектной моделью SkelCAD (без геометрии)."""

from __future__ import annotations

import math

from skelcad.context import Context
from skelcad.core.findings import Finding
from skelcad.core.model import PlatePart, Project, TubePart

SRC = "rules.gost"
F = lambda level, code, ref, msg: Finding(level=level, code=code, ref=ref, message=msg, source=SRC)


def _thickness(part) -> float:
    return part.thickness if isinstance(part, PlatePart) else part.wall


def r_sheet(m: Project, ctx: Context) -> list[Finding]:
    """Толщины листа из ряда ГОСТ 19903."""
    std = ctx.table("sheet")
    return [
        F("error", "R-SHEET", f"part:{p.id}", f"Толщина {p.thickness:g} мм отсутствует в ряду {std['standard']}")
        for p in m.parts
        if isinstance(p, PlatePart) and p.thickness not in std["thicknesses"]
    ]


def r_tube(m: Project, ctx: Context) -> list[Finding]:
    """Трубы — из сортамента ГОСТ 8732; расточка возможна (припуск ≥ 1 мм на сторону)."""
    out = []
    t = ctx.table("tubes")
    for p in m.parts:
        if not isinstance(p, TubePart):
            continue
        if p.tube_size not in t["sizes"]:
            out.append(F("error", "R-TUBE", f"part:{p.id}", f"Трубы {p.tube_size} нет в сортаменте {t['standard']}"))
            continue
        if p.bore:
            inner = p.od - 2 * p.wall
            allowance = (p.bore.diameter - inner) / 2
            if allowance < 0:
                out.append(
                    F(
                        "error",
                        "R-TUBE",
                        f"part:{p.id}/bore",
                        f"Внутренний Ø трубы {inner:g} больше расточки Ø{p.bore.diameter:g}",
                    )
                )
            elif allowance < 1:
                out.append(
                    F(
                        "warning",
                        "R-TUBE",
                        f"part:{p.id}/bore",
                        f"Припуск на расточку {allowance:.1f} мм на сторону < 1 мм",
                    )
                )
            else:
                out.append(
                    F(
                        "info",
                        "R-TUBE",
                        f"part:{p.id}/bore",
                        f"Труба Ø{p.od:g}×{p.wall:g} (внутр. Ø{inner:g}) растачивается до Ø{p.bore.diameter:g}"
                        f"{p.bore.tolerance or ''}, припуск {allowance:.1f} мм на сторону",
                    )
                )
    return out


def _plate_rect(p: PlatePart) -> tuple[float, float, float, float]:
    us = [q[0] for q in p.outline.points]
    vs = [q[1] for q in p.outline.points]
    return min(us), max(us), min(vs), max(vs)


def r_anchor_edges(m: Project, ctx: Context) -> list[Finding]:
    """СП 16.13330, табл. 40: от центра отверстия до кромки ≥ 1,5·d0 (поперёк усилия), ≥ 2·d0 (вдоль);
    между центрами ≥ 2,5·d0; для анкеров дополнительно s ≥ s_min производителя."""
    out = []
    for p in m.parts:
        if not isinstance(p, PlatePart):
            continue
        anchors = [h for h in p.holes if h.purpose == "anchor"]
        if not anchors:
            continue
        u0, u1, v0, v1 = _plate_rect(p)
        for h in anchors:
            d0 = h.diameter
            e = min(h.center[0] - u0, u1 - h.center[0], h.center[1] - v0, v1 - h.center[1])
            ref = f"part:{p.id}/hole:{h.id}"
            if e < 1.5 * d0:
                out.append(F("error", "R-EDGE", ref, f"До кромки {e:.0f} мм < 1,5·d0 = {1.5 * d0:.0f} мм"))
            elif e < 2 * d0:
                out.append(F("warning", "R-EDGE", ref, f"До кромки {e:.0f} мм < 2·d0 = {2 * d0:.0f} мм (вдоль усилия)"))
        if len(anchors) > 1:
            fs = [f for f in m.fasteners if f.part == p.id]
            s_min = 2.5 * anchors[0].diameter
            if fs:
                s_min = max(s_min, ctx.anchor(fs[0].size)["s_min"])
            s = min(math.dist(a.center, b.center) for i, a in enumerate(anchors) for b in anchors[i + 1 :])
            lvl = "error" if s < s_min else "info"
            out.append(
                F(
                    lvl,
                    "R-SPACING",
                    f"part:{p.id}",
                    f"Минимальный шаг анкеров {s:.0f} мм, требуется ≥ {s_min:.0f} мм (2,5·d0 и s_min анкера)",
                )
            )
    return out


def r_weld_legs(m: Project, ctx: Context) -> list[Finding]:
    """СП 16.13330, табл. 38 и п. 14.1.7: k_min по более толстому элементу, k ≤ 1,2·t_min."""
    wc = ctx.welds()
    out = []
    for w in m.welds:
        ts = [_thickness(m.part(pid)) for pid in w.parts]
        kmin, kmax = ctx.k_min(max(ts)), wc["k_max_factor"] * min(ts)
        ref = f"weld:{w.id}"
        if w.leg < kmin:
            out.append(F("error", "R-WELD-LEG", ref, f"Катет {w.leg:g} < k_min = {kmin:g} мм (t_max = {max(ts):g})"))
        elif w.leg > kmax:
            out.append(F("error", "R-WELD-LEG", ref, f"Катет {w.leg:g} > 1,2·t_min = {kmax:g} мм"))
    return out


def r_weld_access(m: Project, ctx: Context) -> list[Finding]:
    """Доступ горелки (механизированная сварка): ширина щели ≥ access_gap_min, глубина/ширина ≤ предела."""
    wc = ctx.welds()
    out = []
    for w in m.welds:
        if w.access_gap is None:
            continue
        ref = f"weld:{w.id}"
        if w.access_gap < wc["access_gap_min"]:
            out.append(
                F(
                    "error",
                    "R-WELD-ACCESS",
                    ref,
                    f"Щель {w.access_gap:g} мм < {wc['access_gap_min']} мм — горелка не проходит",
                )
            )
        elif w.access_depth and w.access_depth / w.access_gap > wc["access_depth_ratio_max"]:
            out.append(
                F(
                    "warning",
                    "R-WELD-ACCESS",
                    ref,
                    f"Шов на дне щели {w.access_gap:g}×{w.access_depth:.0f} мм (глубина/ширина "
                    f"{w.access_depth / w.access_gap:.1f} > {wc['access_depth_ratio_max']}): нужен удлинённый "
                    "наконечник или варить до установки второго элемента",
                )
            )
    return out


RULES = [r_sheet, r_tube, r_anchor_edges, r_weld_legs, r_weld_access]
