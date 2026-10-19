# SkelCAD — один образ для сервера (`skelcad serve`) и воркера (`skelcad worker --queue /data/jobs`).

# 1. Workbench (web/) → статика; отдаётся сервером по «/».
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build -- --outDir /web/dist --emptyOutDir

# 2. Сервер.
FROM python:3.12-slim

# git — проекты-репозитории; libGL/X11 — зависимости OCCT (OCP), без них импорт build123d падает.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates libgl1 libglx0 libx11-6 libxcb1 libxau6 libxdmcp6 libfontconfig1 libfreetype6 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/app/.venv

# сначала зависимости (кэшируемый слой), потом код
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-extras --no-install-project --no-install-workspace

COPY src ./src
COPY examples ./examples
COPY --from=web /web/dist ./src/skelcad/server/static
RUN uv sync --frozen --no-dev --all-extras

RUN useradd -m -u 1000 skelcad && mkdir -p /data && chown skelcad:skelcad /data
USER skelcad
ENV PATH=/app/.venv/bin:$PATH \
    SKELCAD_DATA=/data \
    SKELCAD_TEMPLATES=/app/examples \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["skelcad", "serve", "--host", "0.0.0.0", "--port", "8000"]
