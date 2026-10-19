"""HTTP-приложение SkelCAD: /mcp (агент, Bearer-токен), /api (то же для CLI и workbench), /out (артефакты).

Окружение:
  SKELCAD_DATA       папка данных: projects/, out/ (по умолчанию .tmp/data)
  SKELCAD_TOKENS     токены клиентов «имя:токен;имя2:токен2»; имя попадает в автора коммитов.
                     Не задано — доступ без токена под именем anonymous (только для разработки).
  SKELCAD_AUTH       вход для браузера (/, /api, /out): none | tokens | proxy — см. auth.py
  SKELCAD_JOBS       папка файловой очереди воркера; не задано — воркер подпроцессом здесь же
  SKELCAD_SEED       проекты-примеры, которые завести при старте (по умолчанию bracket,pipe_support)
  SKELCAD_TEMPLATES  папка шаблонов проектов (по умолчанию examples/ репозитория)
  PUBLIC_URL         внешний адрес для ссылок на артефакты
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from anyio import to_thread
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from skelcad.server import api
from skelcad.server.auth import CURRENT_PRINCIPAL, client_for, parse_tokens, resolve, web_mode
from skelcad.server.mcp import CURRENT_CLIENT, build_mcp
from skelcad.server.tools import Server, ToolError, Tools

__all__ = ["client_for", "create_app", "main", "parse_tokens"]

log = logging.getLogger("skelcad.server")
STATIC = Path(__file__).parent / "static"
PLACEHOLDER = """<!doctype html><html lang="ru"><meta charset="utf-8"><title>SkelCAD</title>
<body style="font:15px system-ui;padding:2em;max-width:40em"><h1>SkelCAD</h1>
<p>Рабочее место не собрано. Соберите его: <code>cd web &amp;&amp; npm ci &amp;&amp; npm run build</code>
(в образе это делает Dockerfile).
Точка MCP для агентов: <code>/mcp</code>, REST: <code>/api/docs</code>.</p></body></html>"""


def create_app(srv: Server | None = None) -> FastAPI:
    srv = srv or Server.from_env()
    tokens = parse_tokens(os.environ.get("SKELCAD_TOKENS"))
    mode = web_mode(tokens)
    if not tokens:
        log.warning("SKELCAD_TOKENS не задан — доступ без токена (режим разработки)")
    log.info("вход для браузера: SKELCAD_AUTH=%s", mode)
    mcp = build_mcp(srv)
    mcp_app = mcp.streamable_http_app()
    tools = Tools(srv)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        seed = [s.strip() for s in os.environ.get("SKELCAD_SEED", "bracket,pipe_support").split(",")]
        made = await to_thread.run_sync(srv.workspace.seed, seed)
        if made:
            log.info("заведены проекты-примеры: %s", ", ".join(made))
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="SkelCAD", version="0.1", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
    )
    app.state.server = srv

    @app.middleware("http")
    async def auth(request: Request, call_next):
        path = request.url.path
        if path == "/health":
            return await call_next(request)
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
        return {"ok": True, "projects": srv.workspace.names()}

    @app.get("/api/me")
    async def api_me(request: Request):
        who = request.state.principal
        return {
            "name": who.name,
            "kind": who.kind,
            "email": who.email,
            "auth": mode,
            "logout_url": "/oauth2/sign_out?rd=" + srv.public_url if mode == "proxy" else None,
        }

    @app.get("/api/projects")
    async def api_projects():
        return await to_thread.run_sync(api.projects_overview, srv.workspace, srv.workspace.out_dir)

    @app.get("/api/projects/{name}")
    async def api_project(name: str):
        return await to_thread.run_sync(tools.project_read, name)

    @app.get("/api/projects/{name}/variants/{variant}/report")
    async def api_variant_report(name: str, variant: str):
        try:
            return await to_thread.run_sync(api.variant_report, srv.workspace, srv.workspace.out_dir, name, variant)
        except api.NotBuilt as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/api/projects/{name}/variants/{variant}/params")
    async def api_variant_params(name: str, variant: str):
        return await to_thread.run_sync(api.variant_params, srv.workspace, name, variant)

    @app.post("/api/projects/{name}/variants/{variant}/draft")
    async def api_variant_draft(name: str, variant: str, request: Request):
        body = await request.json()
        return await to_thread.run_sync(api.variant_draft, srv, name, variant, body.get("params") or {})

    @app.post("/api/projects/{name}/variants/{variant}/params")
    async def api_variant_save(name: str, variant: str, request: Request):
        body = await request.json()
        return await to_thread.run_sync(
            api.variant_save, srv, name, variant, body.get("params") or {}, body.get("message") or "", body.get("draft")
        )

    @app.get("/api/projects/{name}/review")
    async def api_review(name: str, status: str = "all"):
        return await to_thread.run_sync(tools.review_list, name, status)

    @app.post("/api/projects/{name}/review")
    async def api_review_add(name: str, request: Request):
        b = await request.json()
        return await to_thread.run_sync(
            tools.review_add, name, b.get("text", ""), b.get("variant"), b.get("part"), b.get("point"), "workbench"
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

    for exc in ToolError:
        app.add_exception_handler(exc, tool_error)

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
