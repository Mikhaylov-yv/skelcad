"""Компоновочный эскиз: скелет (базы, интерфейсы, зоны), обстановка, нагрузки и ограничения — SVG по видам.

Строится из одного project.yaml, без генератора и сборки; собранные детали (если геометрия есть) рисуются
поверх тонкой линией — изделие видно в обстановке. Предмет согласования между конструктором и агентом
(D21): конструктор ставит пометки на эскизе и нажимает «Компоновка согласована».

Система координат вида — как у HLR-проекций build123d (render.py, views.py), но без сдвига к центру габарита:
u, v в мм модели. main (вдоль −X): u = −Y, v = Z; left (со стороны +Y): u = −X, v = Z; top (вдоль −Z): u = X, v = Y.
SVG: y экрана = −v; размеры шрифта, стрелок и штриховки — от размера сцены, чтобы эскиз читался при вписывании.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skelcad.core.model import (
    BoxBody,
    CylinderBody,
    Datum,
    Envelope,
    Interface,
    PlaneBody,
    Project,
    Surrounding,
    Vec3,
    axis_index,
    text,
)

DIST = 3000
VIEWS: dict[str, dict] = {
    "main": {"u": (1, -1.0), "v": (2, 1.0), "depth": 0, "eye": (-DIST, 0, 0), "up": (0, 0, 1), "title": "главный вид"},
    "left": {"u": (0, -1.0), "v": (2, 1.0), "depth": 1, "eye": (0, DIST, 0), "up": (0, 0, 1), "title": "вид слева"},
    "top": {"u": (0, 1.0), "v": (1, 1.0), "depth": 2, "eye": (0, 0, DIST), "up": (0, 1, 0), "title": "вид сверху"},
}
AXES = "XYZ"
LAYERS = ("surroundings", "envelopes", "datums", "interfaces", "parts", "loads", "dims", "labels", "marks")
C_MARK = "#e08a00"

# цвета — презентационные атрибуты; интерфейс переопределяет их по классам (тёмная тема)
C_SURR = "#6b7a8a"
C_SURR_FACE = "#3a4653"
C_DATUM = "#1f5fbf"
C_KEEP_IN = "#1b7f3b"
C_KEEP_OUT = "#b42318"
C_LOAD = "#b42318"
C_DIM = "#1b1f24"
C_TEXT = "#1b1f24"
C_MUTED = "#5b6470"

ROLE_RU = {
    "wall": "стена",
    "floor": "пол",
    "ceiling": "потолок",
    "pipe": "труба",
    "shaft": "вал",
    "equipment": "оборудование",
    "service_zone": "зона обслуживания",
    "mating_part": "ответная деталь",
}
KIND_RU = {"mount_plane": "крепление", "shaft_seat": "посадка вала", "pipe_rest": "опирание трубы", "flange": "фланец"}
PARAM_RU = {
    "anchor_size": "анкеры {v}",
    "concrete": "бетон {v}",
    "thread": "резьба {v}",
    "count": "{v} шт",
    "d": "Ø{v}",
    "od": "Ø{v}",
    "overhang": "вылет {v}",
    "length": "длина {v}",
    "lateral_gap": "зазор {v}",
}
LOAD_WORDS = {"fv": "вниз", "fh": "от опоры", "fa": "вдоль оси", "fx": "по X", "fy": "по Y", "fz": "по Z"}


# ---------------------------------------------------------------- координаты вида


def to_view(view: str, p: Vec3) -> tuple[float, float]:
    s = VIEWS[view]
    (ua, us), (va, vs) = s["u"], s["v"]
    return (us * p[ua], vs * p[va])


def from_view(view: str, u: float, v: float, depth: float) -> Vec3:
    """Точка модели по точке эскиза; координата вдоль взгляда — depth (обычно центр сцены)."""
    s = VIEWS[view]
    (ua, us), (va, vs) = s["u"], s["v"]
    out = [0.0, 0.0, 0.0]
    out[ua] = u / us
    out[va] = v / vs
    out[s["depth"]] = depth
    return (out[0], out[1], out[2])


def project_box(view: str, lo: Vec3, hi: Vec3) -> tuple[float, float, float, float]:
    """Габарит бокса модели на виде: (umin, vmin, umax, vmax)."""
    pts = [to_view(view, (x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _num(x: float) -> str:
    return f"{round(x):d}" if abs(x - round(x)) < 1e-6 else f"{x:.1f}".rstrip("0").rstrip(".")


def _name(e: Any) -> str:
    return text(getattr(e, "name", "") or "") or e.id


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _cyl_bbox(center: Vec3, axis: Vec3, diameter: float, length: float) -> tuple[Vec3, Vec3]:
    return CylinderBody(id="_", center=center, axis=axis, diameter=diameter, length=length).bbox()


# ---------------------------------------------------------------- лист SVG


@dataclass
class Sheet:
    """SVG-лист одного вида: примитивы по слоям в координатах вида (v вверх), размеры от величины сцены."""

    view: str
    size: float
    uid: str = "l"
    layers: dict[str, list[str]] = field(default_factory=lambda: {k: [] for k in LAYERS})
    bb: list[float] = field(default_factory=lambda: [math.inf, math.inf, -math.inf, -math.inf])
    dims: list[dict] = field(default_factory=list)
    levels: dict[str, int] = field(default_factory=lambda: {"h": 0, "v": 0})
    base: tuple[float, float, float, float] | None = None  # габарит содержимого до размеров и подписей
    viewbox: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        d = max(self.size, 50.0)
        self.fs = max(2.5, d / 42)  # высота шрифта, мм
        self.lw = max(0.25, d / 500)  # основная линия
        self.hs = max(2.0, d / 70)  # шаг штриховки
        self.gap = 2.6 * self.fs  # первый ярус размеров от контура
        self.step = 2.4 * self.fs  # шаг ярусов

    # ---------- служебное
    @staticmethod
    def f(x: float) -> str:
        return f"{x:.2f}".rstrip("0").rstrip(".") if abs(x) > 1e-9 else "0"

    def pt(self, u: float, v: float) -> str:
        return f"{self.f(u)},{self.f(-v)}"

    def _bb(self, *pts: tuple[float, float]) -> None:
        for u, v in pts:
            self.bb[0] = min(self.bb[0], u)
            self.bb[1] = min(self.bb[1], v)
            self.bb[2] = max(self.bb[2], u)
            self.bb[3] = max(self.bb[3], v)

    @staticmethod
    def _attrs(ref: str | None, cls: str | None) -> str:
        return (f' data-ref="{_esc(ref)}"' if ref else "") + (f' class="{cls}"' if cls else "")

    def _dash(self, dash: str | None) -> str:
        if not dash:
            return ""
        fs = self.fs
        kinds = {
            "dash": f"{fs:.2f} {fs * 0.5:.2f}",
            "dashdot": f"{fs * 1.6:.2f} {fs * 0.4:.2f} {fs * 0.3:.2f} {fs * 0.4:.2f}",
        }
        return f' stroke-dasharray="{kinds.get(dash, dash)}"'

    @staticmethod
    def _title(title: str | None, tag: str) -> str:
        return f"><title>{_esc(title)}</title></{tag}>" if title else "/>"

    # ---------- примитивы
    def line(self, layer, a, b, color=C_DIM, width=None, dash=None, ref=None, cls=None) -> None:
        self._bb(a, b)
        w = width if width is not None else self.lw
        self.layers[layer].append(
            f'<line x1="{self.f(a[0])}" y1="{self.f(-a[1])}" x2="{self.f(b[0])}" y2="{self.f(-b[1])}" '
            f'stroke="{color}" stroke-width="{self.f(w)}"{self._dash(dash)}{self._attrs(ref, cls)}/>'
        )

    def rect(self, layer, box, color=C_DIM, width=None, dash=None, fill="none", ref=None, cls=None, title=None):
        """box = (umin, vmin, umax, vmax) в координатах вида."""
        umin, vmin, umax, vmax = box
        self._bb((umin, vmin), (umax, vmax))
        w = width if width is not None else self.lw
        self.layers[layer].append(
            f'<rect x="{self.f(umin)}" y="{self.f(-vmax)}" width="{self.f(umax - umin)}" '
            f'height="{self.f(vmax - vmin)}" fill="{fill}" stroke="{color}" stroke-width="{self.f(w)}"'
            f"{self._dash(dash)}{self._attrs(ref, cls)}{self._title(title, 'rect')}"
        )

    def circle(self, layer, c, r, color=C_DIM, width=None, dash=None, fill="none", ref=None, cls=None, title=None):
        self._bb((c[0] - r, c[1] - r), (c[0] + r, c[1] + r))
        w = width if width is not None else self.lw
        self.layers[layer].append(
            f'<circle cx="{self.f(c[0])}" cy="{self.f(-c[1])}" r="{self.f(r)}" fill="{fill}" stroke="{color}" '
            f'stroke-width="{self.f(w)}"{self._dash(dash)}{self._attrs(ref, cls)}{self._title(title, "circle")}'
        )

    def text(self, layer, at, s, size=None, anchor="start", rotate=0.0, color=C_TEXT, weight=None, ref=None):
        fs = size or self.fs
        w = 0.56 * fs * len(s)
        if rotate:
            self._bb((at[0] - fs, at[1]), (at[0], at[1] + w))
        else:
            left = at[0] - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
            self._bb((left, at[1] - 0.25 * fs), (left + w, at[1] + fs))
        tr = f' transform="rotate({self.f(-rotate)} {self.pt(*at)})"' if rotate else ""
        wt = f' font-weight="{weight}"' if weight else ""
        self.layers[layer].append(
            f'<text x="{self.f(at[0])}" y="{self.f(-at[1])}" font-size="{self.f(fs)}" text-anchor="{anchor}" '
            f'fill="{color}"{wt}{tr}{self._attrs(ref, None)}>{_esc(s)}</text>'
        )

    def cross(self, layer, c, r, color=C_DIM, dash="dashdot", ref=None) -> None:
        self.line(layer, (c[0] - r, c[1]), (c[0] + r, c[1]), color, self.lw * 0.6, dash, ref)
        self.line(layer, (c[0], c[1] - r), (c[0], c[1] + r), color, self.lw * 0.6, dash, ref)

    def arrowhead(self, layer, tip, direction, color=C_DIM, length=None) -> None:
        n = math.hypot(direction[0], direction[1]) or 1.0
        d = (direction[0] / n, direction[1] / n)
        al = length or 0.9 * self.fs
        aw = 0.32 * al
        base = (tip[0] - d[0] * al, tip[1] - d[1] * al)
        left = (base[0] - d[1] * aw, base[1] + d[0] * aw)
        right = (base[0] + d[1] * aw, base[1] - d[0] * aw)
        self.layers[layer].append(
            f'<path d="M {self.pt(*tip)} L {self.pt(*left)} L {self.pt(*right)} Z" fill="{color}" stroke="none"/>'
        )

    def load_arrow(self, a, b, label: str, ref: str | None = None) -> None:
        fs = self.fs
        self.line("loads", a, b, C_LOAD, self.lw * 1.2, ref=ref)
        self.arrowhead("loads", b, (b[0] - a[0], b[1] - a[1]), C_LOAD, 1.2 * fs)
        if abs(b[1] - a[1]) > abs(b[0] - a[0]):  # вертикальная стрелка — подпись сбоку у острия
            at = (b[0] + 0.6 * fs, b[1] - (0.3 * fs if b[1] < a[1] else -0.9 * fs))
            self.text("loads", at, label, 0.95 * fs, "start", color=C_LOAD, weight="600", ref=ref)
        else:
            right = b[0] >= a[0]
            at = (b[0] + (0.5 * fs if right else -0.5 * fs), b[1] + 0.5 * fs)
            self.text("loads", at, label, 0.95 * fs, "start" if right else "end", color=C_LOAD, weight="600", ref=ref)

    def dim(
        self,
        p1,
        p2,
        label: str,
        ref: str,
        dim_id: str,
        axis: str,
        value: float,
        refs: list[str],
        level: int | None = None,
    ) -> None:
        """Линейный размер между двумя точками одного вида (по u или по v); размерная линия — снаружи
        содержимого, ярусами: горизонтальные снизу, вертикальные слева. level — ярус (цепочка размеров
        делит один ярус), иначе следующий свободный."""
        base = self.base or tuple(self.bb)
        horizontal = abs(p1[1] - p2[1]) <= abs(p1[0] - p2[0])
        key = "h" if horizontal else "v"
        if level is None:
            level = self.levels[key]
        self.levels[key] = max(self.levels[key], level + 1)
        off = self.gap + level * self.step
        ov = 0.7 * self.fs
        al = 0.9 * self.fs
        thin = self.lw * 0.5
        if horizontal:
            vl = base[1] - off
            u1, u2 = sorted((p1[0], p2[0]))
            for p in (p1, p2):
                self.line("dims", (p[0], p[1] - 0.3 * self.fs), (p[0], vl - ov), C_DIM, thin, ref=ref)
            self.line("dims", (u1, vl), (u2, vl), C_DIM, self.lw * 0.6, ref=ref)
            inside = (u2 - u1) > 3 * al
            self.arrowhead("dims", (u1, vl), (-1, 0) if inside else (1, 0), C_DIM, al)
            self.arrowhead("dims", (u2, vl), (1, 0) if inside else (-1, 0), C_DIM, al)
            self.text("dims", ((u1 + u2) / 2, vl + 0.35 * self.fs), label, anchor="middle", ref=ref)
        else:
            ul = base[0] - off
            v1, v2 = sorted((p1[1], p2[1]))
            for p in (p1, p2):
                self.line("dims", (p[0] - 0.3 * self.fs, p[1]), (ul - ov, p[1]), C_DIM, thin, ref=ref)
            self.line("dims", (ul, v1), (ul, v2), C_DIM, self.lw * 0.6, ref=ref)
            inside = (v2 - v1) > 3 * al
            self.arrowhead("dims", (ul, v1), (0, -1) if inside else (0, 1), C_DIM, al)
            self.arrowhead("dims", (ul, v2), (0, 1) if inside else (0, -1), C_DIM, al)
            self.text("dims", (ul - 0.35 * self.fs, (v1 + v2) / 2), label, anchor="middle", rotate=90, ref=ref)
        self.dims.append(
            {
                "id": dim_id,
                "view": self.view,
                "kind": "linear",
                "axis": axis,
                "value": round(value, 2),
                "text": label,
                "refs": refs,
            }
        )

    def callout(self, at, label: str, ref: str, dim_id: str, side: tuple[float, float] = (1.0, 1.0)) -> None:
        """Выноска: линия от точки `at` под 45° и полка с текстом (диаметр, радиус, сечение трубы, крепёж)."""
        fs = self.fs
        knee = (at[0] + side[0] * 1.8 * fs, at[1] + side[1] * 1.8 * fs)
        w = 0.56 * fs * len(label)
        end = (knee[0] + side[0] * (w + 0.4 * fs), knee[1])
        self.line("dims", at, knee, C_DIM, self.lw * 0.5, ref=ref)
        self.line("dims", knee, end, C_DIM, self.lw * 0.5, ref=ref)
        x = min(knee[0], end[0]) + 0.2 * fs
        self.text("dims", (x, knee[1] + 0.3 * fs), label, ref=ref)
        self.dims.append(
            {
                "id": dim_id,
                "view": self.view,
                "kind": "callout",
                "axis": "",
                "value": None,
                "text": label,
                "refs": [ref],
            }
        )

    def raw(self, layer: str, svg: str) -> None:
        self.layers[layer].append(svg)

    # ---------- лист
    def emit(self, title: str, subtitle: str, legend: list[str]) -> str:
        fs = self.fs
        if not math.isfinite(self.bb[0]):
            self._bb((0, 0), (100, 100))
        top = self.bb[3] + 1.2 * fs  # заголовок над содержимым, легенда — под ним
        self.text("labels", (self.bb[0], top + 1.5 * fs), title, 1.15 * fs, weight="600")
        self.text("labels", (self.bb[0], top), subtitle, 0.9 * fs, color=C_MUTED)
        y = self.bb[1] - 1.6 * fs
        for line in legend:
            self.text("labels", (self.bb[0], y), line, 0.85 * fs, color=C_MUTED)
            y -= 1.35 * fs
        m = 2 * fs
        x0, y0 = self.bb[0] - m, -(self.bb[3] + m)
        w, h = (self.bb[2] - self.bb[0]) + 2 * m, (self.bb[3] - self.bb[1]) + 2 * m
        self.viewbox = [round(x0, 2), round(y0, 2), round(w, 2), round(h, 2)]
        hs = self.f(self.hs)
        hatch = (
            '<pattern id="hatch-{id}" width="{hs}" height="{hs}" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="{hs}" stroke="{c}" '
            'stroke-width="{w}"/></pattern>'
        )
        defs = "<defs>{}{}</defs>".format(
            hatch.format(id=self.uid, hs=hs, c=C_SURR, w=self.f(self.lw * 0.6)),
            hatch.format(id="out-" + self.uid, hs=hs, c=C_KEEP_OUT, w=self.f(self.lw * 0.6)),
        )
        body = "".join(f'<g class="{name}">{"".join(items)}</g>' for name, items in self.layers.items() if items)
        vb = " ".join(self.f(x) for x in self.viewbox)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{self.f(w)}" height="{self.f(h)}" '
            f'data-view="{self.view}" font-family="system-ui, Arial, sans-serif" class="layout">{defs}{body}</svg>'
        )


# ---------------------------------------------------------------- элементы компоновки


def iface_short(i: Interface) -> str:
    """Краткая подпись интерфейса из параметров: «анкеры M16, бетон B25», «Ø50H8/f7, вылет 30»."""
    p = i.params
    parts = [PARAM_RU[k].format(v=v) for k, v in p.items() if k in PARAM_RU]
    fit = f"{p['fit_hole']}/{p['fit_shaft']}" if "fit_hole" in p and "fit_shaft" in p else ""
    if fit:
        if any(x.startswith("Ø") for x in parts):
            parts = [x + fit if x.startswith("Ø") else x for x in parts]
        else:
            parts.append(fit)
    return ", ".join(parts) or KIND_RU.get(i.kind, i.kind)


def surrounding_label(b: Surrounding) -> str:
    lo, hi = b.bbox()
    if isinstance(b, CylinderBody):
        size = f"Ø{_num(b.diameter)}×{_num(b.length)}"
    elif isinstance(b, PlaneBody):
        size = f"{_num(2 * b.extent)}×{_num(2 * b.extent)}, толщина {_num(b.thickness)}"
    else:
        size = "×".join(_num(hi[i] - lo[i]) for i in range(3))
    role = ROLE_RU.get(b.role, b.role)
    mat = f", {b.material}" if b.material else ""
    return f"{_name(b)} ({role + ', ' if role else ''}{size}{mat})"


def draw_surrounding(sh: Sheet, b: Surrounding) -> None:
    s = VIEWS[sh.view]
    (ua, us), (va, vs) = s["u"], s["v"]
    ref, name = f"surrounding:{b.id}", _name(b)
    fs, lw = sh.fs, sh.lw
    lo, hi = b.bbox()
    box = project_box(sh.view, lo, hi)
    umin, vmin, umax, vmax = box
    if isinstance(b, CylinderBody):
        ax = axis_index(b.axis)
        c2 = to_view(sh.view, b.center)
        r = b.diameter / 2
        label = f"{name} Ø{_num(b.diameter)}"
        if ax == s["depth"]:
            sh.circle("surroundings", c2, r, C_SURR, lw, ref=ref, title=name)
            sh.cross("surroundings", c2, 1.25 * r, C_SURR, ref=ref)
            sh.text("labels", (c2[0] + r + 0.4 * fs, c2[1] + r), label, 0.9 * fs, color=C_SURR_FACE, ref=ref)
            return
        sh.rect("surroundings", box, C_SURR, lw, ref=ref, title=name)
        if ax == ua:
            a, c = (umin - 0.6 * fs, c2[1]), (umax + 0.6 * fs, c2[1])
            sh.line("surroundings", a, c, C_SURR, lw * 0.6, "dashdot", ref)
        elif ax == va:
            a, c = (c2[0], vmin - 0.6 * fs), (c2[0], vmax + 0.6 * fs)
            sh.line("surroundings", a, c, C_SURR, lw * 0.6, "dashdot", ref)
        sh.text("labels", (umin, vmax + 0.4 * fs), label, 0.9 * fs, color=C_SURR_FACE, ref=ref)
        return
    if isinstance(b, BoxBody):
        dash = "dash" if b.role == "service_zone" else "dashdot" if b.role == "mating_part" else None
        fill = "none" if dash else "rgba(107,122,138,0.08)"
        sh.rect("surroundings", box, C_SURR, lw, dash, fill, ref=ref, title=name)
        size = "×".join(_num(b.max[i] - b.min[i]) for i in range(3))
        sh.text("labels", (umin, vmax + 0.4 * fs), f"{name} {size}", 0.9 * fs, color=C_SURR_FACE, ref=ref)
        return
    # плоская поверхность: с ребра — разрез со штриховкой и толстая линия по плоскости, в лицо — след квадрата
    ax = axis_index(b.normal)
    if ax is None or ax == s["depth"]:
        sh.rect("surroundings", box, C_SURR, lw * 0.7, "dash", ref=ref, title=name)
        tag = f"{name} (в плане)" if ax is not None else name
        sh.text("labels", (umin, vmax + 0.4 * fs), tag, 0.9 * fs, color=C_MUTED, ref=ref)
        return
    sh.rect("surroundings", box, C_SURR, lw * 0.5, None, f"url(#hatch-{sh.uid})", ref=ref, title=name)
    label = name + (f", {b.material}" if b.material else "")
    mid = ((umin + umax) / 2, (vmin + vmax) / 2)
    if ax == ua:
        face = us * b.origin[ax]
        sh.line("surroundings", (face, vmin), (face, vmax), C_SURR_FACE, lw * 1.8, ref=ref)
        sh.text("labels", mid, label, 0.85 * fs, "middle", 90, C_SURR_FACE, ref=ref)
    else:
        face = vs * b.origin[ax]
        sh.line("surroundings", (umin, face), (umax, face), C_SURR_FACE, lw * 1.8, ref=ref)
        sh.text("labels", (mid[0], mid[1] - 0.4 * fs), label, 0.85 * fs, "middle", 0, C_SURR_FACE, ref=ref)


def draw_envelope(sh: Sheet, e: Envelope) -> None:
    box = project_box(sh.view, e.min, e.max)
    ref, name = f"envelope:{e.id}", _name(e)
    size = "×".join(_num(e.max[i] - e.min[i]) for i in range(3))
    at = (box[0], box[3] + 0.4 * sh.fs)
    if e.kind == "keep_out":
        sh.rect("envelopes", box, C_KEEP_OUT, sh.lw * 0.8, "dash", f"url(#hatch-out-{sh.uid})", ref=ref, title=name)
        sh.text("labels", at, f"запретная зона: {name} {size}", 0.85 * sh.fs, color=C_KEEP_OUT, ref=ref)
    else:
        sh.rect("envelopes", box, C_KEEP_IN, sh.lw * 0.8, "dash", ref=ref, title=name)
        sh.text("labels", at, f"отведённый объём: {name} {size}", 0.85 * sh.fs, color=C_KEEP_IN, ref=ref)


def draw_datum(sh: Sheet, d: Datum, ext: tuple[float, float, float, float]) -> None:
    s = VIEWS[sh.view]
    (ua, _), (va, _) = s["u"], s["v"]
    ref = f"datum:{d.id}"
    o = to_view(sh.view, d.origin)
    umin, vmin, umax, vmax = ext
    fs, lw = sh.fs, sh.lw
    small = 0.85 * fs
    if d.kind == "point":
        sh.cross("datums", o, 0.8 * fs, C_DATUM, None, ref)
        sh.text("labels", (o[0] + 0.5 * fs, o[1] + 0.5 * fs), d.id, small, color=C_DATUM, ref=ref)
        return
    ax = axis_index(d.direction)
    if d.kind == "plane":
        if ax is None or ax == s["depth"]:
            return  # плоскость видна в лицо — её называет легенда
        if ax == ua:
            sh.line("datums", (o[0], vmin), (o[0], vmax), C_DATUM, lw * 0.7, "dashdot", ref)
            sh.text("labels", (o[0] + 0.3 * fs, vmax + 0.3 * fs), d.id, small, color=C_DATUM, ref=ref)
        else:
            sh.line("datums", (umin, o[1]), (umax, o[1]), C_DATUM, lw * 0.7, "dashdot", ref)
            sh.text("labels", (umax + 0.3 * fs, o[1] + 0.3 * fs), d.id, small, color=C_DATUM, ref=ref)
        return
    # ось
    if ax == s["depth"]:
        sh.circle("datums", o, 0.55 * fs, C_DATUM, lw * 0.6, ref=ref)
        sh.cross("datums", o, 1.2 * fs, C_DATUM, "dashdot", ref)
        sh.text("labels", (o[0] + 1.4 * fs, o[1] + 0.9 * fs), d.id, small, color=C_DATUM, ref=ref)
    elif ax == ua:
        sh.line("datums", (umin, o[1]), (umax, o[1]), C_DATUM, lw * 0.7, "dashdot", ref)
        sh.text("labels", (umax + 0.3 * fs, o[1] + 0.3 * fs), d.id, small, color=C_DATUM, ref=ref)
    elif ax == va:
        sh.line("datums", (o[0], vmin), (o[0], vmax), C_DATUM, lw * 0.7, "dashdot", ref)
        sh.text("labels", (o[0] + 0.3 * fs, vmax + 0.3 * fs), d.id, small, color=C_DATUM, ref=ref)
    else:
        d2 = to_view(sh.view, _unit(d.direction))
        n = math.hypot(*d2) or 1.0
        half = 0.6 * sh.size
        a = (o[0] - d2[0] / n * half, o[1] - d2[1] / n * half)
        b = (o[0] + d2[0] / n * half, o[1] + d2[1] / n * half)
        sh.line("datums", a, b, C_DATUM, lw * 0.7, "dashdot", ref)
        sh.text("labels", (b[0] + 0.3 * fs, b[1]), d.id, small, color=C_DATUM, ref=ref)


def draw_interface(sh: Sheet, i: Interface, m: Project, ext: tuple[float, float, float, float]) -> None:
    s = VIEWS[sh.view]
    ua = s["u"][0]
    ref = f"interface:{i.id}"
    d = m.skeleton.datum(i.datum) if i.datum else None
    fs, lw = sh.fs, sh.lw
    small = 0.85 * fs
    if i.body:
        ax = axis_index(i.body.axis)
        if ax == s["depth"]:
            c2 = to_view(sh.view, i.body.center)
            sh.circle("interfaces", c2, i.body.diameter / 2, C_DATUM, lw * 0.8, "dash", ref=ref, title=_name(i))
        elif ax is not None:
            box = project_box(sh.view, *_cyl_bbox(i.body.center, i.body.axis, i.body.diameter, i.body.length))
            sh.rect("interfaces", box, C_DATUM, lw * 0.8, "dash", ref=ref, title=_name(i))
    elif d is not None and d.kind == "axis" and i.kind in ("shaft_seat", "pipe_rest"):
        dia = float(i.params.get("d") or i.params.get("od") or 0)
        if dia > 0 and axis_index(d.direction) == s["depth"]:
            c2 = to_view(sh.view, d.origin)
            sh.circle("interfaces", c2, dia / 2, C_DATUM, lw * 0.8, "dash", ref=ref, title=_name(i))
    if d is None:
        return
    o = to_view(sh.view, d.origin)
    label = f"{i.id}: {iface_short(i)}"
    umin, vmin, umax, vmax = ext
    if d.kind == "plane":
        ax = axis_index(d.direction)
        n2 = to_view(sh.view, _unit(d.direction)) if d.direction else (0.0, 0.0)
        if ax is None or ax == s["depth"]:  # плоскость в лицо: подпись в верхнем левом углу сцены, под подписью тела
            sh.text("labels", (umin + 0.5 * fs, vmax - 3.2 * fs), label, small, color=C_DATUM, ref=ref)
        elif ax == ua:  # вертикальная линия: подпись у верхнего конца со стороны нормали (к изделию)
            right = n2[0] > 0
            at = (o[0] + (0.4 * fs if right else -0.4 * fs), vmax - 0.9 * fs)
            sh.text("labels", at, label, small, "start" if right else "end", color=C_DATUM, ref=ref)
        else:  # горизонтальная линия: подпись у левого конца со стороны нормали
            up = n2[1] > 0
            sh.text("labels", (umin, o[1] + (0.4 * fs if up else -1.2 * fs)), label, small, color=C_DATUM, ref=ref)
    else:
        sh.text("labels", (o[0] + 1.4 * fs, o[1] - 1.3 * fs), label, small, color=C_DATUM, ref=ref)


def load_directions(m: Project) -> tuple[Vec3, Vec3]:
    """Направления условных имён нагрузок: «от опоры» — нормаль первой плоскости скелета, «вдоль оси» — первая ось."""
    mount = next((d for d in m.skeleton.datums if d.kind == "plane" and d.direction), None)
    axis = next((d for d in m.skeleton.datums if d.kind == "axis" and d.direction), None)
    return (
        _unit(mount.direction) if mount else (0.0, 1.0, 0.0),
        _unit(axis.direction) if axis else (1.0, 0.0, 0.0),
    )


def load_dir(name: str, value: float, mount_n: Vec3, axis_d: Vec3) -> Vec3 | None:
    """Fx/Fy/Fz — по осям; Fv — вниз; Fh — от опорной плоскости; Fa — вдоль оси; знак значения меняет сторону."""
    base = {
        "fx": (1.0, 0.0, 0.0),
        "fy": (0.0, 1.0, 0.0),
        "fz": (0.0, 0.0, 1.0),
        "fv": (0.0, 0.0, -1.0),
        "fh": mount_n,
        "fa": axis_d,
    }.get(name.lower())
    if base is None:
        return None
    sgn = -1.0 if value < 0 else 1.0
    return (base[0] * sgn, base[1] * sgn, base[2] * sgn)


def load_point(m: Project, ext3: tuple[Vec3, Vec3]) -> Vec3:
    for i in m.skeleton.interfaces:
        if i.kind != "mount_plane" and i.datum and (d := m.skeleton.datum(i.datum)):
            return d.origin
    lo, hi = ext3
    return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2)


def draw_loads(sh: Sheet, m: Project, at3: Vec3) -> list[dict]:
    mount_n, axis_d = load_directions(m)
    s = VIEWS[sh.view]
    (ua, us), (va, vs) = s["u"], s["v"]
    at = to_view(sh.view, at3)
    items = [(k, v, "requirements") for k, v in m.requirements.loads.items()]
    for i in m.skeleton.interfaces:
        items += [(k, v, f"interface:{i.id}") for k, v in i.loads.items()]
    out, flat = [], []
    length = 0.22 * sh.size
    for name, val, src in items:
        if not val:
            continue
        d3 = load_dir(name, float(val), mount_n, axis_d)
        label = f"{name} = {_num(abs(float(val)))} кН"
        out.append({"name": name, "value": val, "source": src, "dir": list(d3) if d3 else None})
        if d3 is None:
            flat.append(label)
            continue
        d2 = (us * d3[ua], vs * d3[va])
        n = math.hypot(*d2)
        if n < 0.3:  # перпендикулярно виду — подпись без стрелки
            flat.append(label + " ⊙")
            continue
        tip = (at[0] + d2[0] / n * length, at[1] + d2[1] / n * length)
        sh.load_arrow(at, tip, label, ref=f"load:{name}")
    if flat:
        at2 = (at[0] + 0.6 * sh.fs, at[1] + 2.3 * sh.fs)
        sh.text("loads", at2, "; ".join(flat), 0.9 * sh.fs, color=C_LOAD, weight="600")
    return out


def auto_dims(sh: Sheet, m: Project) -> None:
    """Положения осей, точек и тел обстановки относительно плоскостей скелета; тела обстановки относительно
    осей. Дубликаты (та же ось, те же координаты) не повторяются; не больше восьми размеров на вид."""
    s = VIEWS[sh.view]
    screen = {s["u"][0], s["v"][0]}
    seen: set[tuple] = set()
    planes = [d for d in m.skeleton.datums if d.kind == "plane" and axis_index(d.direction) in screen]
    axes_pts: list[tuple[str, Vec3]] = [
        (f"datum:{d.id}", d.origin) for d in m.skeleton.datums if d.kind in ("axis", "point")
    ]
    points = axes_pts + [
        (f"surrounding:{b.id}", b.center) for b in m.skeleton.surroundings if isinstance(b, CylinderBody)
    ]
    n = 0

    def put(pt: Vec3, k: int, coord: float, dim_id: str, refs: list[str]) -> None:
        nonlocal n
        p0 = list(pt)
        p0[k] = coord
        dist = abs(coord - pt[k])
        sh.dim(
            to_view(sh.view, pt),
            to_view(sh.view, (p0[0], p0[1], p0[2])),
            _num(dist),
            ref=f"dim:{dim_id}",
            dim_id=dim_id,
            axis=AXES[k],
            value=dist,
            refs=refs,
        )
        n += 1

    for pl in planes:
        k = axis_index(pl.direction)
        for ref, pt in points:
            key = (k, round(pl.origin[k], 1), round(pt[k], 1))
            if abs(pt[k] - pl.origin[k]) < 0.5 or key in seen or n >= 8:
                continue
            seen.add(key)
            put(pt, k, pl.origin[k], f"{pl.id}-{ref.split(':')[1]}", [f"datum:{pl.id}", ref])
    for b in m.skeleton.surroundings:
        if isinstance(b, PlaneBody):
            continue
        lo, hi = b.bbox()
        ref_b = f"surrounding:{b.id}"
        for pl in planes:  # зазор от плоскости скелета до ближней грани тела (ответная деталь над базой)
            k = axis_index(pl.direction)
            c0 = pl.origin[k]
            if lo[k] - 0.5 <= c0 <= hi[k] + 0.5 or n >= 8:
                continue
            face = lo[k] if c0 < lo[k] else hi[k]
            key = (k, round(c0, 1), round(face, 1))
            if key in seen:
                continue
            seen.add(key)
            mid = [(lo[i] + hi[i]) / 2 for i in range(3)]
            mid[k] = face
            put((mid[0], mid[1], mid[2]), k, c0, f"{pl.id}-{b.id}", [f"datum:{pl.id}", ref_b])
        for ref, pt in axes_pts:
            for k in sorted(screen):
                if lo[k] - 0.5 <= pt[k] <= hi[k] + 0.5 or n >= 8:
                    continue
                face = lo[k] if pt[k] < lo[k] else hi[k]
                key = (k, round(face, 1), round(pt[k], 1))
                if key in seen:
                    continue
                seen.add(key)
                put(pt, k, face, f"{b.id}-{ref.split(':')[1]}", [f"surrounding:{b.id}", ref])


# ---------------------------------------------------------------- сцена, легенда, проекции деталей


def scene_bbox3(m: Project, parts_bbox: tuple[Vec3, Vec3] | None) -> tuple[Vec3, Vec3]:
    lo = [math.inf] * 3
    hi = [-math.inf] * 3

    def add(a: Vec3, b: Vec3 | None = None) -> None:
        b = b or a
        for k in range(3):
            lo[k] = min(lo[k], a[k], b[k])
            hi[k] = max(hi[k], a[k], b[k])

    for b in m.skeleton.surroundings:
        add(*b.bbox())
    for e in m.skeleton.envelopes:
        add(e.min, e.max)
    for d in m.skeleton.datums:
        add(d.origin)
    for i in m.skeleton.interfaces:
        if i.body:
            add(*_cyl_bbox(i.body.center, i.body.axis, i.body.diameter, i.body.length))
    if parts_bbox:
        add(*parts_bbox)
    if not math.isfinite(lo[0]):
        lo, hi = [-50.0] * 3, [50.0] * 3
    for k in range(3):
        if hi[k] - lo[k] < 20:
            c = (hi[k] + lo[k]) / 2
            lo[k], hi[k] = c - 10, c + 10
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


def legend_lines(m: Project) -> list[str]:
    r = m.requirements
    lines = []
    if text(r.purpose, m.lang):
        lines.append(f"Назначение: {text(r.purpose, m.lang)}")
    if r.loads:
        loads = []
        for k, v in r.loads.items():
            word = LOAD_WORDS.get(k.lower())
            loads.append(f"{k} = {_num(float(v))} кН" + (f" ({word})" if word else ""))
        extra = "; ".join(f"{k} = {_num(float(v))}" for k, v in r.factors.items())
        line = "Нагрузки: " + "; ".join(loads) + (f"; {extra}" if extra else "")
        lines.append(f"{line}; K_треб = {_num(r.safety_required)}")
    if r.environment:
        lines.append("Среда: " + "; ".join(f"{k}: {v}" for k, v in r.environment.items()))
    if r.constraints:
        lines.append("Ограничения: " + "; ".join(f"{k}: {v}" for k, v in r.constraints.items()))
    sk = m.skeleton
    if sk.datums:
        lines.append("Базы: " + "; ".join(f"{d.id} — {_name(d)}" for d in sk.datums))
    if sk.interfaces:
        lines.append("Интерфейсы: " + "; ".join(f"{i.id} — {_name(i)}: {iface_short(i)}" for i in sk.interfaces))
    if sk.envelopes:
        kinds = {"keep_out": "запретная", "keep_in": "отведённая"}
        lines.append("Зоны: " + "; ".join(f"{e.id} — {kinds[e.kind]}: {_name(e)}" for e in sk.envelopes))
    if sk.surroundings:
        lines.append("Обстановка: " + "; ".join(f"{b.id} — {surrounding_label(b)}" for b in sk.surroundings))
    return lines


def entity_geom(e: Any) -> dict:
    """Числовые поля сущности для ручек на эскизе (M2.3): положение и размеры; направления — только для чтения."""
    if isinstance(e, Datum):
        return {"origin": list(e.origin), "direction": list(e.direction) if e.direction else None}
    if isinstance(e, Interface):
        body = e.body
        return {
            "datum": e.datum,
            "body": {
                "center": list(body.center),
                "axis": list(body.axis),
                "diameter": body.diameter,
                "length": body.length,
            }
            if body
            else None,
        }
    if isinstance(e, Envelope):
        return {"min": list(e.min), "max": list(e.max)}
    if isinstance(e, PlaneBody):
        return {"origin": list(e.origin), "normal": list(e.normal), "extent": e.extent, "thickness": e.thickness}
    if isinstance(e, BoxBody):
        return {"min": list(e.min), "max": list(e.max)}
    if isinstance(e, CylinderBody):
        return {"center": list(e.center), "axis": list(e.axis), "diameter": e.diameter, "length": e.length}
    return {}


def entities(m: Project) -> list[dict]:
    out = []
    groups = (
        ("datum", m.skeleton.datums),
        ("interface", m.skeleton.interfaces),
        ("envelope", m.skeleton.envelopes),
        ("surrounding", m.skeleton.surroundings),
    )
    for group, items in groups:
        for e in items:
            if isinstance(e, Interface):
                note = iface_short(e)
            elif group == "surrounding":
                note = surrounding_label(e)
            else:
                note = ""
            out.append(
                {
                    "ref": f"{group}:{e.id}",
                    "group": group,
                    "id": e.id,
                    "kind": getattr(e, "kind", ""),
                    "name": _name(e),
                    "status": e.status,
                    "source": e.source,
                    "note": note,
                    "geom": entity_geom(e),
                }
            )
    return out


Projection = tuple[dict[str, tuple[str, tuple[float, float]]], tuple[Vec3, Vec3]]


def hlr_inner(shape, view: str, c, color: int = 0x8A929B, hidden: bool = True) -> str:
    """HLR-проекция тела build123d на вид: внутренность SVG (слои visible / hidden) в координатах
    относительно точки c (центр, в который смотрит камера)."""
    import build123d as bd

    from skelcad.render import _svg_via_file

    s = VIEWS[view]
    eye, up = s["eye"], s["up"]
    origin = (c[0] + eye[0], c[1] + eye[1], c[2] + eye[2])
    visible, hid = shape.project_to_viewport(origin, up, look_at=(c[0], c[1], c[2]))
    exp = bd.ExportSVG(margin=1, line_weight=0.35)
    if hidden:
        exp.add_layer("hidden", line_color=0x8A929B, line_weight=0.18, line_type=bd.LineType.ISO_DASH)
        exp.add_shape(hid, layer="hidden")
    exp.add_layer("visible", line_color=color, line_weight=0.35)
    exp.add_shape(visible, layer="visible")
    svg = exp.get_svg_string() if hasattr(exp, "get_svg_string") else _svg_via_file(exp)
    mt = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S)
    inner = mt.group(1) if mt else ""
    return re.sub(r'\bid="(hidden|visible)"', r'class="\1"', inner)


def parts_projection(m: Project, g, views: list[str]) -> Projection:
    """HLR-проекции сборки по видам (внутренность SVG build123d) и её габарит; координаты проекции даны
    относительно центра габарита — сдвиг возвращает их в систему модели."""
    asm = g.assembly(m, with_purchased=True)
    bb = asm.bounding_box()
    c = bb.center()
    out = {}
    for view in views:
        inner = hlr_inner(asm, view, (c.X, c.Y, c.Z))
        out[view] = (inner, to_view(view, (c.X, c.Y, c.Z)))
    return out, ((bb.min.X, bb.min.Y, bb.min.Z), (bb.max.X, bb.max.Y, bb.max.Z))


def draw_marks(sh: Sheet, marks: list[dict]) -> int:
    """Пометки конструктора (review.yaml): точка — кружок с номером, росчерк — ломаная на своём виде.
    Возвращает число пометок, попавших на вид."""
    n = 0
    fs = sh.fs
    r = 0.6 * fs
    for mk in marks:
        mid = str(mk.get("id") or "")
        st = mk.get("stroke") if isinstance(mk.get("stroke"), dict) else None
        if st and st.get("view") == sh.view and len(st.get("points") or []) >= 2:
            pts = [to_view(sh.view, (float(p[0]), float(p[1]), float(p[2]))) for p in st["points"]]
            sh._bb(*pts)
            path = " ".join(sh.pt(*p) for p in pts)
            sh.raw(
                "marks",
                f'<polyline points="{path}" fill="none" stroke="{C_MARK}" stroke-width="{sh.f(sh.lw * 2.2)}" '
                f'stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.9" data-mark="{_esc(mid)}"/>',
            )
            sh.text("marks", (pts[0][0] + 0.4 * fs, pts[0][1] + 0.4 * fs), mid, 0.9 * fs, color=C_MARK, weight="600")
            n += 1
            continue
        pt = mk.get("point")
        if isinstance(pt, list | tuple) and len(pt) == 3 and not st:
            c = to_view(sh.view, (float(pt[0]), float(pt[1]), float(pt[2])))
            sh.circle("marks", c, r, C_MARK, sh.lw * 1.2, fill="rgba(224,138,0,0.35)", title=mid)
            sh.text("marks", (c[0] + r + 0.2 * fs, c[1] + 0.3 * fs), mid, 0.9 * fs, color=C_MARK, weight="600")
            n += 1
    return n


def write_layout(
    m: Project,
    g,
    out: Path,
    prefix: str,
    views: list[str] | None = None,
    png: bool = True,
    marks: list[dict] | None = None,
) -> dict:
    """Компоновочный эскиз по видам: <prefix>_layout_<view>.svg (+ .png) и <prefix>_layout.json в out/.
    marks — открытые замечания конструктора (точки и росчерки) из review.yaml: рисуются поверх, видны агенту в PNG."""
    views = [v for v in (views or list(VIEWS)) if v in VIEWS] or list(VIEWS)
    out.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    parts_svg: dict[str, tuple[str, tuple[float, float]]] = {}
    parts_bbox = None
    if g is not None and m.parts:
        try:
            parts_svg, parts_bbox = parts_projection(m, g, views)
        except Exception as e:  # noqa: BLE001 — проекция деталей не должна валить компоновку
            notes.append(f"проекция деталей не построена: {e}")
    lo3, hi3 = scene_bbox3(m, parts_bbox)
    legend = legend_lines(m)
    title = text(m.title, m.lang)
    res: dict = {
        "project": m.id,
        "variant": m.variant,
        "title": title,
        "views": {},
        "dims": [],
        "entities": entities(m),
        "loads": [],
        "legend": legend,
        "parts": bool(parts_svg),
        "notes": notes,
    }
    at3 = load_point(m, (lo3, hi3))
    for view in views:
        s = VIEWS[view]
        umin, vmin, umax, vmax = project_box(view, lo3, hi3)
        size = max(umax - umin, vmax - vmin)
        sh = Sheet(view, size, uid=f"{view}-{abs(hash((m.id, m.variant))) % 10000}")
        pad = 0.06 * size
        ext = (umin - pad, vmin - pad, umax + pad, vmax + pad)
        for b in m.skeleton.surroundings:
            draw_surrounding(sh, b)
        for e in m.skeleton.envelopes:
            draw_envelope(sh, e)
        if parts_svg.get(view):
            inner, (cu, cv) = parts_svg[view]
            inner = re.sub(r'stroke-width="0\.35"', f'stroke-width="{sh.f(sh.lw * 0.9)}"', inner)
            inner = re.sub(r'stroke-width="0\.18"', f'stroke-width="{sh.f(sh.lw * 0.45)}"', inner)
            sh.raw("parts", f'<g transform="translate({sh.f(cu)},{sh.f(-cv)})" data-ref="assembly">{inner}</g>')
            if parts_bbox:
                pu0, pv0, pu1, pv1 = project_box(view, *parts_bbox)
                sh._bb((pu0, pv0), (pu1, pv1))
        for d in m.skeleton.datums:
            draw_datum(sh, d, ext)
        for i in m.skeleton.interfaces:
            draw_interface(sh, i, m, ext)
        sh.base = tuple(sh.bb)  # размеры — снаружи всего нарисованного
        loads = draw_loads(sh, m, at3)
        auto_dims(sh, m)
        n_marks = draw_marks(sh, marks or [])
        sub = s["title"] + (", детали собранного варианта тонкой линией" if parts_svg.get(view) else "")
        if n_marks:
            sub += f"; пометок конструктора: {n_marks}"
        svg = sh.emit(f"{title} — компоновка", sub, legend)
        file = f"{prefix}_layout_{view}.svg"
        (out / file).write_text(svg, encoding="utf-8")
        png_file = None
        if png:
            try:
                from skelcad.render import svg_to_png

                png_file = f"{prefix}_layout_{view}.png"
                (out / png_file).write_bytes(svg_to_png(svg, 1400))
            except Exception as e:  # noqa: BLE001 — без растеризатора остаётся SVG
                png_file = None
                notes.append(f"PNG вида {view} не получен: {e}")
        (ua, us), (va, vs) = s["u"], s["v"]
        da = s["depth"]
        res["views"][view] = {
            "svg": file,
            "png": png_file,
            "viewBox": sh.viewbox,
            "u": [AXES[ua], us],
            "v": [AXES[va], vs],
            "depth": [AXES[da], round((lo3[da] + hi3[da]) / 2, 1)],
            "title": s["title"],
            "marks": n_marks,
        }
        res["dims"] += sh.dims
        if not res["loads"]:
            res["loads"] = loads
    (out / f"{prefix}_layout.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res
