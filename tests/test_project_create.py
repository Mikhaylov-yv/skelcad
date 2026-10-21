"""Создание проекта из рабочего места: POST /api/projects (пустой или из шаблона, название изделия,
коммит от имени конструктора), шаблоны с названиями в /api/projects, ошибки словами."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from skelcad.server.app import create_app
from skelcad.server.tools import local_server

USER = {"X-Forwarded-Preferred-Username": "petrov", "X-Forwarded-Email": "p@x"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_SEED", "plate")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    app = create_app(local_server(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


def test_http_project_create(client: TestClient, tmp_path: Path):
    lst = client.get("/api/projects", headers=USER).json()
    assert {"id": "plate", "title": "Планка с 4 резьбовыми отверстиями M10"} in lst["templates"]
    # пустой проект с названием — первый коммит от конструктора
    r = client.post("/api/projects", json={"name": "pump_support", "title": "Опора насоса"}, headers=USER)
    assert r.status_code == 200, r.text
    p = r.json()["project"]
    assert p["name"] == "pump_support" and p["title"] == "Опора насоса" and p["variants"] == []
    assert p["last_commit"]["author"] == "petrov"
    assert p["last_commit"]["message"] == "Проект pump_support «Опора насоса»"
    spec = yaml.safe_load((tmp_path / "data" / "projects" / "pump_support" / "project.yaml").read_text("utf-8"))
    assert spec["id"] == "pump_support" and spec["title"] == "Опора насоса" and spec["skeleton"] == {}
    # из шаблона: копия с новым id и названием, варианты шаблона на месте
    r = client.post("/api/projects", json={"name": "plate2", "title": "Планка-2", "template": "plate"}, headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["project"]["title"] == "Планка-2" and r.json()["project"]["variants"]
    spec = yaml.safe_load((tmp_path / "data" / "projects" / "plate2" / "project.yaml").read_text("utf-8"))
    assert spec["id"] == "plate2" and spec["title"] == "Планка-2"
    names = [p["name"] for p in client.get("/api/projects", headers=USER).json()["projects"]]
    assert names == ["plate", "plate2", "pump_support"]
    # ошибки словами: имя, повтор, шаблон
    assert "имя проекта" in client.post("/api/projects", json={"name": "Bad Name"}, headers=USER).json()["error"]
    assert "уже есть" in client.post("/api/projects", json={"name": "plate"}, headers=USER).json()["error"]
    r = client.post("/api/projects", json={"name": "x1", "template": "nope"}, headers=USER)
    assert r.status_code == 400 and "нет шаблона" in r.json()["error"]
    assert client.post("/api/projects", json={"name": "x2"}).status_code == 401
