"""Вложения конструктора (M2.3, D28): хранение в attachments/ коммитом, уменьшение растра, растр SVG и PDF,
сводка .excalidraw, инструмент attachment (HTTP, MCP), вложения в задаче агенту и изображения в цикле модели."""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from skelcad.agent import ToolOutput, run_loop, task_text
from skelcad.server import attachments as A
from skelcad.server.app import create_app
from skelcad.server.tools import Tools, local_server
from skelcad.server.workspace import Actor


def png_bytes(w: int, h: int, fmt: str = "PNG") -> bytes:
    im = Image.new("RGB", (w, h), (250, 250, 250))
    for x in range(0, w, max(1, w // 10)):
        for y in range(h):
            im.putpixel((x, y), (20, 20, 20))
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
    '<rect x="10" y="10" width="80" height="50"/></svg>'
)
EXCALIDRAW = {
    "type": "excalidraw",
    "version": 2,
    "elements": [
        {
            "id": "wall", "type": "rectangle", "x": 0, "y": 0, "width": 40, "height": 300,
            "customData": {"ref": "surrounding:wall_body"},
        },
        {"id": "t1", "type": "text", "x": 60, "y": 10, "width": 80, "height": 20, "text": "стена"},
        {
            "id": "a1", "type": "arrow", "x": 0, "y": 0, "width": 50, "height": 0,
            "startBinding": {"elementId": "wall"}, "endBinding": {"elementId": "t1"},
        },
        {"id": "gone", "type": "ellipse", "x": 0, "y": 0, "width": 1, "height": 1, "isDeleted": True},
    ],
}  # fmt: skip


@pytest.fixture
def srv(tmp_path: Path):
    s = local_server(tmp_path / "data")
    s.workspace.seed(["bracket"])
    return s


def test_add_shrinks_rotates_and_commits_as_constructor(srv):
    ws, actor = srv.workspace, Actor("Иванов", "ivanov@x")
    res = A.add(ws, "bracket", "Набросок кронштейна.PNG", png_bytes(4000, 2000), actor, "вид сбоку, стена слева")
    item = res["item"]
    assert re.fullmatch(r"attachments/\d{8}-\d{4}-nabrosok-kronshteyna\.png", item["path"])
    assert (item["width"], item["height"]) == (3000, 1500) and item["kind"] == "image"
    assert res["commit"]["author"] == "Иванов" and res["commit"]["message"].endswith(": вид сбоку, стена слева")
    assert item["path"] in ws.files("bracket")
    # второй файл с тем же именем в ту же минуту — суффикс
    res2 = A.add(ws, "bracket", "Набросок кронштейна.png", png_bytes(100, 50), actor)
    assert res2["item"]["path"].endswith("-2.png") and res2["item"]["width"] == 100
    assert "изображение 100×50" in res2["commit"]["message"]
    items = A.list_items(ws, "bracket")
    assert [i["path"] for i in items] == [res2["item"]["path"], item["path"]]  # новые первыми
    # jpeg с EXIF-поворотом: становится вертикальным
    im = Image.new("RGB", (300, 100), "white")
    exif = im.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=exif)
    r3 = A.add(ws, "bracket", "photo.jpeg", buf.getvalue(), actor)
    assert (r3["item"]["width"], r3["item"]["height"]) == (100, 300) and r3["item"]["path"].endswith(".jpg")
    # удаление — коммит, файла нет в git
    rm = A.remove(ws, "bracket", r3["item"]["path"], actor)
    assert rm["commit"]["message"].startswith("удалено вложение") and r3["item"]["path"] not in ws.files("bracket")


def test_validation(srv):
    ws, actor = srv.workspace, Actor("Иванов", "ivanov@x")
    with pytest.raises(ValueError, match="допустимые файлы"):
        A.add(ws, "bracket", "model.exe", b"MZ", actor)
    with pytest.raises(ValueError, match="пустой"):
        A.add(ws, "bracket", "a.png", b"", actor)
    with pytest.raises(ValueError, match="не читается"):
        A.add(ws, "bracket", "a.png", b"not a png at all", actor)
    with pytest.raises(ValueError, match="не SVG"):
        A.add(ws, "bracket", "a.svg", b"<html></html>", actor)
    with pytest.raises(ValueError, match="не PDF"):
        A.add(ws, "bracket", "a.pdf", b"hello", actor)
    with pytest.raises(ValueError, match="Excalidraw"):
        A.add(ws, "bracket", "a.excalidraw", b'{"type": "other"}', actor)
    big = png_bytes(10, 10) + b"\0" * (A.MAX_BYTES + 1)
    with pytest.raises(ValueError, match="больше"):
        A.add(ws, "bracket", "a.png", big, actor)
    with pytest.raises(Exception, match="ожидался путь"):
        A.check_path(ws, "bracket", "../project.yaml")
    with pytest.raises(Exception, match="нет"):
        A.check_path(ws, "bracket", "attachments/none.png")


def test_image_for_agent_svg_pdf_excalidraw(srv):
    ws, actor = srv.workspace, Actor("Иванов", "ivanov@x")
    t = Tools(srv)
    svg = A.add(ws, "bracket", "sketch.svg", SVG.encode(), actor)["item"]["path"]
    r = A.image(ws, "bracket", svg)
    assert r["format"] == "png" and Image.open(io.BytesIO(r["png"])).size[0] == A.RASTER_WIDTH
    # pdf: первая страница растром (страницу делает Pillow)
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, "PDF")
    pdf = A.add(ws, "bracket", "drawing.pdf", buf.getvalue(), actor)["item"]["path"]
    r = A.image(ws, "bracket", pdf)
    assert (
        r["format"] == "png" and r["text"].startswith("страниц 1") and Image.open(io.BytesIO(r["png"])).size[0] >= 1000
    )
    # excalidraw: сводка элементов, без удалённых, с привязками и ref
    ex = A.add(ws, "bracket", "board.excalidraw", json.dumps(EXCALIDRAW).encode(), actor)["item"]["path"]
    r = A.image(ws, "bracket", ex)
    assert r["png"] is None and "элементов 3" in r["text"] and "ref=surrounding:wall_body" in r["text"]
    assert "«стена»" in r["text"] and "wall → t1" in r["text"] and "gone" not in r["text"]
    # webp → png
    wp = A.add(ws, "bracket", "photo.webp", png_bytes(50, 40, "WEBP"), actor)["item"]["path"]
    assert A.image(ws, "bracket", wp)["format"] == "png"
    # инструмент агента и project_read
    res = t.attachment("bracket", ex)
    assert (
        res["png_base64"] is None and "файл доски Excalidraw" in res["summary"] and "добавил Иванов" in res["summary"]
    )
    res = t.attachment("bracket", Path(svg).name)  # можно и без папки
    assert res["format"] == "png" and base64.b64decode(res["png_base64"])[:4] == b"\x89PNG"
    pr = t.project_read("bracket")
    assert len(pr["attachments"]) == 4 and "вложений конструктора: 4" in pr["summary"]
    assert "sketch.svg" in t.attachments("bracket")["summary"]


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    app = create_app(local_server(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


USER = {"X-Forwarded-Preferred-Username": "petrov", "X-Forwarded-Email": "petrov@x"}


def test_http_upload_list_file_task_delete(client: TestClient):
    r = client.post(
        "/api/projects/bracket/attachments",
        files={"file": ("Эскиз.png", png_bytes(120, 80), "image/png")},
        data={"note": "набросок от руки"},
        headers=USER,
    )
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert item["author"] == "petrov" and item["name"].endswith("-eskiz.png")
    assert client.get("/api/projects/bracket/attachments", headers=USER).json()["items"][0]["path"] == item["path"]
    f = client.get(f"/api/projects/bracket/attachments/{item['name']}", headers=USER)
    assert f.status_code == 200 and f.headers["content-type"] == "image/png" and f.content[:4] == b"\x89PNG"
    assert client.get("/api/projects/bracket/attachments/none.png", headers=USER).status_code == 400
    bad = client.post("/api/projects/bracket/attachments", files={"file": ("m.exe", b"x", "text/plain")}, headers=USER)
    assert bad.status_code == 400 and "допустимые" in bad.json()["error"]
    # задача с вложением: пути проверяются, список попадает в задачу; пока задача в очереди — загрузка закрыта
    r = client.post(
        "/api/projects/bracket/tasks", json={"text": "по наброску", "attachments": ["attachments/x.png"]}, headers=USER
    )
    assert r.status_code == 400
    r = client.post(
        "/api/projects/bracket/tasks", json={"text": "по наброску", "attachments": [item["path"]]}, headers=USER
    )
    assert r.status_code == 200 and r.json()["attachments"] == [item["path"]]
    tid = r.json()["id"]
    r = client.post(
        "/api/projects/bracket/attachments", files={"file": ("b.png", png_bytes(10, 10), "image/png")}, headers=USER
    )
    assert r.status_code == 409
    client.post(f"/api/tasks/{tid}/stop", headers=USER)
    r = client.delete(f"/api/projects/bracket/attachments/{item['name']}", headers=USER)
    assert r.status_code == 200 and r.json()["commit"]["author"] == "petrov"
    assert client.get("/api/projects/bracket/attachments", headers=USER).json()["items"] == []


def test_mcp_attachment_tool(client: TestClient):
    client.post(
        "/api/projects/bracket/attachments", files={"file": ("s.png", png_bytes(60, 30), "image/png")}, headers=USER
    )
    path = client.get("/api/projects/bracket/attachments", headers=USER).json()["items"][0]["path"]
    h = {"Authorization": "Bearer secret1", "Accept": "application/json, text/event-stream"}
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, headers=h)
    assert "attachment" in {t["name"] for t in r.json()["result"]["tools"]}
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "attachment", "arguments": {"project": "bracket", "path": path}},
        },
        headers=h,
    )
    content = r.json()["result"]["content"]
    assert content[0]["type"] == "text" and "изображение 60×30" in content[0]["text"]
    assert content[1]["type"] == "image" and content[1]["mimeType"] == "image/png"
    r = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "project_read", "arguments": {"project": "bracket"}},
        },
        headers=h,
    )
    assert path in json.loads(r.json()["result"]["content"][0]["text"])["attachments"]


class ImageBridge:
    """Мост-фейк: attachment и render отдают изображение, остальное — текст."""

    def __init__(self):
        self.called = []

    def list_tools(self):
        return [
            {"name": n, "description": "", "input_schema": {"type": "object"}}
            for n in ("attachment", "render", "project_read")
        ]

    def call(self, name, args):
        self.called.append((name, args))
        if name in ("attachment", "render"):
            return ToolOutput(f"{name}: изображение", [{"mime": "image/png", "b64": "QUJD"}])
        return json.dumps({"summary": f"{name} ok"})


class ScriptLLM:
    def __init__(self, script):
        self.script, self.seen = list(script), []

    def chat(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        return self.script.pop(0) if self.script else {"content": "готово"}


def test_run_loop_passes_attachments_and_tool_images_to_model():
    task = {"project": "bracket", "text": "по наброску", "user": "petrov", "attachments": ["attachments/a.png"]}
    assert "attachments/a.png" in task_text(task)
    llm = ScriptLLM(
        [
            {
                "content": "",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "render", "arguments": '{"project": "bracket", "layout": true}'}}
                ],
            },
            {"content": "Отчёт"},
        ]
    )
    bridge, events = ImageBridge(), []
    res = run_loop(task, llm, bridge, lambda k, **d: events.append((k, d)), lambda: False)
    assert res["status"] == "done" and bridge.called[0] == (
        "attachment",
        {"project": "bracket", "path": "attachments/a.png"},
    )
    first = llm.seen[0][1]
    assert first["role"] == "user" and isinstance(first["content"], list)
    assert [p["type"] for p in first["content"]] == ["text", "text", "image_url"]
    assert first["content"][2]["image_url"]["url"].startswith("data:image/png;base64,QUJD")
    # после ответа инструмента render — сообщение пользователя с картинкой
    msgs = llm.seen[1]
    assert msgs[-2]["role"] == "tool" and "[изображение — передано модели]" not in msgs[-2]["content"]
    assert msgs[-1]["role"] == "user" and msgs[-1]["content"][1]["type"] == "image_url"
    kinds = [k for k, _ in events]
    assert kinds[:2] == ["start", "attachment"] and "images" in kinds
    assert events[1][1]["images"] == 1


def test_run_loop_without_attachments_keeps_plain_text():
    llm = ScriptLLM([{"content": "ок"}])
    run_loop({"project": "p", "text": "x"}, llm, ImageBridge(), lambda k, **d: None, lambda: False)
    assert isinstance(llm.seen[0][1]["content"], str)


def test_files_zone_kinds_note_and_thumb(client: TestClient):
    """Зона файлов (M2.5): текст и модели CAD принимаются, заметка из коммита видна в списке, миниатюры для
    картинок, SVG и PDF; у текста миниатюры нет; агент получает текст как текст, CAD — только имя и размер."""
    up = lambda name, data, note="": client.post(  # noqa: E731
        "/api/projects/bracket/attachments",
        files={"file": (name, data, "application/octet-stream")},
        data={"note": note},
        headers=USER,
    )
    assert up("Примечания.txt", "нагрузка 12 кН, стена бетон".encode(), "пример задания").status_code == 200
    assert up("analog.step", b"ISO-10303-21;\nHEADER;\nENDSEC;\n").status_code == 200
    assert up("sketch.svg", SVG.encode()).status_code == 200
    assert up("photo.png", png_bytes(900, 600)).status_code == 200
    assert up("m.exe", b"MZ").status_code == 400
    listed = client.get("/api/projects/bracket/attachments", headers=USER).json()["items"]
    items = {i["name"].split("-", 2)[-1]: i for i in listed}
    assert items["primechaniya.txt"]["kind"] == "text" and items["primechaniya.txt"]["note"] == "пример задания"
    assert items["analog.step"]["kind"] == "cad" and items["analog.step"]["note"] is None
    for n in ("photo.png", "sketch.svg"):
        r = client.get(f"/api/projects/bracket/attachments/{items[n]['name']}/thumb", headers=USER)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png", n
        im = Image.open(io.BytesIO(r.content))
        assert max(im.size) <= A.THUMB_SIDE
    r = client.get(f"/api/projects/bracket/attachments/{items['primechaniya.txt']['name']}/thumb", headers=USER)
    assert r.status_code == 404
    t = client.get(f"/api/projects/bracket/attachments/{items['primechaniya.txt']['name']}", headers=USER)
    assert t.status_code == 200 and "12 кН" in t.text and t.headers["content-type"].startswith("text/plain")
    # для агента
    tools = Tools(client.app.state.server)
    res = tools.attachment("bracket", items["primechaniya.txt"]["path"])
    assert res["png_base64"] is None and "12 кН" in res["summary"]
    res = tools.attachment("bracket", items["analog.step"]["path"])
    assert res["png_base64"] is None and "не читает" in res["summary"]
