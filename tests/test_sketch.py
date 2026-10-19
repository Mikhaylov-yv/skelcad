"""Эскиз варианта с размерами по модели (M2.1, D18): правила размеров на трёх пилотах, раздел sketch
(hide, явные размеры), эскиз в комплекте сборки и у инструмента агента."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from skelcad.core.model import SketchDim, SketchSpec
from skelcad.core.project import ProjectDir
from skelcad.geom import generate
from skelcad.geom.sketch import point_of, write_sketch
from skelcad.pipeline import build_variant
from skelcad.server.tools import Tools, local_server

ROOT = Path(__file__).resolve().parent.parent


def _dims(res: dict, view: str) -> dict[str, str]:
    return {d["id"]: d["text"] for d in res["dims"] if d["view"] == view}


def test_plate_sketch_dims(tmp_path):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(ROOT / "examples" / "plate")
    m = pd.resolve("A_base")
    g = generate(m, pd.ctx)
    res = write_sketch(m, g, tmp_path, "A_base", png=False)
    top = _dims(res, "top")
    assert top["plate.size_X"] == "120" and top["plate.size_Y"] == "60"
    assert top["plate.holes.pitch_X_1"] == "90" and top["plate.holes.pitch_Y_1"] == "30"
    assert top["plate.holes.edge_X"] == "15" and top["plate.holes.edge_Y"] == "15"
    assert top["plate.holes.d8_5"].startswith("4 отв. Ø8.5") and top["plate.corner_radius"] == "R5"
    main = _dims(res, "main")
    assert main["plate.thickness"] == "s10" and main["base-mating"] == "12" and main["overall_Y"] == "60"
    svg = (tmp_path / "A_base_sketch_top.svg").read_text(encoding="utf-8")
    assert 'data-ref="part:plate"' in svg and 'data-ref="dim:plate.holes.pitch_X_1"' in svg
    assert res["views"]["top"]["u"] == ["X", 1.0] and res["entities"] == ["part:plate"]
    assert (tmp_path / "A_base_sketch.json").is_file()


def test_bracket_sketch_dims(tmp_path):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(ROOT / "examples" / "bracket")
    m = pd.resolve("A_fork")
    g = generate(m, pd.ctx)
    res = write_sketch(m, g, tmp_path, "A_fork", png=False)
    left = _dims(res, "left")
    assert left["base_plate.holes.pitch_X_1"] == "180" and left["base_plate.holes.pitch_Z_1"] == "200"
    assert left["fasteners.M16"].startswith("4 × M16") and left["cheek_L.thickness"] == "s12"
    main = _dims(res, "main")
    assert main["wall-axle_axis"] == "200" and main["overall_Y"] == "250"
    assert "cheek_L.holes.edge_Y" not in main  # одиночная расточка привязана скелетом, кромка не нужна
    assert main["cheek_L.holes.d50"].startswith("Ø50H8")


def test_sketch_spec_hide_and_explicit(tmp_path):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(ROOT / "examples" / "pipe_support")
    m = pd.resolve("A_tube")
    g = generate(m, pd.ctx)
    m.sketch = SketchSpec(
        views=["main"],
        hide=["guide_L.thickness", "guide_R.thickness"],
        dims=[
            SketchDim(view="main", between=["datum:floor", "part:top_plate"], axis="Z", text="h"),
            SketchDim(of="part:post", kind="diameter"),
        ],
    )
    res = write_sketch(m, g, tmp_path, "A_tube", png=False)
    assert list(res["views"]) == ["main"]
    main = _dims(res, "main")
    assert "guide_L.thickness" not in main and main["post.length"] == "322" and main["post.section"] == "Ø76×6"
    assert main["dim.1"] == "h" and main["dim.2"] == "Ø76×6"
    assert point_of(m, g, "part:base_plate/hole:a00") is not None and point_of(m, g, "point:1,2,3") == (1, 2, 3)
    assert point_of(m, g, "part:nope") is None


def test_sketch_in_build_and_tool(tmp_path):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(ROOT / "examples" / "plate")
    r = build_variant(pd, "B_wide", tmp_path / "out", export=True)
    assert (
        set(r["files"]["sketch"]) == {"main", "left", "top"}
        and r["files"]["sketch_json"] == "B_wide/B_wide_sketch.json"
    )
    sj = json.loads((tmp_path / "out" / r["files"]["sketch_json"]).read_text(encoding="utf-8"))
    assert _dims(sj, "top")["plate.size_X"] == "160"
    assert any(f["code"] == "C-KEEP-IN" for f in r["findings"])  # широкая планка выходит за отведённое место
    srv = local_server(tmp_path / "data")
    srv.workspace.seed(["plate"])
    tools = Tools(srv)
    res = tools.render_sketch("plate", "A_base", "top")
    assert res["png_base64"] and "plate.holes.pitch_X_1 = 90" in res["summary"]
    assert tools.sketch("plate", "A_base")["key"] == res["sketch"]["commit"] + "-A_base"
    spec = yaml.safe_load((ROOT / "examples" / "plate" / "project.yaml").read_text("utf-8"))
    assert "sketch" not in spec  # по умолчанию раздел не нужен


def test_compare_rows_dims_and_params(tmp_path):
    """Сравнение (D19): различающиеся размеры из <v>_sketch.json и параметры вариантов."""
    pytest.importorskip("skelcad_std_gost")
    from skelcad.server import api

    srv = local_server(tmp_path / "data")
    srv.workspace.seed(["plate"])
    tools = Tools(srv)
    tools.build("plate")
    res = api.compare(tools, srv.workspace.out_dir, "plate")
    assert [v["id"] for v in res["variants"]] == ["A_base", "B_wide"]
    assert res["variants"][0]["sketch"]["top"].endswith("A_base_sketch_top.svg")
    assert res["variants"][0]["sketch_views"]["top"]["u"] == ["X", 1.0]
    dims = {r["id"]: r["values"] for r in res["dim_rows"]}
    assert dims["plate.holes.pitch_X_1"] == {"A_base": "90", "B_wide": "120"}
    assert dims["overall_X"] == {"A_base": "120", "B_wide": "160"}
    params = {r["path"]: r["values"] for r in res["param_rows"]}
    assert params["plate.length"] == {"A_base": 120, "B_wide": 160} and "material" not in params
