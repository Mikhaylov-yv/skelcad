"""Рендер видов для агента: SVG-проекция (видимые и скрытые линии) -> PNG.

Виды: main (вдоль −X), left (со стороны +Y), top (сверху), iso (из октанта −X+Y+Z).
Подсветка: деталь или крепёж по ссылке рисуется отдельным слоем красным.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import build123d as bd

from skelcad.core.model import Project
from skelcad.geom.generator import Geometry

DIST = 3000
VIEWS = {
    "main": ((-DIST, 0, 0), (0, 0, 1)),
    "left": ((0, DIST, 0), (0, 0, 1)),
    "top": ((0, 0, DIST), (0, 1, 0)),
    "iso": ((-DIST, DIST, DIST * 0.8), (0, 0, 1)),
}


def render_svg(shape: bd.Shape, view: str, highlight: bd.Shape | None = None) -> str:
    if view not in VIEWS:
        raise ValueError(f"вид «{view}»; есть: {', '.join(VIEWS)}")
    eye, up = VIEWS[view]
    c = shape.bounding_box().center()
    origin = (c.X + eye[0], c.Y + eye[1], c.Z + eye[2])
    look = (c.X, c.Y, c.Z)
    visible, hidden = shape.project_to_viewport(origin, up, look_at=look)
    exp = bd.ExportSVG(margin=8, line_weight=0.35)
    exp.add_layer("hidden", line_color=0x828282, line_weight=0.18, line_type=bd.LineType.ISO_DASH)
    exp.add_layer("visible", line_color=0x141414, line_weight=0.35)
    exp.add_shape(hidden, layer="hidden")
    exp.add_shape(visible, layer="visible")
    if highlight is not None:
        hv, _ = highlight.project_to_viewport(origin, up, look_at=look)
        exp.add_layer("highlight", line_color=0xC81E1E, line_weight=0.7)
        exp.add_shape(hv, layer="highlight")
    return exp.get_svg_string() if hasattr(exp, "get_svg_string") else _svg_via_file(exp)


def _svg_via_file(exp: bd.ExportSVG) -> str:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        exp.write(f.name)
        return Path(f.name).read_text(encoding="utf-8")


def svg_to_png(svg: str, width: int = 1200) -> bytes:
    import resvg_py

    # build123d пишет размер в мм — resvg хочет безразмерные px; масштаб задаём параметром width
    svg = re.sub(r'width="([\d.]+)mm" height="([\d.]+)mm"', r'width="\1" height="\2"', svg, count=1)
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width, background="white"))


def render(m: Project, g: Geometry, view: str, out: Path, highlight: str | None = None, width: int = 1200) -> dict:
    """SVG и PNG в out/views/, PNG — ещё и base64 для ответа агенту."""
    from skelcad.measure import shape_by_ref

    asm = g.assembly(m, with_purchased=True)
    hl = shape_by_ref(m, g, highlight) if highlight else None
    svg = render_svg(asm, view, hl)
    vdir = out / "views"
    vdir.mkdir(parents=True, exist_ok=True)
    name = f"{m.variant or m.id}_{view}" + (f"_{highlight.replace(':', '-')}" if highlight else "")
    (vdir / f"{name}.svg").write_text(svg, encoding="utf-8")
    try:
        png = svg_to_png(svg, width)
        (vdir / f"{name}.png").write_bytes(png)
        png_b64 = base64.b64encode(png).decode()
    except Exception as e:  # noqa: BLE001 — без растеризатора отдаём SVG
        png_b64 = None
        svg_note = f"PNG не получен ({e}); есть SVG"
    else:
        svg_note = ""
    return {
        "view": view,
        "highlight": highlight,
        "svg": f"{out.name}/views/{name}.svg",
        "png": f"{out.name}/views/{name}.png" if png_b64 else None,
        "png_base64": png_b64,
        "note": svg_note,
        "svg_text": svg if not png_b64 else None,
    }
