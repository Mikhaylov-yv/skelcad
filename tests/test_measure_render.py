"""Измерения и рендер на примере bracket (напрямую, без воркера) и через инструменты."""

from __future__ import annotations

import pytest

from skelcad.core.project import ProjectDir
from skelcad.geom.generator import generate
from skelcad.measure import measure
from skelcad.render import render, render_svg
from skelcad.server.tools import Tools, local_server


@pytest.fixture(scope="module")
def mg(bracket_dir):
    pd = ProjectDir(bracket_dir)
    m = pd.resolve("A_fork")
    return pd, m, generate(m, pd.ctx)


def test_measure_ops(mg):
    pd, m, g = mg
    lst = measure(m, g, pd.ctx, "list")
    assert "base_plate" in lst["parts"] and "axle" in lst["bodies"]
    mass = measure(m, g, pd.ctx, "mass")
    assert mass["total_kg"] == pytest.approx(sum(mass["parts_kg"].values()), abs=0.01)
    assert measure(m, g, pd.ctx, "mass", {"a": "part:base_plate"})["mass_kg"] > 1
    cog = measure(m, g, pd.ctx, "cog")
    assert len(cog["cog"]) == 3 and cog["mass_kg"] == pytest.approx(mass["total_kg"], abs=0.01)
    bb = measure(m, g, pd.ctx, "bbox")
    assert bb["size"][2] > 200
    cheeks = [p for p in lst["parts"] if p != "base_plate"]
    d = measure(m, g, pd.ctx, "distance", {"a": f"part:{cheeks[0]}", "b": f"part:{cheeks[1]}"})
    assert d["distance_mm"] == pytest.approx(100, abs=1)  # gap: 100 между щеками
    t = measure(m, g, pd.ctx, "clearance", {"a": "part:base_plate", "b": f"part:{cheeks[0]}"})
    assert t["distance_mm"] == 0 and t.get("touching")  # щека стоит на плите
    inter = measure(m, g, pd.ctx, "interference", {"a": "body:axle", "b": f"part:{cheeks[0]}"})
    assert inter["interferes"] is False  # ось в расточке с зазором
    sec = measure(m, g, pd.ctx, "section", {"a": "part:base_plate", "origin": [0, 8, 0], "normal": [0, 1, 0]})
    assert sec["area_mm2"] > 10000
    part = measure(m, g, pd.ctx, "part", {"a": "base_plate"})
    assert part["valid"] and part["model"]["thickness"] == 16
    with pytest.raises(KeyError, match="нет тела"):
        measure(m, g, pd.ctx, "bbox", {"a": "nope"})
    with pytest.raises(ValueError, match="неизвестная операция"):
        measure(m, g, pd.ctx, "zzz")


def test_render_views(mg, tmp_path):
    pd, m, g = mg
    svg = render_svg(g.assembly(m), "iso")
    assert svg.startswith("<?xml") or "<svg" in svg
    r = render(m, g, "main", tmp_path / "A_fork", highlight="part:base_plate")
    assert r["png_base64"] and (tmp_path / "A_fork" / "views").glob("*.png")
    assert "highlight" in (tmp_path / "A_fork" / "views" / "A_fork_main_part-base_plate.svg").read_text()
    with pytest.raises(ValueError, match="вид"):
        render_svg(g.assembly(m), "back")


def test_tools_measure_render(tmp_path_factory):
    srv = local_server(tmp_path_factory.mktemp("data"))
    srv.workspace.seed(["bracket"])
    t = Tools(srv)
    r = t.measure("bracket", "A_fork", "bbox", {"a": "assembly"})
    assert r["result"]["size"]
    r = t.render("bracket", "A_fork", "iso")
    assert r["links"]["png"].endswith("/out/bracket/A_fork/views/A_fork_iso.png") and r["png_base64"]
