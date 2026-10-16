"""Второй класс изделий (опора под трубопровод) строится теми же модулями ядра — критерий M0."""

import pytest

from skelcad.core.project import ProjectDir
from skelcad.pipeline import build_variant

ROLES = {"base_plate", "post", "top_plate", "guide"}


@pytest.fixture(scope="module")
def reports(tmp_path_factory):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(__import__("pathlib").Path(__file__).resolve().parent.parent / "examples" / "pipe_support")
    out = tmp_path_factory.mktemp("out")
    return {v: build_variant(pd, v, out, export=False) for v in ("A_tube", "B_plates")}


@pytest.mark.parametrize("variant", ["A_tube", "B_plates"])
def test_builds_without_errors(reports, variant):
    r = reports[variant]
    assert r["summary"]["findings"]["error"] == 0, [f["message"] for f in r["findings"] if f["level"] == "error"]
    assert {p["role"] for p in r["parts"]} == ROLES
    assert r["summary"]["mass_kg"] > 5 and r["summary"]["envelope_mm"][2] == 406
    assert r["summary"]["K_min"] > 1.5
    assert r["mount_plane"] == {"origin": [0.0, 0.0, 0.0], "normal": [0.0, 0.0, 1.0]}


def test_core_checks_cover_new_product(reports):
    """Общие проверки ядра отработали на новом классе изделия: тело трубы касается верхней плиты, ключ проходит."""
    codes = {f["code"]: f for f in reports["A_tube"]["findings"]}
    assert "C-BODY" in codes and "top_plate" in codes["C-BODY"]["message"]
    assert codes["C-WRENCH"]["level"] == "info" and codes["R-WRENCH"]["level"] == "info"
    assert codes["C-INTERFERE"]["level"] == "info"


def test_variant_b_has_design_warnings(reports):
    """Пластинчатая стойка: гибкая свободная кромка и швы в узкой щели — правила это видят."""
    warn = {f["code"] for f in reports["B_plates"]["findings"] if f["level"] == "warning"}
    assert {"R-FREE-EDGE", "R-WELD-ACCESS"} <= warn
