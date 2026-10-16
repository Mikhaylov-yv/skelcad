"""SVG-проекции: главный вид, вид слева, вид сверху (метод первого угла).

Направления взгляда заданы в глобальной системе координат проекта:
главный вид — вдоль −X, вид слева — вдоль −Y (со стороны +Y), вид сверху — вдоль −Z.
"""

from __future__ import annotations

from pathlib import Path

import build123d as bd

DIST = 3000
VIEWS = {
    # имя: (точка взгляда относительно центра, «верх» вида)
    "main": ((-DIST, 0, 0), (0, 0, 1)),
    "left": ((0, DIST, 0), (0, 0, 1)),
    "top": ((0, 0, DIST), (0, 1, 0)),
}


def write_views(shape: bd.Shape, out: Path, prefix: str) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    c = shape.bounding_box().center()
    files = {}
    for name, (eye, up) in VIEWS.items():
        origin = (c.X + eye[0], c.Y + eye[1], c.Z + eye[2])
        visible, hidden = shape.project_to_viewport(origin, up, look_at=(c.X, c.Y, c.Z))
        exp = bd.ExportSVG(margin=5, line_weight=0.35)
        exp.add_layer("hidden", line_color=(130, 130, 130), line_weight=0.18, line_type=bd.LineType.ISO_DASH)
        exp.add_layer("visible", line_color=(20, 20, 20), line_weight=0.35)
        exp.add_shape(hidden, layer="hidden")
        exp.add_shape(visible, layer="visible")
        f = out / f"{prefix}_{name}.svg"
        exp.write(f)
        files[name] = f.name
    return files
