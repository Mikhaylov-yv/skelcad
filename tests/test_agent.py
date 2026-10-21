"""Встроенный агент: очередь задач, цикл с моделью на фейках, остановка и лимит шагов; мост MCP к живому серверу."""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

import pytest

from skelcad.agent import McpBridge, ToolOutput, openai_tools, run_loop
from skelcad.server.tasks import TaskError, TaskStore


class FakeLLM:
    def __init__(self, script: list[dict]):
        self.script, self.calls = list(script), []

    def chat(self, messages, tools):
        self.calls.append((len(messages), len(tools)))
        return self.script.pop(0) if self.script else {"content": "готово"}


class FakeBridge:
    def __init__(self):
        self.called = []

    def list_tools(self):
        return [{"name": "project_read", "description": "спецификация", "input_schema": {"type": "object"}}]

    def call(self, name, args):
        self.called.append((name, args))
        return json.dumps({"summary": f"{name} ok"})


def test_task_store_lifecycle(tmp_path: Path):
    st = TaskStore(tmp_path / "tasks")
    t = st.create("bracket", "подними K", "ivanov", variant="A_fork")
    assert t["status"] == "queued" and st.active("bracket")["id"] == t["id"]
    with pytest.raises(TaskError):
        st.create("bracket", "ещё", "ivanov")  # проект у агента
    claimed = st.claim()
    assert claimed["id"] == t["id"] and claimed["status"] == "running"
    assert st.claim() is None
    st.event(t["id"], "tool_call", name="project_read", args={})
    st.progress(t["id"], 1)
    ev = st.events(t["id"])
    assert ev["events"][0]["type"] == "tool_call" and ev["next"] == 1 and ev["task"]["steps"] == 1
    st.finish(t["id"], "done", result="отчёт")
    assert st.get(t["id"])["status"] == "done" and st.active("bracket") is None
    st.create("bracket", "вторая", "ivanov")
    q = st.list("bracket")[0]
    assert st.stop(q["id"])["status"] == "stopped"


def test_run_loop_tool_calls_and_done():
    llm = FakeLLM(
        [
            {
                "content": "читаю проект",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "project_read", "arguments": '{"project": "bracket"}'}}
                ],
            },
            {"content": "Отчёт: всё хорошо"},
        ]
    )
    bridge, events = FakeBridge(), []
    res = run_loop(
        {"project": "bracket", "text": "проверь", "user": "ivanov"},
        llm,
        bridge,
        lambda k, **d: events.append((k, d)),
        lambda: False,
    )
    assert res["status"] == "done" and res["result"].startswith("Отчёт") and res["steps"] == 2
    assert bridge.called == [("project_read", {"project": "bracket"})]
    kinds = [k for k, _ in events]
    assert kinds == ["start", "step", "assistant", "tool_call", "tool_result", "step", "assistant", "done"]
    assert [d["n"] for k, d in events if k == "step"] == [1, 2] and "seconds" in events[1][1]
    assert llm.calls[0][1] == 1  # инструменты переданы в формате OpenAI
    assert openai_tools(bridge.list_tools())[0]["function"]["name"] == "project_read"


def test_run_loop_stop_and_limit():
    llm = FakeLLM(
        [{"content": "", "tool_calls": [{"id": "c", "function": {"name": "project_read", "arguments": "{}"}}]}] * 5
    )
    events = []
    res = run_loop(
        {"project": "p", "text": "x", "max_steps": 2}, llm, FakeBridge(), lambda k, **d: events.append(k), lambda: False
    )
    assert res["status"] == "limit" and res["steps"] == 2
    flag = {"stop": False}
    llm = FakeLLM(
        [{"content": "", "tool_calls": [{"id": "c", "function": {"name": "project_read", "arguments": "{}"}}]}] * 5
    )

    def stop():
        flag["stop"] = True
        return False

    res = run_loop(
        {"project": "p", "text": "x"}, llm, FakeBridge(), lambda k, **d: None, lambda: flag["stop"] or stop()
    )
    assert res["status"] == "stopped"


def test_mcp_bridge_against_live_server(tmp_path: Path, monkeypatch):
    """Мост агента к точке /mcp живого сервера: список инструментов и вызов project_list."""
    import socket

    import uvicorn

    from skelcad.server.app import create_app
    from skelcad.server.tools import local_server

    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:s1")
    monkeypatch.setenv("SKELCAD_AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    app = create_app(local_server(tmp_path / "data"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    import time

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with McpBridge(f"http://127.0.0.1:{port}/mcp", "agent-secret") as b:
            names = {t["name"] for t in b.list_tools()}
            assert {"project_read", "files_write", "review_list"} <= names
            out = b.call("project_list", {})
            assert "bracket" in out
            res = b.call("files_write", {"project": "bracket", "files": {"n.md": "x"}, "message": "заметка агента"})
            assert "коммит" in res
        with pytest.raises(RuntimeError, match="MCP"), McpBridge(f"http://127.0.0.1:{port}/mcp", "wrong"):
            pass
    finally:
        server.should_exit = True
        th.join(timeout=5)


def test_run_loop_saves_tool_images(tmp_path: Path):
    """Картинка из инструмента (render) сохраняется к задаче, имя файла — в событии tool_result.images."""
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16

    class ImageBridge(FakeBridge):
        def call(self, name, args):
            self.called.append((name, args))
            return ToolOutput("компоновка", [{"mime": "image/png", "b64": base64.b64encode(png).decode()}])

    llm = FakeLLM(
        [
            {"content": "", "tool_calls": [{"id": "c", "function": {"name": "render", "arguments": "{}"}}]},
            {"content": "готово"},
        ]
    )
    st = TaskStore(tmp_path / "tasks")
    t = st.create("bracket", "покажи", "ivanov")
    events = []
    res = run_loop(
        {"project": "bracket", "text": "покажи", "id": t["id"]},
        llm,
        ImageBridge(),
        lambda k, **d: events.append((k, d)),
        lambda: False,
        save=lambda n, b: st.save_file(t["id"], n, b),
    )
    assert res["status"] == "done"
    result = next(d for k, d in events if k == "tool_result")
    assert result["images"] == ["img-001.png"]
    f, mime = st.file_path(t["id"], "img-001.png")
    assert f.read_bytes() == png and mime == "image/png"
    with pytest.raises(TaskError):
        st.file_path(t["id"], "../task.json")
    with pytest.raises(TaskError):
        st.file_path(t["id"], "img-002.png")
    assert st.save_file(t["id"], "bad name.png", png) is None
