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
    assert client.get("/out/bracket/x.txt").status_code == 401  # артефакты — за входом (M2)
    assert client.get("/out/bracket/x.txt", headers={"Authorization": "Bearer secret1"}).text == "hi"


def test_workbench_static_and_me(client: TestClient):
    h = {"Authorization": "Bearer secret1"}
    assert client.get("/").status_code == 401  # режим tokens: браузер без токена не пускаем
    r = client.get("/", headers=h)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    r = client.get("/p/bracket/A_fork", headers=h)  # маршрут браузера → index.html (или заглушка)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert client.get("/api/nope", headers=h).status_code == 404
    me = client.get("/api/me", headers=h).json()
    assert me == {"name": "claude-code", "kind": "agent", "email": None, "auth": "tokens", "logout_url": None}
    p = client.get("/api/projects", headers=h).json()["projects"][0]
    assert p["name"] == "bracket" and p["state"] == "constructor"
    assert {v["id"] for v in p["variants"]} >= {"A_fork"} and all("built" in v for v in p["variants"])


def test_auth_modes(tmp_path, monkeypatch):
    from skelcad.server.auth import Principal, resolve

    class R:
        def __init__(self, path, headers):
            self.url = type("U", (), {"path": path})()
            self.headers = headers

    tokens = {"t1": "claude-code"}
    assert resolve(R("/mcp", {}), tokens, "proxy") is None
    assert resolve(R("/mcp", {"authorization": "Bearer t1"}), tokens, "proxy") == Principal("claude-code", "agent")
    assert resolve(R("/", {}), tokens, "proxy") is None
    u = resolve(R("/api/projects", {"x-forwarded-user": "ivanov", "x-forwarded-email": "i@x.ru"}), tokens, "proxy")
    assert u == Principal("ivanov", "user", "i@x.ru")
    assert resolve(R("/", {}), tokens, "none") == Principal("constructor", "user")
    assert resolve(R("/", {}), {}, "none") == Principal("constructor", "user")
    assert resolve(R("/mcp", {}), {}, "none") == Principal("anonymous", "agent")


def test_proxy_user_commits_as_person(tmp_path_factory, monkeypatch):
    """Режим proxy: пользователь из заголовков oauth2-proxy, коммит через инструменты — его именем."""
    from skelcad.server.auth import CURRENT_PRINCIPAL, Principal, current_actor

    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    srv = local_server(tmp_path_factory.mktemp("data"))
    with TestClient(create_app(srv)) as c:
        assert c.get("/api/me").status_code == 401
        me = c.get("/api/me", headers={"X-Forwarded-User": "ivanov", "X-Forwarded-Email": "ivanov@kb.ru"}).json()
        assert me["name"] == "ivanov" and me["kind"] == "user" and me["auth"] == "proxy"
        assert me["logout_url"].startswith("/oauth2/sign_out?rd=")
        # токен агента по-прежнему работает на /api и /mcp
        assert c.get("/api/me", headers={"Authorization": "Bearer secret1"}).json()["kind"] == "agent"
    tok = CURRENT_PRINCIPAL.set(Principal("ivanov", "user", "ivanov@kb.ru"))
    try:
        a = current_actor("claude-code")
        assert (a.name, a.email) == ("ivanov", "ivanov@kb.ru")
    finally:
        CURRENT_PRINCIPAL.reset(tok)
    assert current_actor("claude-code").name == "SkelCAD agent (claude-code)"
