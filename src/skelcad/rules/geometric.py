"""Встроенные проверки на геометрии: пересечения, контакт свариваемых деталей, посадка вала, доступ ключа."""

from __future__ import annotations

import build123d as bd

from skelcad.context import Context
from skelcad.core.findings import Finding
from skelcad.core.model import PlatePart, Project
from skelcad.core.vec import dot, unit
from skelcad.geom.generator import Geometry, any_perp, plane

TOL_VOL = 1.0  # мм³ — допуск на численный шум булевых операций
TOL_GAP = 0.05  # мм — касание свариваемых деталей
SOCKET_H = 100  # мм — высота цилиндра торцевой головки над гайкой

SRC = "checks.core"
F = lambda level, code, ref, msg: Finding(level=level, code=code, ref=ref, message=msg, source=SRC)


def common_volume(a: bd.Shape, b: bd.Shape) -> float:
    if not a.bounding_box().overlaps(b.bounding_box()):
        return 0.0
    r = a & b
    return sum(s.volume for s in r.solids()) if r else 0.0


def extent_along(s: bd.Shape, axis) -> tuple[float, float]:
    """Проекция габаритного бокса на ось: (min, max)."""
    bb, a = s.bounding_box(), unit(axis)
    xs = [dot((x, y, z), a) for x in (bb.min.X, bb.max.X) for y in (bb.min.Y, bb.max.Y) for z in (bb.min.Z, bb.max.Z)]
    return min(xs), max(xs)


def c_interference(m: Project, g: Geometry, ctx: Context) -> list[Finding]:
    out = []
    ids = list(g.parts)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            v = common_volume(g.parts[a], g.parts[b])
            if v > TOL_VOL:
                out.append(F("error", "C-INTERFERE", f"part:{a}+part:{b}", f"Детали пересекаются, объём {v:.0f} мм³"))
    for fid, fc in g.fasteners.items():
        for pid, ps in g.parts.items():
            v = sum(common_volume(s, ps) for s in fc.solids())
            if v > TOL_VOL:
                out.append(
                    F(
                        "error",
                        "C-INTERFERE",
                        f"fastener:{fid}+part:{pid}",
                        f"Крепёж (стержень/шайба/гайка) пересекает деталь, объём {v:.0f} мм³",
                    )
                )
    if not out:
        out.append(
            F(
                "info",
                "C-INTERFERE",
                "assembly",
                f"Пересечений нет: {len(ids)} деталей, {len(g.fasteners)} крепёжных элементов (попарно)",
            )
        )
    return out


def c_weld_contact(m: Project, g: Geometry, ctx: Context) -> list[Finding]:
    out = []
    for w in m.welds:
        a, b = (g.parts[p] for p in w.parts)
        d = a.distance_to(b)
        if d > TOL_GAP:
            out.append(
                F(
                    "error",
                    "C-WELD-CONTACT",
                    f"weld:{w.id}",
                    f"Свариваемые детали {w.parts[0]} и {w.parts[1]} не касаются, зазор {d:.2f} мм",
                )
            )
    if not out and m.welds:
        out.append(F("info", "C-WELD-CONTACT", "welds", f"Все {len(m.welds)} швов соединяют касающиеся детали"))
    return out


def c_shaft_seat(m: Project, g: Geometry, ctx: Context) -> list[Finding]:
    """Опорное тело интерфейса shaft_seat (вал наибольшего предельного размера) проходит все посадки насквозь."""
    out = []
    for i in m.skeleton.interfaces:
        if i.kind != "shaft_seat" or not i.body or i.id not in g.bodies:
            continue
        body = g.bodies[i.id]
        seats = [
            p
            for p in m.parts
            if (isinstance(p, PlatePart) and any(h.purpose == "shaft_seat" for h in p.holes))
            or getattr(p, "bore", None)
        ]
        if not seats:
            out.append(F("error", "C-SHAFT-SEAT", f"interface:{i.id}", "Нет ни одной посадки под вал"))
            continue
        b0, b1 = extent_along(body, i.body.axis)
        for p in seats:
            s = g.parts[p.id]
            v = common_volume(body, s)
            s0, s1 = extent_along(s, i.body.axis)
            gap = body.distance_to(s)
            ref = f"part:{p.id}"
            if v > TOL_VOL:
                out.append(
                    F("error", "C-SHAFT-SEAT", ref, f"Вал Ø{i.body.diameter:.3f} пересекает посадку, объём {v:.0f} мм³")
                )
            elif not (b0 <= s0 + 1e-6 and b1 >= s1 - 1e-6):
                out.append(F("error", "C-SHAFT-SEAT", ref, "Вал не проходит посадку насквозь"))
            elif gap > 0.5:
                out.append(
                    F("error", "C-SHAFT-SEAT", ref, f"Вал не касается посадки: зазор {gap:.2f} мм — несоосность")
                )
            else:
                out.append(
                    F(
                        "info",
                        "C-SHAFT-SEAT",
                        ref,
                        f"Вал Ø{i.body.diameter:.3f} входит в посадку, радиальный зазор {gap * 1000:.1f} мкм",
                    )
                )
    return out


def c_wrench(m: Project, g: Geometry, ctx: Context) -> list[Finding]:
    """Цилиндр торцевой головки над гайкой не должен задевать детали; шайба — не ближе катета шва + 1 мм."""
    out = []
    for f in m.fasteners:
        c = ctx.fastener(f.size)
        members = {k: v for k, v in g.parts.items() if k != f.part}
        if not members:
            continue
        y0 = f.clamp_depth + c["washer_s"]
        origin = tuple(f.position[i] + f.axis[i] * y0 for i in range(3))
        sock = bd.Cylinder(c["socket_od"] / 2, SOCKET_H, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)).moved(
            bd.Location(plane(origin, any_perp(f.axis), f.axis))
        )
        hits = [pid for pid, s in members.items() if common_volume(sock, s) > TOL_VOL]
        washer = g.fasteners[f.id].solids()[1]
        dmin = min(washer.distance_to(s) for s in members.values())
        legs = [w.leg for w in m.welds if f.part in w.parts]
        leg = max(legs) if legs else 0.0
        ref = f"fastener:{f.id}"
        if hits:
            out.append(F("error", "C-WRENCH", ref, f"Головка ключа Ø{c['socket_od']} задевает: {', '.join(hits)}"))
        elif dmin < leg + 1:
            out.append(
                F(
                    "warning",
                    "C-WRENCH",
                    ref,
                    f"Шайба в {dmin:.1f} мм от элемента — меньше катета шва + 1 мм ({leg + 1:g})",
                )
            )
        else:
            out.append(F("info", "C-WRENCH", ref, f"Ключ проходит; шайба в {dmin:.1f} мм от ближайшего элемента"))
    return out


def c_interface_bodies(m: Project, g: Geometry, ctx: Context) -> list[Finding]:
    """Опорные тела интерфейсов (труба, соседний узел) не проникают в детали; для shaft_seat — своя проверка."""
    out = []
    for i in m.skeleton.interfaces:
        if i.kind == "shaft_seat" or i.id not in g.bodies:
            continue
        body = g.bodies[i.id]
        bad = {pid: v for pid, s in g.parts.items() if (v := common_volume(body, s)) > TOL_VOL}
        for pid, v in bad.items():
            out.append(
                F(
                    "error",
                    "C-BODY",
                    f"interface:{i.id}+part:{pid}",
                    f"Тело интерфейса врезается в деталь, объём {v:.0f} мм³",
                )
            )
        if not bad:
            touching = [pid for pid, s in g.parts.items() if body.distance_to(s) <= TOL_GAP]
            out.append(
                F(
                    "info",
                    "C-BODY",
                    f"interface:{i.id}",
                    f"Тело интерфейса не врезается в детали; касается: {', '.join(touching) or 'ничего'}",
                )
            )
    return out


CHECKS = [c_interference, c_weld_contact, c_shaft_seat, c_interface_bodies, c_wrench]
