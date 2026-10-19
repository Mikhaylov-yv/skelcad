"""Пример bracket даёт те же числа, что пилот Kronshteqin (контроль переноса)."""

import pytest

from skelcad.core.project import ProjectDir
from skelcad.pipeline import build_variant

# из out/<variant>/report.json пилота (2026-10-11): масса, габарит, длина швов, K_min, замечания
# info: +2 с M2.1 — R-LAYOUT (компоновка не согласована) и C-SURROUND (обстановка не задета)
PILOT = {
    "A_fork": (15.33, [270, 250, 290], 848, 1.14, {"error": 0, "warning": 3, "info": 29}),
    "B_hub": (14.05, [240, 238, 290], 1166, 1.14, {"error": 0, "warning": 3, "info": 27}),
    "C_box": (18.6, [270, 253, 290], 1911, 1.14, {"error": 0, "warning": 1, "info": 23}),
}


@pytest.fixture(scope="module")
def reports(bracket_dir, tmp_path_factory):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(bracket_dir)
    out = tmp_path_factory.mktemp("out")
    return {v: build_variant(pd, v, out, export=False) for v in PILOT}


@pytest.mark.parametrize("variant", list(PILOT))
def test_matches_pilot(reports, variant):
    mass, env, welds, kmin, counts = PILOT[variant]
    s = reports[variant]["summary"]
    assert s["mass_kg"] == pytest.approx(mass, abs=0.01)
    assert s["envelope_mm"] == env
    assert s["weld_length_mm"] == welds
    assert s["K_min"] == pytest.approx(kmin, abs=0.005)
    assert s["findings"] == counts


def test_report_shape(reports):
    r = reports["A_fork"]
    assert r["standards"] == ["gost"]
    assert {p["role"] for p in r["parts"]} == {"base_plate", "cheek"}
    assert any(m["id"] == "anchors" for m in r["metrics"])
    assert any(a["id"] == "G0" for a in r["assumptions"]) and any(a["id"] == "V1" for a in r["assumptions"])
