"""HTTP-приложение SkelCAD: /mcp (агент, Bearer-токен), /api (то же для CLI и workbench), /out (артефакты).

Окружение:
  SKELCAD_DATA       папка данных: projects/, out/ (по умолчанию .tmp/data)
  SKELCAD_TOKENS     токены клиентов «имя:токен;имя2:токен2»; имя попадает в автора коммитов.
                     Не задано — доступ без токена под именем anonymous (только для разработки).
  SKELCAD_JOBS       папка файловой очереди воркера; не задано — воркер подпроцессом здесь же
  SKELCAD_SEED       проекты-примеры, которые завести при старте (по умолчанию bracket,pipe_support)
  SKELCAD_TEMPLATES  папка шаблонов проектов (по умолчанию examples/ репозитория)
  PUBLIC_URL         внешний адрес для ссылок на артефакты
"""

from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager

from anyio import to_thread
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from skelcad.server.mcp import CURRENT_CLIENT, build_mcp
from skelcad.server.tools import Server, ToolError, Tools

log = logging.getLogger("skelcad.server")


def parse_tokens(raw: str | None) -> dict[str, str]:
    """«claude-code:abc;cursor:def» -> {token: client}."""
    out = {}
    for item in (raw or "").replace(",", ";").split(";"):
        item = item.strip()
        if not item:
            continue
        name, _, token = item.partition(":")
        if not token:
            raise ValueError(f"SKELCAD_TOKENS: ожидалось «имя:токен», получено «{item[:20]}»")
        out[token.strip()] = name.strip()
    return out


def client_for(request: Request, tokens: dict[str, str]) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    given = auth[7:].strip().encode()
    for token, name in tokens.items():
        if hmac.compare_digest(given, token.encode()):
            return name
    return None


def create_app(srv: Server | None = None) -> FastAPI:
    srv = srv or Server.from_env()
    tokens = parse_tokens(os.environ.get("SKELCAD_TOKENS"))
    if not tokens:
        log.warning("SKELCAD_TOKENS не задан — доступ без токена (режим разработки)")
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
        if path == "/health" or path.startswith("/out/"):
            return await call_next(request)
        if tokens:
            name = client_for(request, tokens)
            if not name:
                return JSONResponse({"error": "нужен Bearer-токен клиента SkelCAD"}, status_code=401)
        else:
            name = "anonymous"
        token = CURRENT_CLIENT.set(name)
        try:
            return await call_next(request)
        finally:
            CURRENT_CLIENT.reset(token)

    @app.get("/health")
    async def health():
        return {"ok": True, "projects": srv.workspace.names()}

    @app.get("/api/projects")
    async def api_projects():
        return await to_thread.run_sync(tools.project_list)

    @app.get("/api/projects/{name}")
    async def api_project(name: str):
        return await to_thread.run_sync(tools.project_read, name)

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
    # MCP-приложение последним: его маршрут /mcp, остальное FastAPI уже разобрал выше.
    app.mount("/", mcp_app)
    return app


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(create_app(), host=host, port=port, proxy_headers=True, forwarded_allow_ips="*")
