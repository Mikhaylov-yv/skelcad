"""HTTP-приложение SkelCAD: /mcp (агент, Bearer-токен), /api (то же для CLI и workbench), /out (артефакты).

Окружение:
  SKELCAD_DATA       папка данных: projects/, out/ (по умолчанию .tmp/data)
  SKELCAD_TOKENS     токены клиентов «имя:токен;имя2:токен2»; имя попадает в автора коммитов.
                     Не задано — доступ без токена под именем anonymous (только для разработки).
  SKELCAD_AUTH       вход для браузера (/, /api, /out): none | tokens | proxy — см. auth.py
  SKELCAD_AGENT_TOKEN токен встроенного агента (клиент «workbench-agent», контейнер agent)
  SKELCAD_TASKS      папка очереди задач агенту (по умолчанию <SKELCAD_DATA>/tasks)
  SKELCAD_JOBS       папка файловой очереди воркера; не задано — воркер подпроцессом здесь же
  SKELCAD_SEED       проекты-примеры, которые завести при старте (по умолчанию bracket,pipe_support,plate)
  SKELCAD_TEMPLATES  папка шаблонов проектов (по умолчанию examples/ репозитория)
  PUBLIC_URL         внешний адрес для ссылок на артефакты
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from anyio import to_thread
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from skelcad.server import api, decisions, stages, thread
from skelcad.server import providers as PV
from skelcad.server.auth import CURRENT_PRINCIPAL, client_for, current_actor, parse_tokens, resolve, web_mode
from skelcad.server.mcp import CURRENT_CLIENT, build_mcp
from skelcad.server.providers import ProviderError, ProviderStore
from skelcad.server.tasks import TaskError, TaskStore
from skelcad.server.tokens import TokenError, TokenStore
from skelcad.server.tools import GraphOff, Server, ToolError, Tools

__all__ = ["client_for", "create_app", "main", "parse_tokens"]

log = logging.getLogger("skelcad.server")
STATIC = Path(__file__).parent / "static"


def auto_continue() -> bool:
    """После «Согласовать компоновку» агент сам берётся за детали (D32); SKELCAD_AUTO_CONTINUE=0 выключает."""
    return os.environ.get("SKELCAD_AUTO_CONTINUE", "1").strip().lower() not in ("0", "false", "no", "off")


PLACEHOLDER = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>SkelCAD</title>
<body style="font:15px system-ui;padding:2em;max-width:40em"><h1>SkelCAD</h1>
<p>Рабочее место не собрано. Соберите его: <code>cd web &amp;&amp; npm ci &amp;&amp; npm run build</code>
(в образе это делает Dockerfile).
Точка MCP для агентов: <code>/mcp</code>, REST: <code>/api/docs</code>.</p></body></html>"""


def create_app(srv: Server | None = None) -> FastAPI:
    srv = srv or Server.from_env()
    static_tokens = parse_tokens(os.environ.get("SKELCAD_TOKENS"))
    if agent_token := os.environ.get("SKELCAD_AGENT_TOKEN"):
        static_tokens[agent_token] = "workbench-agent"
    token_store = TokenStore(srv.workspace.root / "tokens.json")
    mode = web_mode(static_tokens)
    tokens_mode = bool(static_tokens)  # токены обязательны, если заданы статические (prod)
    tasks = TaskStore(Path(os.environ.get("SKELCAD_TASKS") or (srv.workspace.root / "tasks")))
    providers = ProviderStore(
        srv.workspace.root / "providers.json"
    )  # провайдеры модели (D29); агент читает тот же файл
    if not PV.secure():
        log.warning("SKELCAD_SECRET_KEY не задан — ключи провайдеров модели хранятся без шифрования")
    if not static_tokens:
        log.warning("SKELCAD_TOKENS не задан — доступ без токена (режим разработки)")
    log.info("вход для браузера: SKELCAD_AUTH=%s", mode)
    mcp = build_mcp(srv)
    mcp_app = mcp.streamable_http_app()
    tools = Tools(srv)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        seed = [s.strip() for s in os.environ.get("SKELCAD_SEED", "bracket,pipe_support,plate").split(",")]
        made = await to_thread.run_sync(srv.workspace.seed, seed)
        if made:
            log.info("заведены проекты-примеры: %s", ", ".join(made))
        if srv.indexer is not None:  # граф связей: полный проход при старте (неизменившееся пропускается)
            try:
                r = await to_thread.run_sync(srv.indexer.index_all)
                log.info(
                    "граф связей: проектов %s, проиндексировано %s, без изменений %s",
                    r["projects"],
                    r["indexed"],
                    r["skipped"],
                )
            except Exception as e:  # noqa: BLE001 — сервер работает и без индекса
                log.error("граф связей при старте: %s", e)
        async with mcp.session_manager.run():
            yield
        if srv.graph is not None:
            srv.graph.close()

    app = FastAPI(
        title="SkelCAD", version="0.1", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
    )
    app.state.server = srv
    app.state.tasks = tasks

    @app.middleware("http")
    async def auth(request: Request, call_next):
        path = request.url.path
        if path == "/health":
            return await call_next(request)
        tokens = {**static_tokens, **token_store.tokens()} if tokens_mode else {}
        who = resolve(request, tokens, mode)
        if who is None:
            msg = "нужен Bearer-токен клиента SkelCAD" if path == "/mcp" or mode == "tokens" else "нужен вход"
            return JSONResponse({"error": msg}, status_code=401)
        request.state.principal = who
        token = CURRENT_CLIENT.set(who.name)
        ptoken = CURRENT_PRINCIPAL.set(who)
        try:
            return await call_next(request)
        finally:
            CURRENT_PRINCIPAL.reset(ptoken)
            CURRENT_CLIENT.reset(token)

    @app.get("/health")
    async def health():
        return {"ok": True, "projects": srv.workspace.names(), "graph": srv.graph_status()}

    @app.get("/api/me")
    async def api_me(request: Request):
        who = request.state.principal
        return {
            "name": who.name,
            "kind": who.kind,
            "email": who.email,
            "auth": mode,
            "admin": who.admin,
            "logout_url": "/oauth2/sign_out?rd=" + srv.public_url if mode == "proxy" else None,
        }

    def admin_only(request: Request) -> None:
        if not request.state.principal.admin:
            raise HTTPException(403, "только для администраторов (группа admins)")

    @app.get("/api/tokens")
    async def api_tokens(request: Request):
        admin_only(request)
        static = [
            {"name": n, "created": None, "created_by": "SKELCAD_TOKENS"} for n in sorted(set(static_tokens.values()))
        ]
        return {"tokens": static + token_store.list(), "mcp_url": srv.public_url + "/mcp"}

    @app.post("/api/tokens")
    async def api_token_create(request: Request):
        admin_only(request)
        b = await request.json()
        who = request.state.principal.name
        res = token_store.create((b.get("name") or "").strip(), who, set(static_tokens.values()))
        cmd = (
            f"claude mcp add --transport http skelcad {srv.public_url}/mcp "
            f'--header "Authorization: Bearer {res["token"]}"'
        )
        return {**res, "mcp_url": srv.public_url + "/mcp", "command": cmd}

    @app.delete("/api/tokens/{name}")
    async def api_token_delete(name: str, request: Request):
        admin_only(request)
        token_store.delete(name)
        return {"ok": True}

    @app.get("/api/projects")
    async def api_projects():
        return await to_thread.run_sync(api.projects_overview, srv.workspace, srv.workspace.out_dir, tasks)

    @app.post("/api/projects")
    async def api_project_create(request: Request):
        """Новый проект из рабочего места: пустой или из шаблона; первый коммит — от имени конструктора."""
        b = await request.json()
        b = b if isinstance(b, dict) else {}
        name = str(b.get("name") or "").strip()
        title = str(b.get("title") or "").strip() or None
        template = str(b.get("template") or "").strip() or None
        folder = str(b.get("folder") or "").strip() or None
        parent = str(b.get("parent") or "").strip() or None
        return await to_thread.run_sync(tools.project_create, name, template, "workbench", None, title, folder, parent)

    def guard(project: str) -> None:
        """Правки из workbench закрыты, пока проект у агента (D6: очерёдность)."""
        if (a := tasks.active(project)) is not None:
            raise HTTPException(409, f"проект у агента (задача {a['id']}, {a['status']}); остановите её или дождитесь")

    # ---------- папки, узлы и корзина (M2.5, D32): организация рабочего места, не модель изделия
    ws = srv.workspace

    @app.get("/api/folders")
    async def api_folders():
        return await to_thread.run_sync(lambda: {**ws.meta.tree(ws.names()), "trash": ws.trash_list()})

    @app.post("/api/folders")
    async def api_folder_create(request: Request):
        b = await request.json()
        return await to_thread.run_sync(ws.meta.folder_create, str((b or {}).get("title") or ""))

    @app.post("/api/folders/{fid}")
    async def api_folder_rename(fid: str, request: Request):
        b = await request.json()
        return await to_thread.run_sync(ws.meta.folder_rename, fid, str((b or {}).get("title") or ""))

    @app.delete("/api/folders/{fid}")
    async def api_folder_delete(fid: str):
        await to_thread.run_sync(ws.meta.folder_delete, fid, ws.names())
        return {"ok": True}

    @app.post("/api/projects/{name}/move")
    async def api_project_move(name: str, request: Request):
        """Перенести проект в папку и/или сделать узлом другого проекта; ключа нет в теле — не менять."""
        b = await request.json()
        b = b if isinstance(b, dict) else {}
        ws.path(name)
        folder = (str(b["folder"] or "").strip() or None) if "folder" in b else ...
        parent = (str(b["parent"] or "").strip() or None) if "parent" in b else ...
        return await to_thread.run_sync(lambda: ws.meta.place(name, ws.names(), folder=folder, parent=parent))

    @app.delete("/api/projects/{name}")
    async def api_project_delete(name: str):
        """В корзину вместе с узлами; вернуть — POST /api/trash/{id}/restore."""
        guard(name)
        names = ws.names()

        def below(n: str) -> list[str]:  # потомки, глубокие раньше: узлы уходят в корзину до родителя
            out: list[str] = []
            for k in ws.meta.children(n, names):
                out.extend(below(k))
                out.append(k)
            return out

        kids = below(name)
        for k in kids:
            guard(k)
        res = {"id": None, "name": name, "nodes": []}
        for k in kids:
            res["nodes"].append(await to_thread.run_sync(ws.trash, k))
            await to_thread.run_sync(tasks.archive, k, ws.root / "trash" / res["nodes"][-1]["id"] / "__tasks")
        res.update(await to_thread.run_sync(ws.trash, name))
        await to_thread.run_sync(tasks.archive, name, ws.root / "trash" / res["id"] / "__tasks")
        if srv.indexer is not None:
            for n in [name, *kids]:
                try:
                    await to_thread.run_sync(srv.indexer.drop_project, n)
                except Exception as e:  # noqa: BLE001 — индекс не должен мешать удалению
                    log.warning("индекс связей при удалении %s: %s", n, e)
        return res

    @app.get("/api/trash")
    async def api_trash():
        return {"items": await to_thread.run_sync(ws.trash_list)}

    @app.post("/api/trash/{tid}/restore")
    async def api_trash_restore(tid: str):
        await to_thread.run_sync(tasks.unarchive, ws.root / "trash" / tid / "__tasks")
        name = await to_thread.run_sync(ws.restore, tid)
        return {"name": name, **ws.meta.project(name)}

    # ---------- решения конструктора, комплект, разговор (M2.5)
    @app.post("/api/projects/{name}/choose")
    async def api_choose(name: str, request: Request):
        guard(name)
        b = await request.json()
        variant = str((b or {}).get("variant") or "").strip()
        return await to_thread.run_sync(decisions.choose, ws, name, variant, current_actor("workbench"))

    def kit_variant(name: str, variant: str | None) -> str | None:
        if variant:
            return variant
        chosen = decisions.chosen_variant(ws, name)
        if chosen:
            return chosen
        built = [v["id"] for v in ws.variants(name) if (ws.out_dir / name / v["id"] / "report.json").is_file()]
        return built[0] if built else None

    @app.get("/api/projects/{name}/kit")
    async def api_kit(name: str, variant: str | None = None):
        ws.path(name)
        v = await to_thread.run_sync(kit_variant, name, variant)
        return {"variant": v, "files": stages.kit_files(ws.out_dir, name, v) if v else []}

    @app.post("/api/projects/{name}/kit")
    async def api_kit_build(name: str, variant: str | None = None):
        """Выдать комплект: сборка выбранного варианта с экспортом (STEP, эскизы с размерами, отчёт)."""
        guard(name)
        v = await to_thread.run_sync(kit_variant, name, variant)
        if not v:
            raise HTTPException(400, "сначала выберите вариант")
        res = await to_thread.run_sync(tools.build, name, v, True)
        return {"variant": v, "files": stages.kit_files(ws.out_dir, name, v), "build": res}

    @app.get("/api/projects/{name}/kit.zip")
    async def api_kit_zip(name: str, variant: str | None = None):
        import io
        import zipfile

        ws.path(name)
        v = await to_thread.run_sync(kit_variant, name, variant)
        files = stages.kit_files(ws.out_dir, name, v) if v else []
        if not files:
            raise HTTPException(404, "комплекта ещё нет: соберите вариант с экспортом")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(ws.out_dir / name / v / f["name"], arcname=f"{name}_{v}/{f['name']}")
        from fastapi.responses import Response

        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}_{v}_kit.zip"'},
        )

    @app.get("/api/projects/{name}/thread")
    async def api_thread(name: str, limit: int = 60):
        ws.path(name)
        return await to_thread.run_sync(thread.thread, ws, tasks, name, limit)

    # ---------- задачи агенту
    @app.get("/api/projects/{name}/tasks")
    async def api_tasks(name: str, limit: int = 20):
        return {"tasks": await to_thread.run_sync(tasks.list, name, limit), "active": tasks.active(name)}

    @app.post("/api/projects/{name}/tasks")
    async def api_task_create(name: str, request: Request):
        b = await request.json()
        if name not in srv.workspace.names():
            raise HTTPException(400, f"нет проекта «{name}»")
        who = request.state.principal.name
        atts = b.get("attachments") or []
        if not isinstance(atts, list):
            raise HTTPException(400, "attachments: ожидался список путей")
        for a in atts:
            await to_thread.run_sync(tools.attachment_path, name, str(a))  # каждое вложение должно существовать
        provider = (b.get("provider") or "").strip() or None
        if provider:
            providers.get(provider)  # провайдер должен существовать (ошибка словами)
        return await to_thread.run_sync(
            tasks.create, name, b.get("text", ""), who, b.get("variant"), 60, atts, provider, b.get("model")
        )

    # ---------- провайдеры модели встроенного агента (D29): список — всем, правки — администраторам
    @app.get("/api/providers")
    async def api_providers():
        return {
            "providers": providers.list(),
            "default": providers.default_id(),
            "secure": PV.secure(),
            "presets": PV.PRESETS,
            "env": PV.env_fallback(),
        }

    @app.post("/api/providers")
    async def api_provider_save(request: Request):
        admin_only(request)
        b = await request.json()
        return await to_thread.run_sync(
            providers.upsert, b if isinstance(b, dict) else {}, request.state.principal.name
        )

    @app.delete("/api/providers/{pid}")
    async def api_provider_delete(pid: str, request: Request):
        admin_only(request)
        providers.delete(pid)
        return {"ok": True}

    @app.post("/api/providers/{pid}/default")
    async def api_provider_default(pid: str, request: Request):
        admin_only(request)
        return providers.set_default(pid)

    @app.post("/api/providers/{pid}/test")
    async def api_provider_test(pid: str, request: Request):
        """Короткий запрос к модели сохранённым ключом: время ответа, токены, стоимость."""
        admin_only(request)
        b = await request.json()
        p = providers.get(pid)
        if p["kind"] != "openai":
            return {
                "ok": True,
                "model": "",
                "reply": "",
                "seconds": 0,
                "note": "исполнитель Claude Code: ключ не нужен",
            }
        model = (b.get("model") if isinstance(b, dict) else None) or p["model"]
        return await to_thread.run_sync(PV.test_chat, p["base_url"], providers.key_for(pid), model)

    @app.post("/api/providers/models")
    async def api_provider_models(request: Request):
        """Список моделей провайдера: по сохранённому ключу (id) или по новому ключу до сохранения (base_url + key)."""
        admin_only(request)
        b = await request.json()
        b = b if isinstance(b, dict) else {}
        if b.get("id") and not b.get("key"):
            p = providers.get(str(b["id"]))
            base_url, key = (b.get("base_url") or p["base_url"]), providers.key_for(p["id"])
        else:
            base_url, key = str(b.get("base_url") or ""), str(b.get("key") or "")
        if not base_url:
            raise HTTPException(400, "нужен base_url")
        return {"models": await to_thread.run_sync(PV.fetch_models, base_url, key)}

    # ---------- вложения конструктора (M2.3, D28)
    @app.get("/api/projects/{name}/attachments")
    async def api_attachments(name: str):
        return await to_thread.run_sync(tools.attachments, name)

    @app.post("/api/projects/{name}/attachments")
    async def api_attachment_upload(name: str, file: UploadFile = File(...), note: str = Form("")):  # noqa: B008
        guard(name)
        data = await file.read()
        return await to_thread.run_sync(tools.attachment_add, name, file.filename or "file", data, note, "workbench")

    @app.get("/api/projects/{name}/attachments/{file}")
    async def api_attachment_file(name: str, file: str):
        res = await to_thread.run_sync(tools.attachment_path, name, file)
        return FileResponse(res["file"], media_type=res["mime"], headers={"Cache-Control": "private, max-age=3600"})

    @app.get("/api/projects/{name}/attachments/{file}/thumb")
    async def api_attachment_thumb(name: str, file: str):
        t = await to_thread.run_sync(tools.attachment_thumb, name, file)
        if t is None:
            raise HTTPException(404, "у файла нет миниатюры")
        return FileResponse(t, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    @app.delete("/api/projects/{name}/attachments/{file}")
    async def api_attachment_delete(name: str, file: str):
        guard(name)
        return await to_thread.run_sync(tools.attachment_remove, name, file, "workbench")

    @app.get("/api/tasks/{task_id}")
    async def api_task(task_id: str):
        return await to_thread.run_sync(tasks.get, task_id)

    @app.get("/api/tasks/{task_id}/events")
    async def api_task_events(task_id: str, since: int = 0):
        return await to_thread.run_sync(tasks.events, task_id, since)

    @app.post("/api/tasks/{task_id}/stop")
    async def api_task_stop(task_id: str):
        return await to_thread.run_sync(tasks.stop, task_id)

    @app.get("/api/tasks/{task_id}/files/{name}")
    async def api_task_file(task_id: str, name: str):
        """Картинка, которую агент получил от инструмента в ходе задачи (имя — из события tool_result.images)."""
        f, mime = await to_thread.run_sync(tasks.file_path, task_id, name)
        return FileResponse(f, media_type=mime, headers={"Cache-Control": "private, max-age=86400"})

    @app.get("/api/projects/{name}")
    async def api_project(name: str):
        return await to_thread.run_sync(tools.project_read, name)

    @app.get("/api/projects/{name}/variants/{variant}/report")
    async def api_variant_report(name: str, variant: str):
        try:
            return await to_thread.run_sync(api.variant_report, srv.workspace, srv.workspace.out_dir, name, variant)
        except api.NotBuilt as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/projects/{name}/layout")
    async def api_layout(name: str, variant: str | None = None):
        return await to_thread.run_sync(api.layout_view, tools, name, variant)

    @app.post("/api/projects/{name}/layout/approve")
    async def api_layout_approve(name: str, request: Request):
        """Согласовать компоновку; дальше ход у агента — задача «детали» ставится сразу (D32), если у проекта нет
        узлов и деталей ещё нет. В ответе task — поставленная задача или null."""
        guard(name)
        res = await to_thread.run_sync(api.layout_approve, srv.workspace, name)
        res["task"] = None
        if auto_continue() and not ws.meta.children(name, ws.names()):
            info = await to_thread.run_sync(api.project_overview, ws, ws.out_dir, name, tasks)
            if info["next"].get("act") == "run:design":
                try:
                    res["task"] = await to_thread.run_sync(
                        tasks.create, name, stages.TASK_TEXT["design"], request.state.principal.name
                    )
                except TaskError as e:
                    res["auto_error"] = str(e)
        return res

    @app.post("/api/projects/{name}/layout/edit")
    async def api_layout_edit(name: str, request: Request):
        """Правка компоновки с эскиза: положение и размеры сущностей скелета и обстановки, размер числом (M2.3)."""
        guard(name)
        body = await request.json()
        return await to_thread.run_sync(api.layout_edit, tools, name, body if isinstance(body, dict) else {})

    # ---------------- граф связей (M2.2, D27)
    @app.get("/api/graph/search")
    async def api_graph_search(q: str, project: str | None = None, kind: str | None = None, limit: int = 50):
        return await to_thread.run_sync(tools.search, q, project, kind, limit)

    @app.get("/api/graph/stats")
    async def api_graph_stats(project: str | None = None):
        return await to_thread.run_sync(tools.graph_stats, project)

    @app.post("/api/graph/reindex")
    async def api_graph_reindex(project: str | None = None):
        return await to_thread.run_sync(tools.reindex, project)

    @app.get("/api/projects/{name}/graph/links")
    async def api_graph_links(
        name: str,
        ref: str,
        variant: str | None = None,
        hops: int = 1,
        kinds: str | None = None,
        direction: str = "both",
    ):
        ks = [k for k in (kinds or "").split(",") if k] or None
        return await to_thread.run_sync(tools.links, name, ref, variant or None, hops, ks, direction)

    @app.get("/api/projects/{name}/graph/where-used")
    async def api_graph_where_used(name: str, ref: str):
        return await to_thread.run_sync(tools.where_used, ref, name)

    @app.get("/api/projects/{name}/variants/{variant}/params")
    async def api_variant_params(name: str, variant: str):
        return await to_thread.run_sync(api.variant_params, srv.workspace, name, variant)

    @app.post("/api/projects/{name}/variants/{variant}/draft")
    async def api_variant_draft(name: str, variant: str, request: Request):
        guard(name)
        body = await request.json()
        return await to_thread.run_sync(api.variant_draft, srv, name, variant, body.get("params") or {})

    @app.post("/api/projects/{name}/variants/{variant}/params")
    async def api_variant_save(name: str, variant: str, request: Request):
        guard(name)
        body = await request.json()
        return await to_thread.run_sync(
            api.variant_save, srv, name, variant, body.get("params") or {}, body.get("message") or "", body.get("draft")
        )

    @app.get("/api/projects/{name}/review")
    async def api_review(name: str, status: str = "all"):
        return await to_thread.run_sync(tools.review_list, name, status)

    @app.post("/api/projects/{name}/review")
    async def api_review_add(name: str, request: Request):
        guard(name)
        b = await request.json()
        return await to_thread.run_sync(
            tools.review_add,
            name,
            b.get("text", ""),
            b.get("variant"),
            b.get("part"),
            b.get("point"),
            "workbench",
            b.get("stroke"),
        )

    @app.post("/api/projects/{name}/review/{item_id}/resolve")
    async def api_review_resolve(name: str, item_id: str, request: Request):
        b = await request.json()
        return await to_thread.run_sync(tools.review_resolve, name, item_id, b.get("answer", ""), "workbench")

    @app.get("/api/projects/{name}/compare")
    async def api_compare(name: str, variants: str | None = None):
        vs = [v for v in (variants or "").split(",") if v] or None
        return await to_thread.run_sync(api.compare, tools, srv.workspace.out_dir, name, vs)

    @app.get("/api/projects/{name}/commits")
    async def api_commits(name: str, limit: int = 50):
        return await to_thread.run_sync(api.commits, srv.workspace, name, limit)

    @app.get("/api/projects/{name}/commits/{commit}/diff")
    async def api_commit_diff(name: str, commit: str, variant: str | None = None):
        return await to_thread.run_sync(api.commit_diff, tools, srv.workspace.out_dir, name, commit, variant)

    @app.get("/api/projects/{name}/commits/{commit}/model")
    async def api_commit_model(name: str, commit: str, variant: str):
        return await to_thread.run_sync(api.commit_model, srv, name, commit, variant)

    @app.post("/api/projects/{name}/commits/{commit}/reviewed")
    async def api_reviewed(name: str, commit: str, request: Request):
        body = await request.json()
        who = request.state.principal.name
        return await to_thread.run_sync(api.set_reviewed, srv.workspace, name, commit, bool(body.get("reviewed")), who)

    @app.post("/api/projects/{name}/revert")
    async def api_revert(name: str, request: Request):
        guard(name)
        body = await request.json()
        return await to_thread.run_sync(tools.revert, name, body["commit"], body.get("message"), "workbench")

    @app.get("/api/projects/{name}/history")
    async def api_history(name: str, limit: int = 20):
        return await to_thread.run_sync(tools.history, name, limit)

    @app.post("/api/projects/{name}/build")
    async def api_build(name: str, variant: str | None = None):
        return await to_thread.run_sync(tools.build, name, variant, True)

    async def tool_error(_: Request, e: Exception):
        return JSONResponse({"error": str(e)}, status_code=400)

    for exc in (*ToolError, TaskError, TokenError, ProviderError):
        app.add_exception_handler(exc, tool_error)

    async def graph_off(_: Request, e: Exception):
        return JSONResponse({"error": str(e)}, status_code=503)

    app.add_exception_handler(GraphOff, graph_off)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException):
        return JSONResponse({"error": e.detail}, status_code=e.status_code)

    app.mount("/out", StaticFiles(directory=str(srv.workspace.out_dir), html=True), name="out")
    if (STATIC / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(STATIC / "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def workbench(path: str):
        """Статика workbench; неизвестный путь — index.html (маршруты в браузере). Только GET: POST /mcp идёт в MCP."""
        if path.startswith(("api/", "out/", "mcp")):
            raise HTTPException(404, "нет такого пути")
        index = STATIC / "index.html"
        if not index.is_file():
            return HTMLResponse(PLACEHOLDER)
        f = STATIC / path
        if path and f.is_file() and f.resolve().is_relative_to(STATIC.resolve()):
            return FileResponse(f)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    # MCP-приложение последним: его маршрут /mcp, остальное FastAPI уже разобрал выше.
    app.mount("/", mcp_app)
    return app


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(create_app(), host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")
