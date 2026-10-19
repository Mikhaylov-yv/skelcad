"""Инструменты сервера: проекты в git, запросы к модели через воркер, сборка, проверки, сравнение."""

from __future__ import annotations

from pathlib import Path

import pytest

from skelcad.server.tools import Tools, local_server
from skelcad.server.workspace import WorkspaceError


@pytest.fixture(scope="module")
def tools(tmp_path_factory) -> Tools:
    data = tmp_path_factory.mktemp("data")
    srv = local_server(data)
    srv.workspace.seed(["bracket"])
    return Tools(srv)


def test_project_list_and_read(tools: Tools):
    r = tools.project_list()
    assert [p["name"] for p in r["projects"]] == ["bracket"]
    assert "bracket" in r["templates"] and "pipe_support" in r["templates"]
    r = tools.project_read("bracket")
    assert r["spec"]["id"] == "bracket"
    assert [v["id"] for v in r["variants"]] == ["A_fork", "B_hub", "C_box"]
    assert "generators/bracket.py" in r["files"]
    assert tools.project_read("bracket", "skeleton")["data"]["datums"]


def test_create_empty_and_bad_names(tools: Tools):
    r = tools.project_create("new_one", "empty", client="test")
    assert r["project"]["name"] == "new_one"
    assert r["project"]["last_commit"]["author"] == "SkelCAD agent (test)"
    with pytest.raises(WorkspaceError):
        tools.project_create("Bad Name")
    with pytest.raises(WorkspaceError):
        tools.project_create("new_one")


def test_model_query(tools: Tools):
    r = tools.model_query("bracket", "A_fork")
    assert "base_plate" in r["data"]["parts"]
    r = tools.model_query("bracket", "A_fork", "parts[id=base_plate].holes")
    assert isinstance(r["data"], list) and r["data"][0]["purpose"] == "anchor"
    r = tools.model_query("bracket", "A_fork", "skeleton.interfaces[kind=shaft_seat]")
    assert r["data"]["id"] == "axle"
    with pytest.raises(Exception, match="нет ключа"):
        tools.model_query("bracket", "A_fork", "nothing")


def test_files_write_history_revert(tools: Tools):
    before = tools.files_read("bracket", "variants/A_fork.yaml")["content"]
    r = tools.files_write(
        "bracket",
        {"variants/A_fork.yaml": before.replace("gap: 100", "gap: 120")},
        "щёки шире: gap 120",
        client="claude-code",
    )
    assert r["files"] == ["variants/A_fork.yaml"]
    assert r["commit"]["author"] == "SkelCAD agent (claude-code)"
    h = tools.history("bracket", limit=5)
    assert h["commits"][0]["message"] == "щёки шире: gap 120"
    assert h["commits"][0]["files"] == ["variants/A_fork.yaml"]
    # модель видит изменение
    gap = tools.model_query("bracket", "A_fork", "derived")["data"]
    assert gap  # derived не пуст
    # повторная запись того же содержимого — ошибка «нет изменений»
    with pytest.raises(WorkspaceError, match="не изменилось"):
        tools.files_write("bracket", {"variants/A_fork.yaml": before.replace("gap: 100", "gap: 120")}, "повтор")
    r = tools.revert("bracket", h["commits"][0]["commit"], client="claude-code")
    assert tools.files_read("bracket", "variants/A_fork.yaml")["content"] == before
    assert tools.history("bracket", limit=1)["commits"][0]["message"].startswith("Revert")
    # пути вне проекта и служебные
    for bad in ("../x.yaml", "/etc/passwd", ".git/config", "out/report.json"):
        with pytest.raises(WorkspaceError):
            tools.files_write("bracket", {bad: "x"}, "bad")


def test_context(tools: Tools):
    assert "gost" in tools.standards_list()["summary"]
    t = tools.context_tables("bracket")["tables"]
    assert "fasteners" in t and "M16" in t["fasteners"]["keys"]
    assert tools.context_lookup("bracket", "anchors", "M16")["record"]["N_Rd"] > 0
    hits = tools.context_search("bracket", "M20")["hits"]
    assert {h["table"] for h in hits} >= {"fasteners", "anchors"}


def test_check_and_build_and_compare(tools: Tools):
    r = tools.check("bracket", "A_fork")
    v = r["variants"]["A_fork"]
    assert v["counts"]["error"] == 0 and v["counts"]["warning"] >= 1
    assert any(c["id"] == "anchor_NV" for c in v["calc"])
    g = tools.check("bracket", "A_fork", scope="geometry", all=True)["variants"]["A_fork"]
    assert g["findings"] and not g["calc"]

    r = tools.build("bracket", "A_fork")
    b = r["variants"][0]
    assert b["summary"]["mass_kg"] > 0
    assert b["files"]["gltf"].startswith("http") and "/out/bracket/A_fork/" in b["files"]["gltf"]
    out = tools.srv.workspace.out_dir / "bracket" / "A_fork"
    assert (out / "report.json").exists() and (out / "model.yaml").exists()
    # out вне git проекта
    assert not (tools.ws.path("bracket") / "out").exists()

    r = tools.compare("bracket", ["A_fork", "B_hub"])
    assert r["variants"] == ["A_fork", "B_hub"]
    mass = next(x for x in r["rows"] if x["metric"].startswith("Масса"))
    assert set(mass["values"]) == {"A_fork", "B_hub"} and mass["best"]
    assert Path(tools.srv.workspace.out_dir / "bracket" / "compare.html").exists()


def test_worker_error_is_reported(tools: Tools):
    tools.project_create("broken", "bracket", client="test")
    gen = tools.files_read("broken", "generators/bracket.py")["content"]
    broken = gen + "\nraise RuntimeError('сломано')\n"
    tools.files_write("broken", {"generators/bracket.py": broken}, "ломаем генератор")
    with pytest.raises(Exception, match="сломано"):
        tools.model_query("broken", "A_fork")
