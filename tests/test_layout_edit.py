"""Правка компоновки с эскиза (M2.3 шаг 2): поля сущностей в тексте project.yaml на месте (flow и блочный стиль,
комментарии целы), проверки значений, размер числом, коммит конструктора через API и состояние согласования."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from skelcad.server import layout_edit as E
from skelcad.server.app import create_app
from skelcad.server.tools import local_server
from skelcad.server.workspace import Actor

ROOT = Path(__file__).resolve().parent.parent
BRACKET = (ROOT / "examples" / "bracket" / "project.yaml").read_text(encoding="utf-8")

BLOCK = """id: t
title: t
skeleton:
  datums:
    - id: wall          # лицевая плоскость
      kind: plane
      origin: [0, 0, 0]   # мм
      direction: [0, 1, 0]
    - id: axle
      kind: axis
      origin:
        - 0
        - 200
        - 0
      direction: [1, 0, 0]
  interfaces:
    - id: axle
      kind: shaft_seat
      datum: axle
      body:
        center: [0, 200, 0]
        axis: [1, 0, 0]
        diameter: 50
        length: 300
    - id: pipe
      kind: pipe_rest
      datum: axle
      body: {center: [0, 400, 0], axis: [1, 0, 0], diameter: 108, length: 300}  # труба
  envelopes:
    - {id: zone, kind: keep_in, min: [-100, 0, -100], max: [100, 300, 100], name: "объём"}
  surroundings:
    - {id: pipe_body, kind: cylinder, role: pipe, center: [0, 400, 0], axis: [1, 0, 0], diameter: 108, length: 500}
    - {id: box1, kind: box, role: equipment, min: [200, 0, 0], max: [300, 100, 100]}
"""


def test_flow_item_edit_keeps_comments_and_order():
    new, applied = E.apply_edits(
        BRACKET, [{"ref": "surrounding:wall_body", "set": {"extent": 400, "origin": [0, -5.0, 0]}}]
    )
    assert applied == ["surrounding:wall_body extent 300 → 400", "surrounding:wall_body origin [0, 0, 0] → [0, -5, 0]"]
    assert "# обстановка: тела вокруг изделия" in new and "params: {concrete: B25, anchor_size: M16}" in new
    spec = yaml.safe_load(new)
    wb = spec["skeleton"]["surroundings"][0]
    assert wb["extent"] == 400 and wb["origin"] == [0, -5, 0] and wb["material"] == "бетон B25"
    assert len(new.split("\n")) == len(BRACKET.split("\n"))  # правка на месте: число строк то же
    new2, _ = E.apply_edits(BRACKET, [{"ref": "datum:axle_axis", "set": {"origin": [0, 250, 0]}}])
    line = '- {id: axle_axis, kind: axis, origin: [0, 250, 0], direction: [1, 0, 0], name: "Ось вала (вылет 200)"}'
    assert line in new2


def test_block_item_edit_scalar_flow_and_nested():
    new, applied = E.apply_edits(
        BLOCK,
        [
            {"ref": "datum:wall", "set": {"origin": [0, 10, 0]}},
            {"ref": "interface:axle", "set": {"body.diameter": 60, "body.center": [0, 210, 0]}},
            {"ref": "interface:pipe", "set": {"body.length": 350}},
            {"ref": "envelope:zone", "set": {"max": [100, 320, 100]}},
            {"ref": "surrounding:box1", "set": {"min": [210, 0, 0]}},
        ],
    )
    assert "      origin: [0, 10, 0]   # мм" in new  # комментарий и пробелы на месте
    assert "        diameter: 60\n" in new and "        center: [0, 210, 0]\n" in new
    assert "body: {center: [0, 400, 0], axis: [1, 0, 0], diameter: 108, length: 350}  # труба" in new
    assert "# лицевая плоскость" in new
    spec = yaml.safe_load(new)
    assert spec["skeleton"]["envelopes"][0]["max"] == [100, 320, 100]
    assert spec["skeleton"]["surroundings"][1]["min"] == [210, 0, 0]
    assert len(applied) == 6
    # origin в блочном списке (строки «- 0») на месте не правится: файл переписывается, значение верное
    new2, _ = E.apply_edits(BLOCK, [{"ref": "datum:axle", "set": {"origin": [0, 220, 0]}}])
    assert yaml.safe_load(new2)["skeleton"]["datums"][1]["origin"] == [0, 220, 0]


def test_validation_errors():
    with pytest.raises(E.LayoutEditError, match="не правится"):
        E.apply_edits(BRACKET, [{"ref": "datum:wall", "set": {"direction": [1, 0, 0]}}])
    with pytest.raises(E.LayoutEditError, match="три числа"):
        E.apply_edits(BRACKET, [{"ref": "datum:wall", "set": {"origin": [1, 2]}}])
    with pytest.raises(E.LayoutEditError, match="больше нуля"):
        E.apply_edits(BRACKET, [{"ref": "surrounding:wall_body", "set": {"extent": 0}}])
    with pytest.raises(E.LayoutEditError, match="нет «datum:nope»"):
        E.apply_edits(BRACKET, [{"ref": "datum:nope", "set": {"origin": [0, 0, 0]}}])
    with pytest.raises(E.LayoutEditError, match="нет опорного тела"):
        E.apply_edits(BRACKET, [{"ref": "interface:wall", "set": {"body.diameter": 1}}])
    with pytest.raises(E.LayoutEditError, match="не изменились"):
        E.apply_edits(BRACKET, [{"ref": "datum:wall", "set": {"origin": [0, 0, 0]}}])
    with pytest.raises(E.LayoutEditError, match="min должен быть не больше max"):
        E.apply_edits(BLOCK, [{"ref": "envelope:zone", "set": {"min": [200, 0, 0]}}])
    with pytest.raises(E.LayoutEditError, match="ожидалось"):
        E.apply_edits(BRACKET, [{"ref": "part:base_plate", "set": {"origin": [0, 0, 0]}}])


DIMS = [
    {"id": "wall-axle_axis", "view": "main", "kind": "linear", "axis": "Y", "value": 200, "text": "200",
     "refs": ["datum:wall", "datum:axle_axis"]},
    {"id": "wall-pipe_body", "view": "main", "kind": "linear", "axis": "Y", "value": 346, "text": "346",
     "refs": ["datum:wall", "surrounding:pipe_body"]},
    {"id": "d", "view": "main", "kind": "callout", "axis": "", "value": None, "text": "Ø50",
     "refs": ["interface:axle"]},
]  # fmt: skip


def test_dim_edit_moves_second_entity_along_axis():
    spec_b = yaml.safe_load(BRACKET)
    edits, what = E.dim_edits(spec_b, DIMS, "wall-axle_axis", 250)
    assert edits == [{"ref": "datum:axle_axis", "set": {"origin": [0.0, 250.0, 0.0]}}]
    assert "сдвиг datum:axle_axis на 50 по Y" in what
    spec_c = yaml.safe_load(BLOCK)
    edits, _ = E.dim_edits(spec_c, DIMS, "wall-pipe_body", 300)
    assert edits == [{"ref": "surrounding:pipe_body", "set": {"center": [0.0, 354.0, 0.0]}}]  # 346 → 300: сдвиг −46
    with pytest.raises(E.LayoutEditError, match="не линейный"):
        E.dim_edits(spec_c, DIMS, "d", 10)
    with pytest.raises(E.LayoutEditError, match="нет размера"):
        E.dim_edits(spec_c, DIMS, "zzz", 10)
    with pytest.raises(E.LayoutEditError, match="больше нуля"):
        E.dim_edits(spec_c, DIMS, "wall-axle_axis", 0)


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    app = create_app(local_server(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


USER = {"X-Forwarded-Preferred-Username": "petrov", "X-Forwarded-Email": "petrov@x"}


def test_http_edit_commits_as_constructor_and_changes_approval(client: TestClient):
    url = "/api/projects/bracket/layout"
    assert client.post(url + "/approve", headers=USER).status_code == 200
    lay = client.get(url, headers=USER).json()
    assert lay["approval"]["state"] == "approved"
    assert lay["entities"][0]["geom"]["origin"] == [0, 0, 0]  # геометрия для ручек
    body = {"edits": [{"ref": "surrounding:wall_body", "set": {"extent": 350}}]}
    r = client.post(url + "/edit", json=body, headers=USER)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["commit"]["author"] == "petrov"
    assert d["commit"]["message"].startswith("компоновка с эскиза: surrounding:wall_body extent 300 → 350")
    lay = client.get(url, headers=USER).json()
    assert lay["approval"]["state"] == "changed" and "surrounding:wall_body" in lay["approval"]["diff"]["changed"]
    wb = next(e for e in lay["entities"] if e["ref"] == "surrounding:wall_body")
    assert wb["geom"]["extent"] == 350
    # размер числом: вылет оси 200 → 240
    dim = next(x for x in lay["dims"] if x["refs"] == ["datum:wall", "datum:axle_axis"])
    r = client.post(url + "/edit", json={"dim": dim["id"], "value": 240, "message": "вылет 240 по ТЗ"}, headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["commit"]["message"] == "вылет 240 по ТЗ"
    lay = client.get(url, headers=USER).json()
    ax = next(e for e in lay["entities"] if e["ref"] == "datum:axle_axis")
    assert ax["geom"]["origin"] == [0, 240, 0]
    # ошибки словами; пока проект у агента — 409
    bad = {"edits": [{"ref": "datum:wall", "set": {"origin": [0, 0]}}]}
    r = client.post(url + "/edit", json=bad, headers=USER)
    assert r.status_code == 400 and "три числа" in r.json()["error"]
    t = client.post("/api/projects/bracket/tasks", json={"text": "x"}, headers=USER).json()
    body = {"edits": [{"ref": "datum:wall", "set": {"origin": [0, 1, 0]}}]}
    assert client.post(url + "/edit", json=body, headers=USER).status_code == 409
    client.post(f"/api/tasks/{t['id']}/stop", headers=USER)


def test_edit_via_workspace(tmp_path: Path):
    srv = local_server(tmp_path / "data")
    srv.workspace.seed(["bracket"])
    edits = [{"ref": "datum:axle_axis", "set": {"origin": [0, 210, 0]}}]
    res = E.edit(srv.workspace, "bracket", edits, Actor("Иванов", "i@x"))
    assert res["commit"]["author"] == "Иванов" and res["applied"] == [
        "datum:axle_axis origin [0, 200, 0] → [0, 210, 0]"
    ]
    assert "origin: [0, 210, 0]" in srv.workspace.read_file("bracket", "project.yaml")
