"""Сборка без экспорта не теряет ссылки на артефакты прошлой сборки (3D в workbench после build export=False)."""

import json

import pytest

from skelcad.core.project import ProjectDir
from skelcad.pipeline import build_variant, previous_files


def test_build_without_export_keeps_artifact_links(tmp_path, bracket_dir):
    pytest.importorskip("skelcad_std_gost")
    pd = ProjectDir(bracket_dir)
    out = tmp_path / "out"
    assert previous_files(out / "A_fork") is None

    r1 = build_variant(pd, "A_fork", out, export=True)
    assert r1["exported"] and r1["files"]["gltf"] == "A_fork/A_fork.glb" and r1["files"]["svg"]["top"]

    r2 = build_variant(pd, "A_fork", out, export=False)
    assert not r2["exported"]
    assert r2["files"] == r1["files"]
    on_disk = json.loads((out / "A_fork" / "report.json").read_text(encoding="utf-8"))
    assert on_disk["files"]["gltf"] == r1["files"]["gltf"] and on_disk["exported"] is False

    # удалённый артефакт из ссылок выпадает, остальные остаются
    (out / r1["files"]["gltf"]).unlink()
    r3 = build_variant(pd, "A_fork", out, export=False)
    assert "gltf" not in r3["files"] and r3["files"]["svg"] == r1["files"]["svg"]


def test_previous_files_ignores_broken_report(tmp_path):
    out = tmp_path / "v"
    out.mkdir()
    (out / "report.json").write_text("{not json", encoding="utf-8")
    assert previous_files(out) is None
    (out / "report.json").write_text(json.dumps({"files": {"gltf": "v/missing.glb", "svg": {}}}), encoding="utf-8")
    assert previous_files(out) is None
