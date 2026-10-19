"""Эскиз варианта с размерами по модели (M2.1, D18): HLR-проекции деталей на фоне компоновки, размеры
строятся из модели и привязаны к сущностям (деталь, отверстие, крепёж, труба), а не снимаются с геометрии.

Правила размеров по умолчанию (на каждом виде):
  сборка — габарит по двум осям вида; плита в лицо — габарит контура, кромка и шаги отверстий цепочкой,
  выноска диаметров группами («4 отв. Ø8,5 (резьба M10-6H)»), скругление R; плита с ребра — толщина;
  труба с торца — «Ø76×6», сбоку — длина и сечение; крепёж в лицо — шаги и выноска «4 × M16»;
  положения осей скелета относительно плоскостей — как на компоновке.
Раздел `sketch` проекта или варианта: `views`, `hide` (id автоматических размеров), `dims` (явные).
Файлы: <v>_sketch_<view>.svg (+ .png) и <v>_sketch.json; группы с data-ref — для подсветки в рабочем месте.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from skelcad.core.model import Fastener, PlatePart, Project, SketchDim, TubePart, Vec3, axis_index, text
from skelcad.geom.layout import (
    AXES,
    VIEWS,
    Sheet,
    _num,
    auto_dims,
    draw_datum,
    draw_envelope,
    draw_interface,
    draw_surrounding,
    hlr_inner,
    project_box,
    to_view,
)

MAX_DIMS = 16
TYPE_RU = {"anchor": "анкеры", "bolt": "болты"}


# ---------------------------------------------------------------- точки модели по ссылкам


def point_of(m: Project, g, ref: str) -> Vec3 | None:
    """Точка модели по ссылке: datum:<id>, interface:<id>, surrounding:<id>, envelope:<id>, part:<id>,
    part:<id>/hole:<hid>, part:<id>/bore, fastener:<id>, weld:<id>, point:x,y,z."""
    kind, _, rest = ref.partition(":")
    if kind == "point":
        try:
            x, y, z = (float(v) for v in rest.split(","))
            return (x, y, z)
        except ValueError:
            return None
    if kind == "datum":
        d = m.skeleton.datum(rest)
        return d.origin if d else None
    if kind == "interface":
        i = next((i for i in m.skeleton.interfaces if i.id == rest), None)
        if i is None:
            return None
        if i.body:
            return i.body.center
        d = m.skeleton.datum(i.datum) if i.datum else None
        return d.origin if d else None
    if kind in ("surrounding", "envelope"):
        items = m.skeleton.surroundings if kind == "surrounding" else m.skeleton.envelopes
        e = next((e for e in items if e.id == rest), None)
        if e is None:
            return None
        lo, hi = e.bbox() if kind == "surrounding" else (e.min, e.max)
        return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
    if kind == "fastener":
        f = next((f for f in m.fasteners if f.id == rest), None)
        return f.position if f else None
    if kind == "weld":
        w = next((w for w in m.welds if w.id == rest), None)
        return w.segments[0].start if w and w.segments else None
    if kind == "part":
        pid, _, sub = rest.partition("/")
        p = next((p for p in m.parts if p.id == pid), None)
        if p is None:
            return None
        if isinstance(p, TubePart):
            return p.center
        if sub.startswith("hole:"):
            h = next((h for h in p.holes if h.id == sub[5:]), None)
            return p.placement.to_global(h.center) if h else None
        return p.placement.origin
    return None


def _bbox(shape) -> tuple[Vec3, Vec3]:
    bb = shape.bounding_box()
    return (bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z)


def _with(pt: Vec3, k: int, value: float) -> Vec3:
    out = list(pt)
    out[k] = value
    return (out[0], out[1], out[2])


# ---------------------------------------------------------------- правила размеров


class Dims:
    """Накопитель размеров одного вида: линейные (с ярусом) и выноски; дубликаты по оси и координатам
    не повторяются; скрытые по `sketch.hide` не рисуются."""

    def __init__(self, view: str, hide: set[str]):
        self.view = view
        self.hide = hide
        self.seen: set[tuple] = set()
        self.linear: list[dict] = []
        self.callouts: list[dict] = []

    def add(self, dim_id: str, p1: Vec3, k: int, coord: float, refs: list[str], level: int, text_: str | None = None):
        value = abs(coord - p1[k])
        key = (k, round(min(p1[k], coord), 2), round(max(p1[k], coord), 2))
        if value < 0.5 or key in self.seen or dim_id in self.hide:
            return
        self.seen.add(key)
        self.linear.append(
            {
                "id": dim_id,
                "p1": p1,
                "p2": _with(p1, k, coord),
                "axis": AXES[k],
                "k": k,
                "value": value,
                "text": text_ or _num(value),
                "refs": refs,
                "level": level,
            }
        )

    def callout(self, dim_id: str, at: Vec3, label: str, ref: str, side=(1.0, 1.0)):
        if dim_id in self.hide or any(c["id"] == dim_id for c in self.callouts):
            return
        self.callouts.append({"id": dim_id, "at": at, "text": label, "ref": ref, "side": side})


def plate_dims(d: Dims, p: PlatePart, lo: Vec3, hi: Vec3, ua: int, va: int, depth: int) -> None:
    n_ax = axis_index(p.placement.normal)
    ref = f"part:{p.id}"
    if n_ax == depth:  # в лицо: контур, отверстия, скругление
        for k in (ua, va):
            d.add(f"{p.id}.size_{AXES[k]}", lo, k, hi[k], [ref], 1)
        holes = [(h, p.placement.to_global(h.center)) for h in p.holes]
        for k in (ua, va):
            coords = sorted({round(c[k], 3) for _, c in holes})
            if len(coords) < 2:
                continue  # одиночное отверстие (расточка) привязано размерами скелета
            first = next(c for _, c in holes if round(c[k], 3) == coords[0])
            d.add(f"{p.id}.holes.edge_{AXES[k]}", first, k, lo[k], [ref], 0)
            for i in range(len(coords) - 1):
                a = next((h, c) for h, c in holes if round(c[k], 3) == coords[i])
                d.add(
                    f"{p.id}.holes.pitch_{AXES[k]}_{i + 1}",
                    a[1],
                    k,
                    coords[i + 1],
                    [f"{ref}/hole:{a[0].id}"],
                    0,
                )
        groups: dict[tuple, list] = {}
        for h, c in holes:
            groups.setdefault((round(h.diameter, 2), h.purpose, h.note.split(",")[0].strip()), []).append((h, c))
        for (dia, _purpose, note), items in groups.items():
            h0, c0 = items[0]
            label = f"{len(items)} отв. Ø{_num(dia)}" if len(items) > 1 else f"Ø{_num(dia)}"
            if h0.tolerance:
                label += h0.tolerance
            if note:
                label += f" ({note})"
            d.callout(f"{p.id}.holes.d{_num(dia).replace('.', '_')}", c0, label, f"{ref}/hole:{h0.id}")
        if p.outline.corner_radius > 0 and p.outline.points:
            corner = p.placement.to_global(p.outline.points[0])
            d.callout(f"{p.id}.corner_radius", corner, f"R{_num(p.outline.corner_radius)}", ref, (-1.0, -1.0))
    elif n_ax in (ua, va):  # с ребра: толщина выноской «s10» (ЕСКД 2.307) у середины детали
        mid = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
        d.callout(f"{p.id}.thickness", mid, f"s{_num(p.thickness)}", ref, (1.0, 1.0) if n_ax == va else (1.0, -1.0))


def tube_dims(d: Dims, t: TubePart, ua: int, va: int, depth: int) -> None:
    ax = axis_index(t.axis)
    ref = f"part:{t.id}"
    label = f"Ø{_num(t.od)}×{_num(t.wall)}"
    r = t.od / 2
    if ax == depth:
        at = _with(t.center, ua, t.center[ua] + r * 0.7071)
        at = _with(at, va, at[va] + r * 0.7071)
        d.callout(f"{t.id}.section", at, label, ref)
    elif ax in (ua, va):
        n = math.sqrt(sum(c * c for c in t.axis)) or 1.0
        half = t.length / 2
        p1 = tuple(t.center[i] - t.axis[i] / n * half for i in range(3))
        d.add(f"{t.id}.length", (p1[0], p1[1], p1[2]), ax, t.center[ax] + t.axis[ax] / n * half, [ref], 1)
        other = va if ax == ua else ua
        d.callout(f"{t.id}.section", _with(t.center, other, t.center[other] + r), label, ref)


def fastener_dims(d: Dims, fasteners: list[Fastener], ua: int, va: int, depth: int) -> None:
    groups: dict[tuple, list[Fastener]] = {}
    for f in fasteners:
        if axis_index(f.axis) == depth:
            groups.setdefault((f.size, f.fastener_type), []).append(f)
    for (size, ftype), items in groups.items():
        gid = f"fasteners.{size}"
        for k in (ua, va):
            coords = sorted({round(f.position[k], 3) for f in items})
            for i in range(len(coords) - 1):
                a = next(f for f in items if round(f.position[k], 3) == coords[i])
                d.add(f"{gid}.pitch_{AXES[k]}_{i + 1}", a.position, k, coords[i + 1], [f"fastener:{a.id}"], 0)
        f0 = items[0]
        word = TYPE_RU.get(ftype, ftype)
        d.callout(gid, f0.position, f"{len(items)} × {size} ({word})", f"fastener:{f0.id}", (1.0, -1.0))


def explicit_dims(d: Dims, m: Project, g, spec: list[SketchDim], ua: int, va: int, depth: int) -> list[str]:
    notes = []
    for i, sd in enumerate(spec):
        if sd.view and sd.view != d.view:
            continue
        if sd.between:
            a, b = (point_of(m, g, r) for r in sd.between)
            if a is None or b is None:
                notes.append(f"размер {sd.between}: ссылка не найдена")
                continue
            k = AXES.index(sd.axis) if sd.axis else max((ua, va), key=lambda ax: abs(b[ax] - a[ax]))
            if k not in (ua, va):
                continue
            d.add(f"dim.{i + 1}", a, k, b[k], list(sd.between), 2, sd.text)
        elif sd.of:
            pid = sd.of.split(":", 1)[-1].split("/")[0]
            p = next((p for p in m.parts if p.id == pid), None)
            if p is None:
                notes.append(f"размер {sd.of}: деталь не найдена")
                continue
            if sd.kind == "thickness" and isinstance(p, PlatePart):
                n_ax = axis_index(p.placement.normal)
                if n_ax in (ua, va):
                    lo, hi = _bbox(g.parts[p.id])
                    mid = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)
                    d.callout(f"dim.{i + 1}", mid, sd.text or f"s{_num(p.thickness)}", sd.of)
            elif sd.kind == "length" and isinstance(p, TubePart):
                ax = axis_index(p.axis)
                if ax in (ua, va):
                    half = p.length / 2
                    p1 = _with(p.center, ax, p.center[ax] - half)
                    d.add(f"dim.{i + 1}", p1, ax, p.center[ax] + half, [sd.of], 1, sd.text)
            elif sd.kind == "diameter":
                at = point_of(m, g, sd.of)
                if at is not None:
                    label = sd.text or (f"Ø{_num(p.od)}×{_num(p.wall)}" if isinstance(p, TubePart) else "Ø")
                    d.callout(f"dim.{i + 1}", at, label, sd.of)
    return notes


# ---------------------------------------------------------------- эскиз


def write_sketch(m: Project, g, out: Path, prefix: str, views: list[str] | None = None, png: bool = True) -> dict:
    """Эскиз варианта по видам: <prefix>_sketch_<view>.svg (+ .png) и <prefix>_sketch.json в out/."""
    wanted = views or m.sketch.views or list(VIEWS)
    views = [v for v in wanted if v in VIEWS] or list(VIEWS)
    out.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    hide = set(m.sketch.hide)
    asm = g.assembly(m, with_purchased=True)
    bb = asm.bounding_box()
    c = (bb.center().X, bb.center().Y, bb.center().Z)
    parts_lo, parts_hi = _bbox(g.assembly(m, with_purchased=False)) if m.parts else ((0, 0, 0), (0, 0, 0))
    title = text(m.title, m.lang)
    res: dict = {
        "project": m.id,
        "variant": m.variant,
        "title": title,
        "views": {},
        "dims": [],
        "entities": [f"part:{p.id}" for p in m.parts] + [f"fastener:{f.id}" for f in m.fasteners],
        "notes": notes,
    }
    for view in views:
        s = VIEWS[view]
        ua, va, depth = s["u"][0], s["v"][0], s["depth"]
        umin, vmin, umax, vmax = project_box(view, parts_lo, parts_hi)
        size = max(umax - umin, vmax - vmin, 50.0)
        sh = Sheet(view, size, uid=f"s-{view}-{abs(hash((m.id, m.variant))) % 10000}")
        pad = 0.08 * size
        ext = (umin - pad, vmin - pad, umax + pad, vmax + pad)
        # компоновка фоном, бледнее
        if m.skeleton.surroundings or m.skeleton.envelopes:
            sh.raw("surroundings", '<g opacity="0.45">')
            for b in m.skeleton.surroundings:
                draw_surrounding(sh, b)
            for e in m.skeleton.envelopes:
                draw_envelope(sh, e)
            sh.raw("surroundings", "</g>")
            # подписи обстановки тоже бледнее: перенесём их из labels в surroundings
        for d in m.skeleton.datums:
            draw_datum(sh, d, ext)
        for i in m.skeleton.interfaces:
            draw_interface(sh, i, m, ext)
        # детали: HLR сборки (видимые — тёмные, скрытые — штриховые) + невидимые контуры деталей для подсветки
        cu, cv = to_view(view, c)
        inner = hlr_inner(asm, view, c, color=0x1B1F24)
        inner = re.sub(r'stroke-width="0\.35"', f'stroke-width="{sh.f(sh.lw)}"', inner)
        inner = re.sub(r'stroke-width="0\.18"', f'stroke-width="{sh.f(sh.lw * 0.5)}"', inner)
        sh.raw("parts", f'<g transform="translate({sh.f(cu)},{sh.f(-cv)})" data-ref="assembly">{inner}</g>')
        hits = []
        for p in m.parts:
            hi_inner = hlr_inner(g.parts[p.id], view, c, color=0x000000, hidden=False)
            hi_inner = re.sub(r'stroke-width="0\.35"', f'stroke-width="{sh.f(0.6 * sh.fs)}"', hi_inner)
            tr = f'transform="translate({sh.f(cu)},{sh.f(-cv)})"'
            hits.append(
                f'<g class="hit" data-ref="part:{p.id}" stroke-opacity="0" {tr}>'
                f"<title>{text(p.name, m.lang)}</title>{hi_inner}</g>"
            )
        for fid, fc in g.fasteners.items():
            hi_inner = hlr_inner(fc, view, c, color=0x000000, hidden=False)
            hi_inner = re.sub(r'stroke-width="0\.35"', f'stroke-width="{sh.f(0.6 * sh.fs)}"', hi_inner)
            tr = f'transform="translate({sh.f(cu)},{sh.f(-cv)})"'
            hits.append(f'<g class="hit" data-ref="fastener:{fid}" stroke-opacity="0" {tr}>{hi_inner}</g>')
        sh.raw("parts", "".join(hits))
        sh._bb((umin, vmin), (umax, vmax))
        sh.base = (umin, vmin, umax, vmax)  # размеры — снаружи деталей
        # размеры
        d = Dims(view, hide)
        for p in m.parts:
            if isinstance(p, PlatePart):
                plate_dims(d, p, *_bbox(g.parts[p.id]), ua, va, depth)
            else:
                tube_dims(d, p, ua, va, depth)
        fastener_dims(d, m.fasteners, ua, va, depth)
        notes += explicit_dims(d, m, g, m.sketch.dims, ua, va, depth)
        if m.parts:
            top = max((x["level"] for x in d.linear), default=-1) + 1
            for k in (ua, va):
                d.add(f"overall_{AXES[k]}", parts_lo, k, parts_hi[k], ["assembly"], top)
        for x in sorted(d.linear, key=lambda x: x["level"])[:MAX_DIMS]:
            sh.dim(
                to_view(view, x["p1"]),
                to_view(view, x["p2"]),
                x["text"],
                ref=f"dim:{x['id']}",
                dim_id=x["id"],
                axis=x["axis"],
                value=x["value"],
                refs=x["refs"],
                level=x["level"],
            )
        for cl in d.callouts:
            sh.callout(to_view(view, cl["at"]), cl["text"], cl["ref"], cl["id"], cl["side"])
        auto_dims(sh, m)  # положения скелета (вылет, отметка) — как на компоновке
        svg = sh.emit(f"{title} — эскиз", f"{s['title']}, {m.variant or m.id}", [])
        file = f"{prefix}_sketch_{view}.svg"
        (out / file).write_text(svg, encoding="utf-8")
        png_file = None
        if png:
            try:
                from skelcad.render import svg_to_png

                png_file = f"{prefix}_sketch_{view}.png"
                (out / png_file).write_bytes(svg_to_png(svg, 1400))
            except Exception as e:  # noqa: BLE001 — без растеризатора остаётся SVG
                png_file = None
                notes.append(f"PNG вида {view} не получен: {e}")
        res["views"][view] = {
            "svg": file,
            "png": png_file,
            "viewBox": sh.viewbox,
            "u": [AXES[ua], s["u"][1]],
            "v": [AXES[va], s["v"][1]],
            "depth": [AXES[depth], round(c[depth], 1)],
            "title": s["title"],
        }
        res["dims"] += sh.dims
    (out / f"{prefix}_sketch.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
