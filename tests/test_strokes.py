"""Росчерки конструктора на компоновочном эскизе (M2.3 шаг 3): хранение в review.yaml, слова для агента,
отрисовка на эскизе (SVG/PNG для агента), API."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from skelcad.server import review as R
from skelcad.server.app import create_app
from skelcad.server.tools import Tools, local_server
from skelcad.server.workspace import Actor

STROKE = {"view": "main", "points": [[0, 210, 40], [0, 260, 60.26], [0, 300, 40], [0, 300, 40]]}


def test_clean_and_describe():
    st = R.clean_stroke(STROKE)
    assert st == {"view": "main", "points": [[0, 210, 40], [0, 260, 60.5], [0, 300, 40]]}  # дубль убран, 0,5 мм
    assert R.describe_stroke(st) == "росчерк на виде main: точек 3, габарит Y=210…300; Z=40…60.5 мм"
    assert R.clean_stroke(None) is None
    with pytest.raises(ValueError, match="view"):
        R.clean_stroke({"view": "iso", "points": [[0, 0, 0], [1, 1, 1]]})
    with pytest.raises(ValueError, match="две точки"):
        R.clean_stroke({"view": "main", "points": [[0, 0, 0]]})
    with pytest.raises(ValueError, match="совпадают"):
        R.clean_stroke({"view": "main", "points": [[0, 0, 0], [0, 0, 0.1]]})


def test_add_stroke_and_render_for_agent(tmp_path: Path):
    srv = local_server(tmp_path / "data")
    srv.workspace.seed(["bracket"])
    t = Tools(srv)
    res = R.add(srv.workspace, "bracket", "здесь мешает труба", Actor("Иванов", "i@x"), variant="A_fork", stroke=STROKE)
    item = res["item"]
    assert item["point"] == [0, 210, 40] and item["stroke"]["view"] == "main" and len(item["stroke"]["points"]) == 3
    assert res["commit"]["message"].startswith("замечание R1 (росчерк)")
    data = yaml.safe_load(srv.workspace.read_file("bracket", "review.yaml"))
    assert data["items"][0]["stroke"]["points"][1] == [0, 260, 60.5]
    lst = t.review_list("bracket")
    assert "[росчерк на виде main: точек 3" in lst["summary"] and lst["items"][0]["stroke"]
    # компоновка: росчерк нарисован на главном виде и не нарисован на виде сверху; PNG есть
    lay = t.layout("bracket", "A_fork")
    assert lay["views"]["main"]["marks"] == 1 and lay["views"]["top"]["marks"] == 0
    d = srv.workspace.out_dir / "bracket" / "_layout" / lay["key"]
    svg = (d / lay["views"]["main"]["svg"]).read_text(encoding="utf-8")
    assert 'data-mark="R1"' in svg and "<polyline" in svg and 'class="marks"' in svg
    png = t.render_layout("bracket", "A_fork", "main")
    assert png["png_base64"] and "пометок конструктора: 1" in (d / lay["views"]["main"]["svg"]).read_text(
        encoding="utf-8"
    )
    # обычная точка без росчерка — кружок с номером
    R.add(srv.workspace, "bracket", "тут", Actor("Иванов", "i@x"), point=[0, 100, 0])
    lay2 = t.layout("bracket", "A_fork")
    assert lay2["views"]["top"]["marks"] == 1 and lay2["views"]["main"]["marks"] == 2
    # закрытое замечание с эскиза уходит
    R.resolve(srv.workspace, "bracket", "R1", "учёл", Actor("agent", "a@x"))
    assert t.layout("bracket", "A_fork")["views"]["main"]["marks"] == 1


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    app = create_app(local_server(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


USER = {"X-Forwarded-Preferred-Username": "petrov", "X-Forwarded-Email": "petrov@x"}


def test_http_review_with_stroke(client: TestClient):
    r = client.post(
        "/api/projects/bracket/review", json={"text": "обвёл", "variant": "A_fork", "stroke": STROKE}, headers=USER
    )
    assert r.status_code == 200, r.text
    it = r.json()["item"]
    assert it["stroke"]["view"] == "main" and it["author"] == "petrov" and it["point"] == [0, 210, 40]
    r = client.get("/api/projects/bracket/review", headers=USER)
    assert r.json()["items"][0]["stroke"]["points"][0] == [0, 210, 40]
    bad = client.post(
        "/api/projects/bracket/review", json={"text": "x", "stroke": {"view": "main", "points": []}}, headers=USER
    )
    assert bad.status_code == 400 and "две точки" in bad.json()["error"]
