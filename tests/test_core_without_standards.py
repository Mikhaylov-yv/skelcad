"""Ядро собирается и работает без единого пакета стандартов (критерий M0)."""

from pathlib import Path

import pytest
import yaml

from skelcad.context import Context, MissingStandardError
from skelcad.core import (
    Hole,
    Outline,
    Placement,
    PlatePart,
    Project,
    TubePart,
    Unit,
    Weld,
    WeldSegment,
)
from skelcad.core.project import ProjectDir
from skelcad.geom import generate
from skelcad.pipeline import build_variant
from skelcad.rules import PluginSet, run_checks, run_rules

X, Y, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def tiny_project() -> Project:
    plate = PlatePart(
        id="plate",
        name={"ru": "Плита", "en": "Plate"},
        role="base",
        material="S235",
        thickness=10,
        outline=Outline(points=[(0, 0), (100, 0), (100, 100), (0, 100)]),
        placement=Placement(origin=(0, 0, 0), u=X, normal=Z),
        holes=[Hole(id="h1", purpose="bolt", diameter=13, center=(20, 20))],
    )
    tube = TubePart(
        id="post",
        name="Стойка",
        role="post",
        material="S235",
        tube_size="40x4",
        od=40,
        wall=4,
        length=200,
        center=(50, 50, 110),
        axis=Z,
    )
    weld = Weld(id="w1", parts=("plate", "post"), leg=4, segments=[WeldSegment(start=(30, 50, 10), end=(70, 50, 10))])
    unit = Unit(id="u", name="Узел", parts=[plate, tube], joints=[weld])
    return Project(id="tiny", title="Стойка на плите", units=[unit])


def test_geometry_and_checks_without_tables():
    ctx = Context()  # ни одного пакета стандарта
    m = tiny_project()
    g = generate(m, ctx)
    assert set(g.parts) == {"plate", "post"}
    assert abs(g.parts["plate"].volume - (100 * 100 * 10 - 3.14159 * 6.5**2 * 10)) < 1.0
    ps = PluginSet.collect(ctx)
    findings = run_checks(ps, m, g, ctx) + run_rules(ps, m, ctx)
    codes = {f.code for f in findings}
    assert "C-INTERFERE" in codes and "C-WELD-CONTACT" in codes
    assert not [f for f in findings if f.level == "error"], [f.message for f in findings if f.level == "error"]
    # масса требует таблицу материалов — её нет
    with pytest.raises(MissingStandardError):
        g.masses(m, ctx)


def test_local_tables_substitute_standard():
    ctx = Context(tables={"materials": {"S235": {"grade": "S235JR", "Ry": 235, "E": 210000, "density": 7850}}})
    m = tiny_project()
    masses = generate(m, ctx).masses(m, ctx)
    assert masses["plate"] > 0 and masses["post"] > 0


def test_unknown_standard_is_explicit():
    with pytest.raises(MissingStandardError):
        Context(standards=["no-such-standard"])


def test_project_dir_without_standards(tmp_path: Path):
    """Полный пайплайн build по проекту с генератором и локальной таблицей материалов."""
    (tmp_path / "generators").mkdir()
    (tmp_path / "generators" / "gen.py").write_text(
        """
from skelcad.core import Outline, Placement, PlatePart, Unit
from skelcad.rules import GenResult

def generate(project, params, ctx):
    t = params["thickness"]
    plate = PlatePart(id="p", name="Плита", material="S235", thickness=t,
                      outline=Outline(points=[(0, 0), (100, 0), (100, 50), (0, 50)]),
                      placement=Placement(origin=(0, 0, 0), u=(1, 0, 0), normal=(0, 0, 1)))
    return GenResult(units=[Unit(id="u", name="Узел", parts=[plate])], derived={"t": t})
""",
        encoding="utf-8",
    )
    (tmp_path / "project.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "p1",
                "title": "Пластина",
                "generator": "generators/gen.py",
                "tables": {"materials": {"S235": {"grade": "S235JR", "Ry": 235, "E": 210000, "density": 7850}}},
                "params": {"thickness": 10},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (tmp_path / "variants").mkdir()
    (tmp_path / "variants" / "thick.yaml").write_text("id: thick\nparams: {thickness: 20}\n", encoding="utf-8")

    pd = ProjectDir(tmp_path)
    assert pd.ctx.standards == {}
    r_base = build_variant(pd, None, tmp_path / "out", export=False)
    r_thick = build_variant(pd, "thick", tmp_path / "out", export=False)
    assert abs(r_base["summary"]["mass_kg"] - 0.39) < 0.01
    assert abs(r_thick["summary"]["mass_kg"] - 0.785) < 0.01
    assert (tmp_path / "out" / "thick" / "model.yaml").exists()
    assert not any(f["level"] == "error" for f in r_thick["findings"])
