"""Подключение к Postgres для графа связей: пул соединений, схема с версией, встроенный сервер для разработки и
тестов (`SKELCAD_DATABASE_URL=embedded` → pgserver в <data>/pg). Индекс одноразовый: при смене версии схемы
таблицы пересоздаются, данные берутся заново из git и комплектов сборок."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger("skelcad.graph")

SCHEMA_VERSION = "1"

DDL = [
    "CREATE TABLE IF NOT EXISTS graph_meta (key text PRIMARY KEY, value text NOT NULL)",
    """CREATE TABLE IF NOT EXISTS graph_entity (
        project text NOT NULL,
        variant text NOT NULL DEFAULT '',
        ref text NOT NULL,
        kind text NOT NULL,
        eid text NOT NULL,
        name text NOT NULL DEFAULT '',
        text text NOT NULL DEFAULT '',
        data jsonb NOT NULL DEFAULT '{}'::jsonb,
        commit text NOT NULL DEFAULT '',
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (project, variant, ref))""",
    "CREATE INDEX IF NOT EXISTS graph_entity_kind ON graph_entity (kind, project)",
    "CREATE INDEX IF NOT EXISTS graph_entity_ref ON graph_entity (ref)",
    """CREATE TABLE IF NOT EXISTS graph_relation (
        project text NOT NULL,
        variant text NOT NULL DEFAULT '',
        src text NOT NULL,
        dst text NOT NULL,
        kind text NOT NULL,
        data jsonb NOT NULL DEFAULT '{}'::jsonb,
        commit text NOT NULL DEFAULT '',
        PRIMARY KEY (project, variant, src, dst, kind))""",
    "CREATE INDEX IF NOT EXISTS graph_relation_src ON graph_relation (project, src)",
    "CREATE INDEX IF NOT EXISTS graph_relation_dst ON graph_relation (project, dst)",
    "CREATE INDEX IF NOT EXISTS graph_relation_dst_all ON graph_relation (dst)",
    """CREATE TABLE IF NOT EXISTS graph_state (
        project text NOT NULL,
        variant text NOT NULL DEFAULT '',
        commit text NOT NULL DEFAULT '',
        entities integer NOT NULL DEFAULT 0,
        relations integer NOT NULL DEFAULT 0,
        indexed_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (project, variant))""",
]
TABLES = ("graph_entity", "graph_relation", "graph_state", "graph_meta")


class Graph:
    """Пул соединений с Postgres и схема индекса. `close()` закрывает пул и встроенный сервер, если он наш."""

    def __init__(self, url: str, server: Any = None, max_size: int = 4, timeout: float = 10.0):
        self.url = url
        self._server = server
        self.pool = ConnectionPool(
            url, min_size=1, max_size=max_size, timeout=timeout, kwargs={"row_factory": dict_row}, open=True
        )
        self.ensure_schema()

    @classmethod
    def open(cls, url: str | None, data_dir: Path | None = None) -> Graph | None:
        """URL Postgres → Graph; «embedded» → встроенный сервер (pgserver, dev-зависимость) в <data>/pg;
        пусто → None (граф выключен). Недоступная база — ошибка в журнале и None: сервер работает без графа,
        /health показывает `graph: error`."""
        if not url:
            return None
        server = None
        try:
            if url == "embedded":
                import pgserver

                pgdata = Path(data_dir or ".tmp/data") / "pg"
                pgdata.mkdir(parents=True, exist_ok=True)
                server = pgserver.get_server(str(pgdata))
                url = server.get_uri()
            return cls(url, server)
        except Exception as e:  # noqa: BLE001 — любая ошибка подключения: сервер поднимается без графа
            log.error("граф связей недоступен: %s", str(e).strip()[:300])
            if server is not None:
                server.cleanup()
            return None

    def connection(self):
        return self.pool.connection()

    def ensure_schema(self) -> None:
        with self.pool.connection() as c:
            c.execute(DDL[0])
            row = c.execute("SELECT value FROM graph_meta WHERE key = 'schema'").fetchone()
            if row and row["value"] != SCHEMA_VERSION:
                log.info("схема графа %s → %s: таблицы пересоздаются", row["value"], SCHEMA_VERSION)
                for t in TABLES:
                    c.execute(f"DROP TABLE IF EXISTS {t}")
                c.execute(DDL[0])
            for stmt in DDL[1:]:
                c.execute(stmt)
            c.execute(
                "INSERT INTO graph_meta (key, value) VALUES ('schema', %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (SCHEMA_VERSION,),
            )
        try:  # триграммы ускоряют поиск по подстроке; без расширения поиск работает через ILIKE
            with self.pool.connection() as c:
                c.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                c.execute(
                    "CREATE INDEX IF NOT EXISTS graph_entity_text_trgm ON graph_entity USING gin (text gin_trgm_ops)"
                )
        except psycopg.Error as e:
            log.info("pg_trgm недоступен (%s) — поиск без триграммного индекса", str(e).strip()[:120])

    def ok(self) -> bool:
        try:
            with self.pool.connection() as c:
                c.execute("SELECT 1")
            return True
        except psycopg.Error:
            return False

    def close(self) -> None:
        self.pool.close()
        if self._server is not None:
            self._server.cleanup()
            self._server = None
