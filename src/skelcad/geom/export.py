"""Экспорт: STEP по деталям и сборкой, glTF, STL, рецепт построения (manifest.json) для адаптеров САПР."""

from __future__ import annotations

import json
from pathlib import Path

import build123d as bd

from skelcad.context import Context, MissingStandardError
from skelcad.core.model import PlatePart, Project, TubePart, text
from skelcad.geom.generator import Geometry


def _r(v, n=3):
    return [round(x, n) for x in v]


def _bbox(s: bd.Shape) -> dict:
    bb = s.bounding_box()
    return {"min": _r(bb.min), "max": _r(bb.max), "size": _r(bb.size)}


def export_all(m: Project, g: Geometry, ctx: Context, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "step").mkdir(exist_ok=True)
    (out / "stl").mkdir(exist_ok=True)
    name = m.variant or m.id
    files = {"parts_step": {}, "parts_stl": {}}

    for p in m.parts:
        s = g.parts[p.id]
        s.label = f"{name}_{p.id}"
        f = out / "step" / f"{name}_{p.id}.step"
        bd.export_step(s, f)
        files["parts_step"][p.id] = f.relative_to(out.parent).as_posix()
        fs = out / "stl" / f"{name}_{p.id}.stl"
        bd.export_stl(s, fs, tolerance=0.05, angular_tolerance=0.2)
        files["parts_stl"][p.id] = fs.relative_to(out.parent).as_posix()

    asm = g.assembly(m)
    f = out / f"{name}_assembly.step"
    bd.export_step(asm, f)
    files["assembly_step"] = f.relative_to(out.parent).as_posix()
    f = out / f"{name}.glb"
    bd.export_gltf(asm, f, binary=True, linear_deflection=0.05, angular_deflection=0.2)
    files["gltf"] = f.relative_to(out.parent).as_posix()

    manifest = build_manifest(m, g, ctx)
    f = out / "manifest.json"
    f.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    files["manifest"] = f.relative_to(out.parent).as_posix()
    return files


def _grade(ctx: Context, key: str) -> str:
    try:
        return ctx.material(key)["grade"]
    except MissingStandardError:
        return key


def _standard(ctx: Context, table: str) -> str:
    try:
        return ctx.table(table).get("standard", "")
    except MissingStandardError:
        return ""


def build_manifest(m: Project, g: Geometry, ctx: Context) -> dict:
    """Рецепт построения: изделие в терминах нативных элементов САПР (эскиз + вытяжка + отверстия)."""
    lang = m.lang
    masses = {}
    try:
        masses = g.masses(m, ctx)
    except MissingStandardError:
        pass
    parts = []
    for p in m.parts:
        s = g.parts[p.id]
        d = {
            "id": p.id,
            "name": text(p.name, lang),
            "role": p.role,
            "material": _grade(ctx, p.material),
            "mass_kg": round(masses[p.id], 3) if p.id in masses else None,
            "bbox": _bbox(s),
            "note": p.note,
        }
        if isinstance(p, PlatePart):
            pl = p.placement
            d |= {
                "blank": {"type": "sheet", "standard": _standard(ctx, "sheet"), "thickness": p.thickness},
                "feature": "sketch on plane + boss-extrude by thickness along normal",
                "sketch_plane": {
                    "origin": _r(pl.origin),
                    "x_dir": _r(pl.u),
                    "y_dir": _r(pl.v),
                    "normal": _r(pl.normal),
                },
                "outline": {"type": "convex hull of points and circles", **p.outline.model_dump()},
                "holes": [{**h.model_dump(), "center_global": _r(pl.to_global(h.center))} for h in p.holes],
                "trims": [t.model_dump() for t in p.trims],
            }
        elif isinstance(p, TubePart):
            d |= {
                "blank": {
                    "type": "tube",
                    "standard": _standard(ctx, "tubes"),
                    "size": p.tube_size,
                    "od": p.od,
                    "wall": p.wall,
                    "length": p.length,
                },
                "feature": "ring extruded along axis, centred",
                "center": _r(p.center),
                "axis": _r(p.axis),
                "bore": p.bore.model_dump() if p.bore else None,
            }
        parts.append(d)
    return {
        "schema": "skelcad.recipe/0.1",
        "project": m.id,
        "variant": m.variant,
        "title": text(m.title, lang),
        "units": {"length": "mm", "angle": "deg", "mass": "kg", "force": "kN"},
        "coordinate_system": m.coordinate_system,
        "units_of_product": [
            {
                "id": u.id,
                "name": text(u.name, lang),
                "parts": [p.id for p in u.parts],
                "joints": [j.id for j in u.joints],
            }
            for u in m.units
        ],
        "parts": parts,
        "welds": [
            {
                "id": w.id,
                "parts": list(w.parts),
                "type": w.weld_type,
                "leg": w.leg,
                "length": round(w.length, 1),
                "note": w.note,
                "tags": w.tags,
                "segments": [[_r(s.start, 2), _r(s.end, 2)] for s in w.segments],
            }
            for w in m.welds
        ],
        "fasteners": [f.model_dump() for f in m.fasteners],
        "interfaces": [i.model_dump() for i in m.skeleton.interfaces],
    }
