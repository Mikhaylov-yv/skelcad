"""Встроенный агент SkelCAD: берёт задачи из очереди (/data/tasks) и ведёт цикл «модель → инструмент → результат»
против инструментов MCP сервера. Провайдер модели — любой с OpenAI-совместимым Chat Completions API;
второй исполнитель — headless Claude Code (`claude -p`).

Провайдер модели — из файла providers.json рядом с очередью (настраивается в рабочем месте, D29; ключи
расшифровываются тем же SKELCAD_SECRET_KEY, что у сервера); задача выбирает провайдера и модель, иначе умолчание.
Если провайдеров нет — переменные окружения (старый путь):
  SKELCAD_AGENT_RUNNER   openai (по умолчанию) | claude-code
  SKELCAD_LLM_BASE_URL   например https://openrouter.ai/api/v1, http://litellm:4000/v1, http://ollama:11434/v1
  SKELCAD_LLM_API_KEY    ключ провайдера (для Ollama — любой)
  SKELCAD_LLM_MODEL      имя модели у провайдера
  SKELCAD_SERVER_URL     точка MCP сервера, например http://server:8000/mcp
  SKELCAD_AGENT_TOKEN    Bearer-токен клиента «workbench-agent» (см. SKELCAD_AGENT_TOKEN у сервера)
  SKELCAD_AGENT_MAX_STEPS лимит шагов по умолчанию (60)
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

import httpx

from skelcad.server.providers import ProviderError, ProviderStore, is_openrouter, response_cost
from skelcad.server.tasks import TaskStore

log = logging.getLogger("skelcad.agent")

SYSTEM = """Ты — агент-конструктор SkelCAD. Работаешь только инструментами сервера (MCP): читаешь проект, измеряешь,
правишь файлы проекта (каждая правка — коммит с сообщением «что и зачем»), собираешь, проверяешь, сравниваешь.
Цикл: project_read → review_list (открытые замечания конструктора; на каждое — review_resolve с ответом) →
check/build → measure/context_search/render → files_write → build → diff(HEAD~1 → HEAD) → … → compare → отчёт.
Правила: замечания уровня error не оставляй; числа — из measure и каталогов; параметры — в variants/*.yaml;
одно логическое изменение — один коммит; тупиковый шаг — revert. Единицы: мм, кН, кг. Отвечай по-русски.
Вложения конструктора (набросок от руки, фото, экспорт доски) приходят с задачей как изображения; все вложения
проекта — project_read → attachments, посмотреть ещё раз — attachment(project, path). Набросок — исходный
документ компоновки: опорное на нём (стена, пол, труба, ответная деталь) — skeleton.surroundings и datums; где
изделие крепится и что несёт — interfaces и нагрузки requirements; подписанные числа — размеры, неподписанное
оцени по пропорциям и запиши в assumptions. Опиши скелет в project.yaml, посмотри render(layout=true) и
остановись: детали — после того, как конструктор согласует компоновку.
В конце напиши короткий отчёт конструктору: что сделано, какие коммиты, какие допущения, что осталось."""


class ToolOutput(str):
    """Текст результата инструмента; изображения из ответа MCP — в .images: [{"mime": "image/png", "b64": …}]."""

    images: list[dict]

    def __new__(cls, text: str, images: list[dict] | None = None):
        o = super().__new__(cls, text)
        o.images = images or []
        return o


class ToolBridge(Protocol):
    def list_tools(self) -> list[dict]: ...  # [{name, description, input_schema}]
    def call(self, name: str, args: dict) -> str: ...


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...  # -> message dict (OpenAI)


# ---------------------------------------------------------------- мост к инструментам сервера (MCP, Streamable HTTP)


class McpBridge:
    """Синхронная обёртка над клиентом MCP: сессия живёт в отдельном потоке со своим event loop
    (контекст-менеджеры anyio нельзя входить и выходить из разных задач), вызовы — через очередь."""

    def __init__(self, url: str, token: str | None, timeout: float = 900.0):
        self.url, self.token, self.timeout = url, token, timeout
        self._req: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._err: BaseException | None = None
        self._th: threading.Thread | None = None

    def __enter__(self):
        self._th = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True, name="skelcad-mcp")
        self._th.start()
        self._ready.wait(60)
        if self._err is not None:
            raise RuntimeError(f"MCP {self.url}: {type(self._err).__name__}: {self._err}") from self._err
        if not self._ready.is_set():
            raise RuntimeError(f"MCP {self.url}: нет ответа за 60 с")
        return self

    def __exit__(self, *exc):
        self._req.put(None)
        if self._th:
            self._th.join(10)

    async def _main(self):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        try:
            async with streamablehttp_client(self.url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._ready.set()
                    loop = asyncio.get_running_loop()
                    while True:
                        item = await loop.run_in_executor(None, self._req.get)
                        if item is None:
                            break
                        fut, fn, args = item
                        try:
                            fut.set_result(await fn(session, *args))
                        except BaseException as e:  # noqa: BLE001 — ошибка уходит вызывающему потоку
                            fut.set_exception(e)
        except BaseException as e:  # noqa: BLE001
            self._err = e
            self._ready.set()
            # очередь могла накопить запросы — ответить ошибкой
            while not self._req.empty():
                item = self._req.get_nowait()
                if item:
                    item[0].set_exception(e)

    def _call(self, fn, *args):
        if self._err is not None:
            raise RuntimeError(f"MCP: {self._err}")
        fut: concurrent.futures.Future = concurrent.futures.Future()
        self._req.put((fut, fn, args))
        return fut.result(timeout=self.timeout)

    def list_tools(self) -> list[dict]:
        async def go(session):
            return await session.list_tools()

        res = self._call(go)
        return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in res.tools]

    def call(self, name: str, args: dict) -> str:
        async def go(session, name, args):
            return await session.call_tool(name, args)

        res = self._call(go, name, args)
        parts, images = [], []
        for c in res.content:
            if getattr(c, "type", "") == "text":
                parts.append(c.text)
            elif getattr(c, "type", "") == "image":
                images.append({"mime": getattr(c, "mimeType", None) or "image/png", "b64": c.data})
                parts.append("[изображение — передано модели]")
        text = "\n".join(parts) or json.dumps(getattr(res, "structuredContent", None) or {}, ensure_ascii=False)
        if res.isError:
            text = "ОШИБКА: " + text
        return ToolOutput(text, images)


# ---------------------------------------------------------------- OpenAI-совместимый провайдер


class OpenAICompatible:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 180.0):
        if not base_url or not model:
            raise RuntimeError(
                "провайдер модели не настроен: добавьте его на экране «Подключение агента» "
                "или задайте SKELCAD_LLM_BASE_URL / SKELCAD_LLM_MODEL"
            )
        self.base = base_url.rstrip("/")
        self.model = model
        self.openrouter = is_openrouter(self.base)
        headers = {"Authorization": f"Bearer {api_key or 'none'}"}
        if self.openrouter:
            headers["X-Title"] = "SkelCAD"
        self.client = httpx.Client(timeout=timeout, headers=headers)
        self.usage: dict[str, float] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0, "calls": 0}

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.openrouter:
            body["usage"] = {"include": True}  # OpenRouter отдаёт стоимость запроса
        r = self.client.post(self.base + "/chat/completions", json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"провайдер модели ответил {r.status_code}: {r.text[:300]}")
        data = r.json()
        u = data.get("usage") or {}
        self.usage["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens"):
            self.usage[k] += int(u.get(k) or 0)
        cost = response_cost(u, r.headers)
        if cost:
            self.usage["cost"] = round(self.usage["cost"] + cost, 6)
        return data["choices"][0]["message"]


def openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": (t.get("description") or "")[:1024],
                "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def _clip(s: str, n: int = 6000) -> str:
    return s if len(s) <= n else s[:n] + f"\n… (обрезано, всего {len(s)} символов)"


def task_text(task: dict) -> str:
    """Текст задачи для модели: проект, вариант, задача конструктора, список вложений."""
    variant = f" Вариант: {task['variant']}." if task.get("variant") else ""
    text = f"Проект «{task['project']}».{variant}\n\nЗадача от конструктора ({task.get('user', '?')}):\n{task['text']}"
    atts = task.get("attachments") or []
    if atts:
        text += "\n\nВложения конструктора к задаче (изображения ниже; посмотреть снова — attachment): "
        text += ", ".join(atts)
    return text


def _image_parts(images: list[dict]) -> list[dict]:
    return [{"type": "image_url", "image_url": {"url": f"data:{im['mime']};base64,{im['b64']}"}} for im in images]


def run_loop(
    task: dict,
    llm: LLM,
    bridge: ToolBridge,
    emit: Callable[..., None],
    should_stop: Callable[[], bool],
    on_step: Callable[[int], None] | None = None,
) -> dict:
    """Цикл агента. Возвращает {status, result, steps}."""
    tools = openai_tools(bridge.list_tools())
    user = task_text(task)
    emit("start", runner="openai", tools=len(tools), provider=task.get("provider"), model=task.get("model"))
    # вложения задачи — сразу в первое сообщение как изображения (модель видит набросок, не дожидаясь вызова)
    content: list[dict] = [{"type": "text", "text": user}]
    for path in task.get("attachments") or []:
        try:
            out = bridge.call("attachment", {"project": task["project"], "path": path})
        except Exception as e:  # noqa: BLE001 — вложение не читается: модель узнает из текста
            out = ToolOutput(f"ОШИБКА вложения {path}: {type(e).__name__}: {e}")
        images = getattr(out, "images", None) or []
        content.append({"type": "text", "text": f"Вложение {path}: {_clip(str(out), 2000)}"})
        content += _image_parts(images)
        emit("attachment", path=path, images=len(images), text=_clip(str(out), 300))
    first: str | list[dict] = content if len(content) > 1 else user
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": first}]
    steps = 0
    max_steps = int(task.get("max_steps") or 60)
    while True:
        usage = getattr(llm, "usage", None)
        if should_stop():
            emit("stopped", usage=usage)
            return {"status": "stopped", "result": None, "steps": steps, "usage": usage}
        if steps >= max_steps:
            emit("limit", max_steps=max_steps, usage=usage)
            return {"status": "limit", "result": f"достигнут лимит шагов ({max_steps})", "steps": steps, "usage": usage}
        steps += 1
        on_step and on_step(steps)
        msg = llm.chat(messages, tools)
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": content, **({"tool_calls": calls} if calls else {})})
        if content:
            emit("assistant", text=content)
        if not calls:
            emit("done", text=content, usage=getattr(llm, "usage", None))
            return {"status": "done", "result": content, "steps": steps, "usage": getattr(llm, "usage", None)}
        pictures: list[dict] = []  # изображения из инструментов этого шага — одним сообщением после ответов
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            emit("tool_call", name=name, args=args)
            t0 = time.monotonic()
            try:
                out = bridge.call(name, args)
            except Exception as e:  # noqa: BLE001 — ошибку инструмента отдаём модели текстом
                out = f"ОШИБКА вызова {name}: {type(e).__name__}: {e}"
            images = getattr(out, "images", None) or []
            emit("tool_result", name=name, text=_clip(str(out), 1500), seconds=round(time.monotonic() - t0, 1))
            messages.append({"role": "tool", "tool_call_id": call.get("id") or name, "content": _clip(str(out))})
            for im in images:
                label = f"Изображение из {name} {json.dumps(args, ensure_ascii=False)[:200]}:"
                pictures.append({"type": "text", "text": label})
                pictures += _image_parts([im])
        if pictures:
            # Chat Completions: картинки в ответе инструмента принимают не все провайдеры — отдаём их
            # пользовательским сообщением сразу после ответов инструментов
            messages.append({"role": "user", "content": pictures})
            emit("images", count=sum(1 for p in pictures if p["type"] == "image_url"))


# ---------------------------------------------------------------- headless Claude Code


def run_claude_code(task: dict, server_url: str, token: str | None, emit, should_stop, on_step=None) -> dict:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("исполнитель claude-code: команда claude не найдена")
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "mcp.json"
        cfg.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "skelcad": {"type": "http", "url": server_url, "headers": {"Authorization": f"Bearer {token}"}}
                    }
                }
            ),
            encoding="utf-8",
        )
        prompt = f"{SYSTEM}\n\n{task_text(task)}"
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        cmd = [
            exe, "-p", prompt, "--mcp-config", str(cfg), "--strict-mcp-config",
            "--allowedTools", "mcp__skelcad__*",
            "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Agent",
            "--max-turns", str(task.get("max_steps") or 60), "--output-format", "stream-json", "--verbose",
        ]  # fmt: skip
        emit("start", runner="claude-code")
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=td)
        steps, result = 0, None
        assert p.stdout is not None
        for line in p.stdout:
            if should_stop():
                p.terminate()
                emit("stopped")
                return {"status": "stopped", "result": None, "steps": steps}
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if m.get("type") == "assistant":
                for c in m["message"].get("content", []):
                    if c.get("type") == "text" and c["text"].strip():
                        emit("assistant", text=c["text"])
                    elif c.get("type") == "tool_use":
                        steps += 1
                        on_step and on_step(steps)
                        emit("tool_call", name=c["name"].replace("mcp__skelcad__", ""), args=c.get("input") or {})
            elif m.get("type") == "user":
                for c in m["message"].get("content", []):
                    if c.get("type") == "tool_result":
                        cc = c.get("content")
                        text = " ".join(x.get("text", "") for x in cc) if isinstance(cc, list) else str(cc or "")
                        emit("tool_result", name="", text=_clip(text, 1500))
            elif m.get("type") == "result":
                result = m.get("result")
                emit("done", text=result or "", cost_usd=m.get("total_cost_usd"))
        p.wait()
        if p.returncode != 0 and result is None:
            raise RuntimeError(
                f"claude завершился с кодом {p.returncode}: {(p.stderr.read() if p.stderr else '')[:300]}"
            )
        return {"status": "done", "result": result, "steps": steps}


# ---------------------------------------------------------------- исполнение задачи из очереди


def pick_provider(task: dict, providers: ProviderStore | None) -> dict:
    """Провайдер задачи: из providers.json (задача → умолчание), иначе — переменные окружения."""
    if providers is not None:
        p = providers.resolve(task.get("provider"), task.get("model"))
        if p is not None:
            return p
    return {
        "id": None,
        "title": "окружение",
        "kind": os.environ.get("SKELCAD_AGENT_RUNNER", "openai"),
        "base_url": os.environ.get("SKELCAD_LLM_BASE_URL", ""),
        "api_key": os.environ.get("SKELCAD_LLM_API_KEY", ""),
        "model": task.get("model") or os.environ.get("SKELCAD_LLM_MODEL", ""),
    }


def run_task(store: TaskStore, task: dict, providers: ProviderStore | None = None) -> None:
    tid = task["id"]
    server_url = os.environ.get("SKELCAD_SERVER_URL", "http://127.0.0.1:8000/mcp")
    token = os.environ.get("SKELCAD_AGENT_TOKEN") or None

    def emit(kind: str, **data):
        store.event(tid, kind, **data)

    def should_stop() -> bool:
        return store.stop_requested(tid)

    def on_step(n: int) -> None:
        store.progress(tid, n)

    try:
        prov = pick_provider(task, providers)
        task = {**task, "provider": prov.get("id") or task.get("provider"), "model": prov.get("model")}
        if prov["kind"] == "claude-code":
            res = run_claude_code(task, server_url, token, emit, should_stop, on_step)
        else:
            llm = OpenAICompatible(prov["base_url"], prov["api_key"], prov["model"])
            with McpBridge(server_url, token) as bridge:
                res = run_loop(task, llm, bridge, emit, should_stop, on_step)
        store.finish(tid, res["status"], result=res.get("result"), usage=res.get("usage"), model=prov.get("model"))
    except ProviderError as e:
        log.error("задача %s: %s", tid, e)
        emit("error", text=str(e))
        store.finish(tid, "failed", error=str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("задача %s упала", tid)
        emit("error", text=f"{type(e).__name__}: {e}")
        store.finish(tid, "failed", error=f"{type(e).__name__}: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skelcad agent", description="агент из workbench: очередь задач → цикл с моделью")
    ap.add_argument("--queue", required=True, help="папка очереди задач (/data/tasks)")
    ap.add_argument("--providers", help="файл провайдеров модели (по умолчанию <очередь>/../providers.json)")
    ap.add_argument("--once", action="store_true", help="выполнить одну задачу и выйти")
    ap.add_argument("--poll", type=float, default=2.0)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
    store = TaskStore(Path(a.queue))
    providers = ProviderStore(Path(a.providers) if a.providers else Path(a.queue).resolve().parent / "providers.json")
    log.info(
        "агент ждёт задачи в %s (провайдеры %s, иначе исполнитель %s)",
        a.queue,
        providers.path,
        os.environ.get("SKELCAD_AGENT_RUNNER", "openai"),
    )
    while True:
        task = store.claim()
        if task:
            log.info("задача %s: проект %s, %s", task["id"], task["project"], task["text"][:60])
            run_task(store, task, providers)
            if a.once:
                return 0
        else:
            time.sleep(a.poll)
