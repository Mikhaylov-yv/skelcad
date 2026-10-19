"""diff между коммитами: сущности, геометрия, сводка, замечания."""

from __future__ import annotations

import pytest

from skelcad.server.tools import Tools, local_server
from skelcad.server.workspace import WorkspaceError


@pytest.fixture(scope="module")
def tools(tmp_path_factory) -> Tools:
    srv = local_server(tmp_path_factory.mktemp("data"))
    srv.workspace.seed(["bracket"])
    return Tools(srv)


def test_diff_after_param_change(tools: Tools):
    before = tools.files_read("bracket", "variants/A_fork.yaml")["content"]
    assert "cheek_thickness: 12" in before
    tools.files_write(
        "bracket", {"variants/A_fork.yaml": before.replace("cheek_thickness: 12", "cheek_thickness: 16")}, "щёки 16 мм"
    )
    r = tools.diff("bracket", "A_fork")  # HEAD~1 -> HEAD
    assert "→" in r["summary"]
    parts = r["entities"]["parts"]
    cheeks = [p for p in parts["changed"] if p != "base_plate"]
    assert len(cheeks) == 2 and "thickness" in parts["changed"][cheeks[0]]
    assert parts["changed"][cheeks[0]]["thickness"] == [12, 16]
    g = r["geometry"][cheeks[0]]
    assert g["d_volume_mm3"] > 0 and g["added_mm3"] > 0
    assert r["summary"].count("mass_kg") == 1 and "→" in r["summary"]
    # то же в обратную сторону — явные хеши
    h = tools.history("bracket", limit=2)["commits"]
    back = tools.diff("bracket", "A_fork", h[0]["commit"], h[1]["commit"])
    assert back["entities"]["parts"]["changed"][cheeks[0]]["thickness"] == [16, 12]
    # снимок закэширован вне проекта
    assert (tools.srv.workspace.root / "snapshots" / "bracket").is_dir()
    with pytest.raises(WorkspaceError, match="нет коммита"):
        tools.diff("bracket", "A_fork", "deadbeef", "HEAD")


def test_diff_identical(tools: Tools):
    r = tools.diff("bracket", "B_hub", "HEAD", "HEAD")
    assert "различий" in r["summary"] and not r["entities"] and not r["geometry"]
