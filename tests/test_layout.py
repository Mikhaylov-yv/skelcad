"""Компоновочный эскиз (M2.1, D21): координаты видов, обстановка и зоны в модели, SVG/JSON по трём пилотам,
согласование («Компоновка согласована») и правило R-LAYOUT, проверки обстановки и зон."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from skelcad.context import Context
from skelcad.core import (
    BoxBody,
    Envelope,
    Hole,
    Outline,
    Placement,
    PlatePart,
    Project,
    Skeleton,
    Unit,
)
from skelcad.core.project import ProjectDir, base_project, read_spec
from skelcad.geom import generate
from skelcad.geom.layout import VIEWS, from_view, project_box, to_view, write_layout
from skelcad.rules import PluginSet, run_checks, run_rules
from skelcad.server import layout as L
from skelcad.server.tools import Tools, local_server
from skelcad.server.workspace import Actor

ROOT = Path(__file__).resolve().parent.parent
X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def test_view_mapping_matches_hlr_projection():
    """Координаты эскиза = HLR-координаты build123d + сдвиг центра габарита (по каждому виду)."""
    bd = pytest.importorskip("build123d")
    box = bd.Box(100, 50, 20).moved(bd.Location((1000, 2000, 3000)))
    marker = bd.Box(10, 10, 10).moved(bd.Location((1060, 2035, 3020)))
    shape = bd.Compound(children=[box, marker])
    c = shape.bounding_box().center()
    for view, s in VIEWS.items():
        eye, up = s["eye"], s["up"]
        vis, _ = marker.project_to_viewport((c.X + eye[0], c.Y + eye[1], c.Z + eye[2]), up, look_at=(c.X, c.Y, c.Z))
        hb = bd.Compound(children=vis).bounding_box()
        cu, cv = to_view(view, (c.X, c.Y, c.Z))
        mine = project_box(view, (1055, 2030, 3015), (1065, 2040, 3025))
        assert abs(hb.min.X + cu - mine[0]) < 1e-6 and abs(hb.max.X + cu - mine[2]) < 1e-6, view
        assert abs(hb.min.Y + cv - mine[1]) < 1e-6 and abs(hb.max.Y + cv - mine[3]) < 1e-6, view
        u, v = to_view(view, (1, 2, 3))
        assert from_view(view, u, v, (1, 2, 3)[s["depth"]]) == (1, 2, 3)


def test_surroundings_in_model_and_hash():
    sk = Skeleton.model_validate(
        {
            "datums": [{"id": "wall", "kind": "plane", "origin": [0, 0, 0], "direction": [0, 1, 0]}],
            "surroundings": [
                {"id": "w", "kind": "plane", "origin": [0, 0, 0], "normal": [0, 1, 0], "extent": 300, "thickness": 250},
                {"id": "b", "kind": "box", "role": "equipment", "min": [150, 0, -50], "max": [250, 100, 50]},
                {
                    "id": "c",
                    "kind": "cylinder",
                    "center": [0, 0, 400],
                    "axis": [1, 0, 0],
                    "diameter": 108,
                    "length": 600,
                },
            ],
        }
    )
    assert [b.kind for b in sk.surroundings] == ["plane", "box", "cylinder"]
    assert sk.surroundings[0].bbox() == ((-300.0, -250.0, -300.0), (300.0, 0.0, 300.0))
    lo, hi = sk.surroundings[2].bbox()
    assert lo == (-300.0, -54.0, 346.0) and hi == (300.0, 54.0, 454.0)
    spec = read_spec(ROOT / "examples" / "bracket")
    m = base_project(spec)
    assert m.layout is not None and m.layout.approved is None and len(m.layout.hash) == 12
    assert (
        L.spec_hash(yaml.safe_load((ROOT / "examples" / "bracket" / "project.yaml").read_text("utf-8")))
        == m.layout.hash
    )


@pytest.mark.parametrize(
    "example,variant,dim", [("bracket", "A_fork", "wall-axle_axis"), ("pipe_support", "A_tube", "floor-pipe_axis")]
)
def test_layout_pilots_with_parts(tmp_path, example, variant, dim):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(ROOT / "examples" / example)
    m = pd.resolve(variant)
    g = generate(m, pd.ctx)
    assert set(g.surroundings) == {b.id for b in m.skeleton.surroundings}
    res = write_layout(m, g, tmp_path, variant, png=False)
    assert set(res["views"]) == {"main", "left", "top"} and res["parts"] and not res["notes"]
    ids = {d["id"] for d in res["dims"]}
    assert dim in ids
    svg = (tmp_path / res["views"]["main"]["svg"]).read_text(encoding="utf-8")
    assert 'data-ref="surrounding:' in svg and 'class="parts"' in svg and "компоновка" in svg
    assert any(e["group"] == "surrounding" for e in res["entities"])
    assert res["loads"] and res["loads"][0]["dir"] is not None
    saved = json.loads((tmp_path / f"{variant}_layout.json").read_text(encoding="utf-8"))
    assert saved["views"]["top"]["u"] == ["X", 1.0] and saved["views"]["main"]["u"] == ["Y", -1.0]


def test_layout_without_generator(tmp_path):
    """Компоновка строится по одному project.yaml: ни генератора, ни геометрии ещё нет."""
    (tmp_path / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "demo",
                "title": "Кронштейн под ось на стене",
                "requirements": {"purpose": "опора оси", "loads": {"Fv": 12, "Fh": 3}},
                "skeleton": {
                    "datums": [
                        {"id": "wall", "kind": "plane", "origin": [0, 0, 0], "direction": [0, 1, 0], "name": "Стена"},
                        {"id": "axis", "kind": "axis", "origin": [0, 200, 0], "direction": [1, 0, 0], "name": "Ось"},
                    ],
                    "interfaces": [
                        {"id": "wall", "kind": "mount_plane", "datum": "wall", "params": {"anchor_size": "M16"}},
                        {"id": "axle", "kind": "shaft_seat", "datum": "axis", "params": {"d": 50}},
                    ],
                    "envelopes": [
                        {"id": "service", "kind": "keep_out", "min": [-200, 0, -300], "max": [200, 300, -150]}
                    ],
                    "surroundings": [
                        {"id": "wall_body", "kind": "plane", "role": "wall", "origin": [0, 0, 0], "normal": [0, 1, 0]},
                        {
                            "id": "duct",
                            "kind": "box",
                            "role": "equipment",
                            "name": "Короб",
                            "min": [150, 0, -100],
                            "max": [300, 250, 100],
                        },
                    ],
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    m = base_project(read_spec(tmp_path))
    res = write_layout(m, None, tmp_path / "out", "demo", png=False)
    assert not res["parts"]
    dims = {(d["view"], d["id"]): d["value"] for d in res["dims"]}
    assert dims[("main", "wall-axis")] == 200 and dims[("top", "wall-axis")] == 200
    assert dims[("top", "duct-axis")] == 150  # от оси до короба по X
    svg = (tmp_path / "out" / "demo_layout_main.svg").read_text(encoding="utf-8")
    assert 'data-ref="envelope:service"' in svg and 'data-ref="load:Fv"' in svg and 'data-ref="datum:axis"' in svg


def test_checks_surroundings_and_envelopes():
    plate = PlatePart(
        id="plate",
        name="Плита",
        material="S235",
        thickness=10,
        outline=Outline(points=[(0, 0), (100, 0), (100, 100), (0, 100)]),
        placement=Placement(origin=(0, 0, 0), u=X, normal=Z),
        holes=[Hole(id="h1", purpose="bolt", diameter=13, center=(20, 20))],
    )
    sk = Skeleton(
        envelopes=[
            Envelope(id="zone", kind="keep_out", min=(80, 80, 0), max=(200, 200, 50)),
            Envelope(id="place", kind="keep_in", min=(0, 0, 0), max=(90, 150, 50)),
        ],
        surroundings=[BoxBody(id="duct", role="equipment", min=(-50, -50, 5), max=(10, 10, 50))],
    )
    m = Project(id="t", title="t", skeleton=sk, units=[Unit(id="u", name="u", parts=[plate])])
    ctx = Context()
    g = generate(m, ctx)
    ps = PluginSet.collect(ctx)
    codes = {(f.code, f.level) for f in run_checks(ps, m, g, ctx)}
    assert ("C-SURROUND", "error") in codes and ("C-KEEP-OUT", "error") in codes and ("C-KEEP-IN", "warning") in codes
    assert (
        any(f.code == "R-LAYOUT" and f.level == "info" for f in run_rules(ps, m, ctx)) is False
    )  # без layout — нет правила
    m.layout = base_project(read_spec(ROOT / "examples" / "bracket")).layout
    assert [f.level for f in run_rules(ps, m, ctx) if f.code == "R-LAYOUT"] == ["info"]


@pytest.fixture(scope="module")
def tools(tmp_path_factory) -> Tools:
    pytest.importorskip("skelcad_std_gost")
    srv = local_server(tmp_path_factory.mktemp("data"))
    srv.workspace.seed(["plate"])
    return Tools(srv)


def test_layout_tool_and_approval(tools: Tools):
    r = tools.project_read("plate")
    assert r["layout"]["state"] == "none" and "не согласована" in r["summary"]
    res = tools.layout("plate", "A_base")
    assert res["parts"] and res["views"]["top"]["svg_url"].startswith("/out/plate/_layout/")
    assert tools.layout("plate", "A_base")["key"] == res["key"]  # кэш по коммиту
    png = tools.render_layout("plate", "A_base", "top")
    assert png["png_base64"] and "компоновка" in png["summary"] and png["layout"]["dims"] is not None
    # согласование конструктором
    ap = L.approve(tools.ws, "plate", Actor("Иванов", "ivanov@x"))
    assert ap["state"] == "approved" and ap["commit"]["author"] == "Иванов"
    assert "Компоновка согласована" in ap["commit"]["message"]
    assert tools.project_read("plate")["layout"]["state"] == "approved"
    assert tools.layout("plate", "A_base")["key"] != res["key"]  # новый коммит — новый кэш
    # агент меняет скелет → «изменена после согласования», правило даёт предупреждение
    text = (
        tools.files_read("plate", "project.yaml")["content"]
        .replace("extent: 300", "extent: 320")
        .replace("max: [75, 40, 20]", "max: [85, 40, 20]")
    )
    tools.files_write("plate", {"project.yaml": text}, "место под планку шире", client="t")
    st = L.state(tools.ws, "plate")
    assert st["state"] == "changed" and st["diff"]["changed"] == ["envelope:place"] and not st["diff"]["added"]
    chk = tools.check("plate", "A_base", "rules")
    assert any("R-LAYOUT" in f and "после согласования" in f for f in chk["variants"]["A_base"]["findings"])
    # повторное согласование снимает предупреждение
    ap2 = L.approve(tools.ws, "plate", Actor("Иванов", "ivanov@x"))
    assert ap2["state"] == "approved" and L.state(tools.ws, "plate")["state"] == "approved"
    rec = yaml.safe_load(tools.files_read("plate", "layout.yaml")["content"])["approved"]
    assert rec["by"] == "Иванов" and rec["hash"] == ap2["hash"]
    assert "layout:" not in tools.files_read("plate", "project.yaml")["content"]
    # агент переписал project.yaml целиком — отметка в layout.yaml уцелела: состояние «изменена», а не «нет»
    wider = text.replace("max: [85, 40, 20]", "max: [95, 40, 20]")
    tools.files_write("plate", {"project.yaml": wider}, "ещё шире", client="t")
    assert L.state(tools.ws, "plate")["state"] == "changed"
