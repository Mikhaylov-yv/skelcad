"""Провайдеры модели (D29): хранилище с шифрованием ключей, API администратора (ключ наружу не отдаётся),
проверка и список моделей с фейковым провайдером, выбор провайдера и модели в задаче и у встроенного агента."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from skelcad.server import providers as P
from skelcad.server.app import create_app
from skelcad.server.tools import local_server


def test_store_encrypts_keys_and_hides_them(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_SECRET_KEY", "test-secret")
    st = P.ProviderStore(tmp_path / "providers.json")
    assert st.list() == [] and st.default_id() is None and st.resolve() is None
    rec = st.upsert(
        {
            "id": "openrouter",
            "title": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1/",
            "model": "x/y",
            "key": "sk-or-abcd1234",
        },
        "ivanov",
    )
    assert (
        rec["has_key"]
        and rec["key_tail"] == "1234"
        and rec["default"]
        and rec["base_url"] == "https://openrouter.ai/api/v1"
    )
    raw = json.loads((tmp_path / "providers.json").read_text(encoding="utf-8"))
    assert "sk-or-abcd1234" not in json.dumps(raw) and raw["providers"]["openrouter"]["key_enc"]
    assert (tmp_path / "providers.json").stat().st_mode & 0o777 == 0o600
    r = st.resolve()
    assert r["api_key"] == "sk-or-abcd1234" and r["model"] == "x/y" and r["kind"] == "openai"
    assert st.resolve("openrouter", "other/model")["model"] == "other/model"
    # правка без ключа — ключ остаётся; второй провайдер не становится умолчанием сам
    st.upsert(
        {"id": "openrouter", "base_url": "https://openrouter.ai/api/v1", "model": "a/b", "models": ["a/b", "c/d"]},
        "petrov",
    )
    assert st.resolve()["api_key"] == "sk-or-abcd1234" and st.get("openrouter")["models"] == ["a/b", "c/d"]
    st.upsert({"id": "ollama", "base_url": "http://host:11434/v1", "model": "qwen"}, "ivanov")
    assert st.default_id() == "openrouter" and st.set_default("ollama")["default"]
    assert st.resolve()["id"] == "ollama" and st.resolve()["api_key"] == ""
    st.delete("ollama")
    assert st.default_id() == "openrouter"
    with pytest.raises(P.ProviderError, match="нет провайдера"):
        st.resolve("nope")
    with pytest.raises(P.ProviderError, match="base_url"):
        st.upsert({"id": "bad", "base_url": "ftp://x"}, "ivanov")
    with pytest.raises(P.ProviderError, match="id провайдера"):
        st.upsert({"id": "Bad Id", "base_url": "https://x/v1"}, "ivanov")
    # другой секрет — ключ не расшифровать, ошибка словами
    monkeypatch.setenv("SKELCAD_SECRET_KEY", "another")
    with pytest.raises(P.ProviderError, match="другой"):
        P.ProviderStore(tmp_path / "providers.json").resolve()


def test_store_without_secret_key_is_plain(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SKELCAD_SECRET_KEY", raising=False)
    st = P.ProviderStore(tmp_path / "p.json")
    assert not P.secure()
    st.upsert({"id": "a", "base_url": "https://x/v1", "model": "m", "key": "plain-key-9"}, "u")
    assert st.resolve()["api_key"] == "plain-key-9" and st.get("a")["key_tail"] == "ey-9"


def fake_transport(calls: list):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url), req.headers.get("authorization"), req.read()))
        if req.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "z/last"},
                        {"id": "a/first", "name": "A", "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
                    ]
                },
            )
        if req.headers.get("authorization") == "Bearer bad":
            return httpx.Response(401, json={"error": {"message": "invalid key"}})
        return httpx.Response(
            200,
            json={
                "model": "a/first",
                "choices": [{"message": {"role": "assistant", "content": "ок"}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 1, "cost": 0.000123},
            },
        )

    return httpx.MockTransport(handler)


@pytest.fixture
def fake_llm(monkeypatch):
    calls: list = []
    real = httpx.Client

    def client(*a, **kw):
        kw["transport"] = fake_transport(calls)
        return real(*a, **kw)

    monkeypatch.setattr(httpx, "Client", client)
    return calls


def test_models_and_test_chat(fake_llm):
    models = P.fetch_models("https://openrouter.ai/api/v1", "k")
    assert [m["id"] for m in models] == ["a/first", "z/last"] and models[0]["prompt"] == 3.0
    res = P.test_chat("https://openrouter.ai/api/v1", "k", "a/first")
    assert res["ok"] and res["reply"] == "ок" and res["cost"] == 0.000123 and res["prompt_tokens"] == 9
    body = json.loads(fake_llm[-1][3])
    assert body["usage"] == {"include": True} and body["max_tokens"] == 16  # OpenRouter: учёт стоимости
    with pytest.raises(P.ProviderError, match="401 — ключ не принят"):
        P.test_chat("https://api.openai.com/v1", "bad", "gpt")
    body = json.loads(fake_llm[-1][3])
    assert "usage" not in body  # не OpenRouter — без расширения
    with pytest.raises(P.ProviderError, match="укажите модель"):
        P.test_chat("https://x/v1", "k", "")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SKELCAD_TOKENS", "claude-code:secret1")
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    monkeypatch.setenv("SKELCAD_AUTH", "proxy")
    monkeypatch.setenv("SKELCAD_SECRET_KEY", "s3")
    monkeypatch.delenv("SKELCAD_LLM_API_KEY", raising=False)
    app = create_app(local_server(tmp_path / "data"))
    with TestClient(app) as c:
        yield c


ADMIN = {"X-Forwarded-Preferred-Username": "ivanov", "X-Forwarded-Email": "i@x", "X-Forwarded-Groups": "admins"}
USER = {"X-Forwarded-Preferred-Username": "petrov", "X-Forwarded-Email": "p@x"}


def test_http_admin_crud_and_task_choice(client: TestClient, fake_llm):
    r = client.get("/api/providers", headers=USER)
    assert r.status_code == 200 and r.json()["providers"] == [] and r.json()["secure"] is True
    assert r.json()["presets"][0]["id"] == "openrouter" and r.json()["env"]["has_key"] is False
    body = {
        "id": "openrouter",
        "title": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "a/first",
        "key": "sk-or-xyz9",
    }
    assert client.post("/api/providers", json=body, headers=USER).status_code == 403
    r = client.post("/api/providers", json=body, headers=ADMIN)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["has_key"] and p["key_tail"] == "xyz9" and "key" not in p and "key_enc" not in p
    # список моделей по сохранённому ключу и проверка
    r = client.post("/api/providers/models", json={"id": "openrouter"}, headers=ADMIN)
    assert r.status_code == 200 and [m["id"] for m in r.json()["models"]] == ["a/first", "z/last"]
    assert fake_llm[-1][2] == "Bearer sk-or-xyz9"
    r = client.post("/api/providers/openrouter/test", json={"model": "z/last"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["reply"] == "ок" and r.json()["cost"] == 0.000123
    assert json.loads(fake_llm[-1][3])["model"] == "z/last"
    # список моделей по новому ключу без сохранения
    r = client.post(
        "/api/providers/models", json={"base_url": "https://api.openai.com/v1", "key": "tmp"}, headers=ADMIN
    )
    assert r.status_code == 200 and fake_llm[-1][2] == "Bearer tmp"
    # второй провайдер, умолчание, удаление
    client.post(
        "/api/providers", json={"id": "local", "base_url": "http://ollama:11434/v1", "model": "qwen"}, headers=ADMIN
    )
    assert client.post("/api/providers/local/default", headers=USER).status_code == 403
    assert client.post("/api/providers/local/default", headers=ADMIN).json()["default"]
    lst = client.get("/api/providers", headers=USER).json()
    assert lst["default"] == "local" and [x["id"] for x in lst["providers"]] == ["local", "openrouter"]
    # задача с выбором провайдера и модели; неизвестный провайдер — 400
    r = client.post(
        "/api/projects/bracket/tasks", json={"text": "x", "provider": "openrouter", "model": "z/last"}, headers=USER
    )
    assert r.status_code == 200 and r.json()["provider"] == "openrouter" and r.json()["model"] == "z/last"
    client.post(f"/api/tasks/{r.json()['id']}/stop", headers=USER)
    r = client.post("/api/projects/bracket/tasks", json={"text": "x", "provider": "nope"}, headers=USER)
    assert r.status_code == 400 and "нет провайдера" in r.json()["error"]
    assert client.delete("/api/providers/local", headers=ADMIN).status_code == 200
    assert client.get("/api/providers", headers=USER).json()["default"] == "openrouter"


def test_agent_picks_provider_from_store(tmp_path: Path, monkeypatch):
    """run_task берёт провайдера задачи (или умолчание) из providers.json, иначе — переменные окружения."""
    from skelcad import agent as A
    from skelcad.server.tasks import TaskStore

    monkeypatch.setenv("SKELCAD_SECRET_KEY", "s")
    st = P.ProviderStore(tmp_path / "providers.json")
    st.upsert({"id": "or", "base_url": "https://openrouter.ai/api/v1", "model": "a/b", "key": "k-or"}, "u")
    st.upsert({"id": "cc", "kind": "claude-code"}, "u")
    made: list = []

    class FakeLLM:
        def __init__(self, base_url, api_key, model, timeout=180.0):
            made.append((base_url, api_key, model))
            self.usage = {"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.01}

        def chat(self, messages, tools):
            return {"content": "готово"}

    class FakeBridge:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def list_tools(self):
            return []

        def call(self, name, args):
            return "{}"

    monkeypatch.setattr(A, "OpenAICompatible", FakeLLM)
    monkeypatch.setattr(A, "McpBridge", FakeBridge)
    monkeypatch.setattr(A, "run_claude_code", lambda *a, **kw: {"status": "done", "result": "cc", "steps": 1})
    tasks = TaskStore(tmp_path / "tasks")
    t = tasks.create("p", "x", "u", provider="or", model="c/d")
    A.run_task(tasks, tasks.claim(), st)
    assert made == [("https://openrouter.ai/api/v1", "k-or", "c/d")]
    done = tasks.get(t["id"])
    assert done["status"] == "done" and done["usage"]["cost"] == 0.01 and done["provider"] == "or"
    ev = [json.loads(x) for x in (tmp_path / "tasks" / t["id"] / "events.jsonl").read_text().splitlines()]
    assert ev[0]["type"] == "start" and ev[0]["provider"] == "or" and ev[0]["model"] == "c/d"
    assert ev[-1]["type"] == "done" and ev[-1]["usage"]["cost"] == 0.01
    # провайдер claude-code → исполнитель claude-code
    t2 = tasks.create("p", "y", "u", provider="cc")
    A.run_task(tasks, tasks.claim(), st)
    assert tasks.get(t2["id"])["result"] == "cc"
    # без провайдеров — окружение
    monkeypatch.setenv("SKELCAD_LLM_BASE_URL", "https://env/v1")
    monkeypatch.setenv("SKELCAD_LLM_API_KEY", "env-key")
    monkeypatch.setenv("SKELCAD_LLM_MODEL", "env-model")
    t3 = tasks.create("p", "z", "u")
    A.run_task(tasks, tasks.claim(), P.ProviderStore(tmp_path / "none.json"))
    assert made[-1] == ("https://env/v1", "env-key", "env-model") and tasks.get(t3["id"])["status"] == "done"
