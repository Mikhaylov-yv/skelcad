"""HTTP: токены, /health, /api, /out и точка MCP (список инструментов, вызов, автор коммита по токену)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from skelcad.server.app import create_app, parse_tokens
from skelcad.server.tools import local_server


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    data = tmp_path_factory.mktemp("data")
    monkeypatch_module.setenv("SKELCAD_TOKENS", "claude-code:secret1;cursor:secret2")
    monkeypatch_module.setenv("SKELCAD_SEED", "bracket")
    srv = local_server(data)
    srv.public_url = "https://skelcad.test"
    app = create_app(srv)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


def test_parse_tokens():
    assert parse_tokens("a:1;b:2, c:3") == {"1": "a", "2": "b", "3": "c"}
    assert parse_tokens("") == {}
    with pytest.raises(ValueError):
        parse_tokens("noname")


def test_health_and_auth(client: TestClient):
    assert client.get("/health").json()["projects"] == ["bracket"]
    assert client.get("/api/projects").status_code == 401
    r = client.get("/api/projects", headers={"Authorization": "Bearer secret1"})
    assert r.status_code == 200 and r.json()["projects"][0]["name"] == "bracket"
    assert client.get("/api/projects/nope", headers={"Authorization": "Bearer secret1"}).status_code == 400


def mcp_call(client: TestClient, token: str, method: str, params: dict | None = None, id_: int = 1):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    r = client.post(
        "/mcp",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    return r


def test_mcp_tools_and_author(client: TestClient):
    assert mcp_call(client, "wrong", "tools/list").status_code == 401
    r = mcp_call(client, "secret1", "tools/list")
    assert r.status_code == 200, r.text
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert {"project_list", "files_write", "build", "check", "compare", "model_query", "history", "revert"} <= names

    content = client.get("/api/projects/bracket", headers={"Authorization": "Bearer secret2"}).json()
    assert "variants/A_fork.yaml" in content["files"]
    r = mcp_call(
        client,
        "secret2",
        "tools/call",
        {
            "name": "files_write",
            "arguments": {
                "project": "bracket",
                "files": {"notes.md": "заметка агента\n"},
                "message": "заметка от cursor",
            },
        },
        id_=2,
    )
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert not res.get("isError"), res
    payload = json.loads(res["content"][0]["text"])
    assert payload["commit"]["author"] == "SkelCAD agent (cursor)"

    args = {"project": "bracket", "path": "nope.yaml"}
    r = mcp_call(client, "secret1", "tools/call", {"name": "files_read", "arguments": args}, id_=3)
    res = r.json()["result"]
    assert res.get("isError") and "nope.yaml" in res["content"][0]["text"]


def test_out_static(client: TestClient):
    out = client.app.state.server.workspace.out_dir / "bracket"
    out.mkdir(parents=True, exist_ok=True)
    (out / "x.txt").write_text("hi", encoding="utf-8")
    assert client.get("/out/bracket/x.txt").text == "hi"
