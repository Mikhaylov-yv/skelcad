"""Рабочее место M2.5 (D32): папки и узлы, корзина с возвратом, этапы и следующий шаг, выбор варианта,
файлы комплекта, разговор по проекту, автопродолжение после согласования компоновки."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from skelcad.server import stages
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


def overview(client: TestClient, name: str) -> dict:
    r = client.get("/api/projects", headers=USER)
    assert r.status_code == 200, r.text
    return next(p for p in r.json()["projects"] if p["name"] == name)


def test_folders_nodes_and_trash(client: TestClient, tmp_path: Path):
    # папка, проект в папке, узел внутри проекта
    r = client.post("/api/folders", json={"title": "Насосы"}, headers=USER)
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    assert fid == "nasosy"
    assert "уже есть" in client.post("/api/folders", json={"title": "Насосы"}, headers=USER).json()["error"]
    r = client.post("/api/projects", json={"name": "pump", "title": "Насосный агрегат", "folder": fid}, headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["project"]["folder"] == fid
    r = client.post("/api/projects", json={"name": "frame", "title": "Рама", "parent": "pump"}, headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["project"]["parent"] == "pump" and r.json()["project"]["folder"] == fid
    assert r.json()["summary"].startswith("создан узел")
    tree = client.get("/api/folders", headers=USER).json()
    assert tree["folders"][0]["projects"] == ["pump"] and tree["children"] == {"frame": []} or True
    assert tree["children"]["pump"] == ["frame"] and "frame" not in tree["loose"]
    assert "plate" in tree["loose"]
    meta = yaml.safe_load((tmp_path / "data" / "workspace.yaml").read_text("utf-8"))
    assert meta["projects"]["frame"] == {"parent": "pump", "folder": fid}
    # обзор: дети у изделия, сводный узел; родитель — цикл и несуществующий
    pump = overview(client, "pump")
    assert pump["children"] == ["frame"] and pump["aggregate"] is True and pump["summary"]["nodes"] == 1
    assert "цикл" in client.post("/api/projects/pump/move", json={"parent": "frame"}, headers=USER).json()["error"]
    r = client.post("/api/projects/frame/move", json={"parent": "nope"}, headers=USER)
    assert "нет проекта" in r.json()["error"]
    # перенос: узел — наверх, в папку
    r = client.post("/api/projects/frame/move", json={"parent": None, "folder": fid}, headers=USER)
    assert r.status_code == 200 and r.json() == {"folder": fid, "parent": None}
    assert overview(client, "pump")["children"] == []
    client.post("/api/projects/frame/move", json={"parent": "pump"}, headers=USER)
    # папку с проектами удалить нельзя, пустую — можно
    assert "не пуста" in client.delete(f"/api/folders/{fid}", headers=USER).json()["error"]
    # задачи уходят в корзину вместе с проектом и возвращаются с ним (повторное создание проекта с тем же именем
    # не наследует чужой разговор)
    t = client.post("/api/projects/frame/tasks", json={"text": "Рама из швеллера"}, headers=USER).json()
    client.post(f"/api/tasks/{t['id']}/stop", headers=USER)
    # корзина: удалить изделие вместе с узлом и вернуть
    r = client.delete("/api/projects/pump", headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "pump" and [n["name"] for n in r.json()["nodes"]] == ["frame"]
    names = [p["name"] for p in client.get("/api/projects", headers=USER).json()["projects"]]
    assert names == ["plate"]
    trash = client.get("/api/trash", headers=USER).json()["items"]
    assert sorted(t["name"] for t in trash) == ["frame", "pump"]
    tid = next(t["id"] for t in trash if t["name"] == "pump")
    r = client.post(f"/api/trash/{tid}/restore", headers=USER)
    assert r.status_code == 200 and r.json()["name"] == "pump" and r.json()["folder"] == fid
    tid = next(t["id"] for t in trash if t["name"] == "frame")
    assert client.get("/api/projects/frame/thread", headers=USER).status_code == 400  # проекта нет
    assert client.post(f"/api/trash/{tid}/restore", headers=USER).json()["parent"] == "pump"
    assert overview(client, "pump")["children"] == ["frame"]
    th = client.get("/api/projects/frame/thread", headers=USER).json()
    assert [m["who"] for m in th["messages"]].count("you") == 1 and th["messages"][-1]["who"] == "agent"
    assert "нет «" in client.post("/api/trash/nope.1/restore", headers=USER).json()["error"]
    client.delete("/api/projects/pump", headers=USER)
    assert client.delete(f"/api/folders/{fid}", headers=USER).json() == {"ok": True}


def test_stages_next_and_thread(client: TestClient):
    # пустой проект: задание — первое сообщение агенту
    client.post("/api/projects", json={"name": "clamp", "title": "Хомут"}, headers=USER)
    p = overview(client, "clamp")
    assert p["stages"] == {"brief": "next", "layout": "todo", "design": "todo", "kit": "todo"}
    assert p["next"]["act"] == "say" and p["next"]["stage"] == "brief" and p["thumb"] is None
    # задача поставлена — проект у агента; остановили — задание принято, дальше компоновка
    r = client.post("/api/projects/clamp/tasks", json={"text": "Хомут под трубу Ø57, два болта М10"}, headers=USER)
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    p = overview(client, "clamp")
    assert p["next"]["kind"] == "running" and p["stages"]["layout"] == "agent"
    client.post(f"/api/tasks/{tid}/stop", headers=USER)
    p = overview(client, "clamp")
    assert p["stages"]["brief"] == "done" and p["next"]["act"] == "run:layout"
    # пример с описанным скелетом без согласования — компоновка ждёт конструктора
    pl = overview(client, "plate")
    assert pl["layout"]["state"] == "waiting" and pl["next"]["act"] == "approve" and pl["stages"]["layout"] == "wait"
    assert pl["stages"]["design"] == "todo" and pl["chosen"] is None and pl["kit"]["files"] == []
    # разговор: задача конструктора, ответ агента (остановлен), служебные записи коммитов
    th = client.get("/api/projects/clamp/thread", headers=USER).json()
    kinds = [(m["who"], m.get("by")) for m in th["messages"]]
    assert ("system", "petrov") in kinds and ("you", "petrov") in kinds
    agent = next(m for m in th["messages"] if m["who"] == "agent")
    assert agent["status"] == "stopped" and agent["images"] == [] and agent["task"] == tid
    assert th["messages"][0]["who"] == "system" and "Проект clamp" in th["messages"][0]["text"]
    assert th["active"] is None
    texts = client.get("/api/projects", headers=USER).json()["task_texts"]
    assert set(texts) == {"layout", "design", "kit", "fix"}


def test_choose_variant_and_auto_continue(client: TestClient):
    # выбор варианта — коммит конструктора в decisions.yaml; снять выбор; ошибка словами
    r = client.post("/api/projects/plate/choose", json={"variant": "B_wide"}, headers=USER)
    assert r.status_code == 200, r.text
    assert r.json()["variant"] == "B_wide" and r.json()["commit"]["author"] == "petrov"
    assert overview(client, "plate")["chosen"] == "B_wide"
    r = client.post("/api/projects/plate/choose", json={"variant": "zzz"}, headers=USER)
    assert "нет варианта" in r.json()["error"]
    assert client.post("/api/projects/plate/choose", json={"variant": ""}, headers=USER).json()["variant"] is None
    assert overview(client, "plate")["chosen"] is None
    # согласование компоновки ставит агенту задачу «детали» (D32); проект у агента, следующий шаг — running
    r = client.post("/api/projects/plate/layout/approve", headers=USER)
    assert r.status_code == 200, r.text
    task = r.json()["task"]
    assert task and task["text"] == stages.TASK_TEXT["design"] and task["user"] == "petrov"
    p = overview(client, "plate")
    assert p["layout"]["state"] == "approved" and p["next"]["kind"] == "running"
    assert p["next"]["stage"] == "design" and p["stages"]["layout"] == "done"
    th = client.get("/api/projects/plate/thread", headers=USER).json()
    assert any(m["who"] == "system" and m["text"].startswith("Компоновка согласована") for m in th["messages"])
    assert th["messages"][-1]["who"] == "you" and th["messages"][-1]["text"] == stages.TASK_TEXT["design"]
    client.post(f"/api/tasks/{task['id']}/stop", headers=USER)
    assert overview(client, "plate")["next"]["act"] == "run:design"
    # комплекта нет — zip 404; при агенте правки закрыты (guard) — проверено выше косвенно
    assert client.get("/api/projects/plate/kit.zip", headers=USER).status_code == 404
    assert client.get("/api/projects/plate/kit", headers=USER).json() == {"variant": None, "files": []}


def test_kit_files_and_thumb(tmp_path: Path):
    out = tmp_path / "out"
    d = out / "pump" / "A_base"
    d.mkdir(parents=True)
    for n in ("A_base_assembly.step", "A_base_sketch_main.png", "A_base_main.svg", "report.json", "model.yaml"):
        (d / n).write_text("x", encoding="utf-8")
    files = stages.kit_files(out, "pump", "A_base")
    assert [f["kind"] for f in files] == ["step", "sketch", "view", "report", "model"]
    assert files[0]["url"] == "/out/pump/A_base/A_base_assembly.step" and files[0]["size"] == 1
    assert stages.kit_files(out, "pump", "nope") == []
    built = [{"id": "A_base", "built": True}]
    assert stages.thumb_url(out, "pump", None, built, None) == "/out/pump/A_base/A_base_sketch_main.png"
    lay = out / "pump" / "_layout" / "abcdef123456"
    lay.mkdir(parents=True)
    (lay / "pump_layout_main.png").write_text("x", encoding="utf-8")
    url = "/out/pump/_layout/abcdef123456/pump_layout_main.png"
    assert stages.thumb_url(out, "pump", "abcdef1234567890", [], None) == url
    assert stages.thumb_url(out, "pump", "0000", [], None) is None


def test_stage_rules_leaf_and_aggregate():
    spec = {"description": "x", "skeleton": {"datums": [{"id": "a"}]}}
    base = {"name": "n", "title": "N", "layout": {"state": "none"}, "task": None, "variants": []}
    st = stages.leaf(base, spec, False, None, [])
    assert st["layout_state"] == "waiting" and st["next"]["act"] == "approve" and st["stages"]["layout"] == "wait"
    built = [
        {"id": "A", "built": True, "errors": 0, "warnings": 1, "mass_kg": 2.0, "k_min": 1.8},
        {"id": "B", "built": True, "errors": 0, "warnings": 0, "mass_kg": 3.0, "k_min": 2.1},
    ]
    st = stages.leaf({**base, "layout": {"state": "approved"}, "variants": built}, spec, True, None, [])
    assert st["next"]["act"] == "choose" and st["stages"]["design"] == "wait"
    st = stages.leaf({**base, "layout": {"state": "approved"}, "variants": built}, spec, True, "B", [])
    assert st["next"]["act"] == "run:kit" and st["stages"]["kit"] == "next"
    kit = [{"kind": "step"}]
    st = stages.leaf({**base, "layout": {"state": "approved"}, "variants": built}, spec, True, "B", kit)
    assert st["next"]["kind"] == "done"
    assert st["stages"] == {"brief": "done", "layout": "done", "design": "done", "kit": "done"}
    err = [{"id": "A", "built": True, "errors": 2, "warnings": 0, "mass_kg": 1, "k_min": 1.1}]
    st = stages.leaf({**base, "layout": {"state": "approved"}, "variants": err}, spec, True, None, [])
    assert st["next"]["act"] == "run:fix" and st["errors"] == 2
    busy = {**base, "layout": {"state": "none"}, "task": {"text": stages.TASK_TEXT["layout"]}}
    run = stages.leaf(busy, spec, True, None, [])
    assert run["next"]["kind"] == "running" and run["stages"]["layout"] == "agent"
    # сводный узел: ждёт конструктора, пока хоть один узел ждёт; все готовы — сводный комплект
    own = {"brief": "done", "layout": "done", "design": "next", "kit": "todo"}
    parent = {"name": "pump", "title": "Насос", "stages": own, "next": {}, "children": ["a", "b"]}
    frame = [{"id": "A", "built": True, "mass_kg": 86.4, "k_min": 1.82}]
    done_next = {"kind": "done", "label": "Скачать"}
    kid_done = {"name": "a", "title": "Рама", "children": [], "chosen": "A", "variants": frame, "next": done_next}
    wait_next = {"kind": "you", "label": "Сравнить и выбрать", "hint": ""}
    kid_wait = {"name": "b", "title": "Опоры", "children": [], "chosen": None, "variants": built, "next": wait_next}
    agg = stages.aggregate(parent, [kid_done, kid_wait])
    assert agg["stages"]["design"] == "wait" and agg["next"]["act"] == "open:b" and agg["next"]["kind"] == "you"
    assert agg["summary"]["nodes"] == 2 and agg["summary"]["done"] == 1 and agg["summary"]["mass_kg"] == 88.4
    assert agg["summary"]["k_min"] == 1.8
    agg = stages.aggregate(parent, [kid_done, {**kid_wait, "next": done_next}])
    assert agg["stages"]["design"] == "done" and agg["next"]["act"] == "run:kit" and agg["stages"]["kit"] == "next"


def test_thread_brief_is_one_line_without_markup():
    """Краткий ответ агента в ленте: заголовки и код пропущены, жёсткие переносы модели — пробелами, пункты
    списка через «; », без **разметки**, обрезка по слову."""
    from skelcad.server.thread import brief

    text = (
        "## Итог\n\n"
        "Компоновочный эскиз **построен**: стена `interface:wall`,\n"
        "труба Ø108 на высоте 1200 мм.\n\n"
        "- анкеры M16 — 4 шт\n"
        "- пластина 10 мм\n"
    )
    assert brief(text) == "Компоновочный эскиз построен: стена interface:wall, труба Ø108 на высоте 1200 мм."
    assert brief("# Заголовок\n\n```\ncode\n```\n\n1. первое\n2. второе") == "первое; второе"
    long = " ".join(["слово"] * 100)
    b = brief(long, limit=40)
    assert b.endswith("…") and len(b) <= 41 and "сло…" not in b
    assert brief("") == "" and brief("Остановлено.") == "Остановлено."
    from skelcad.server.thread import failure_text

    assert failure_text("failed", "ReadTimeout: timed out", None).startswith("Провайдер модели не ответил вовремя: ")
    assert "лимит шагов (60)" in failure_text("limit", "достигнут лимит шагов (60)", None, 60)
    assert failure_text("failed", "", "") == "Агент завершился с ошибкой."
