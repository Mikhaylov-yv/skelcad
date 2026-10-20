"""Индексатор: читает проект (project.yaml, варианты, замечания, состояние компоновки) и комплекты сборок
вариантов, пишет сущности и связи в Postgres. Вызывается после коммита (слушатель Workspace), после сборки и
при старте сервера; неизменившийся коммит или сборка пропускаются по `graph_state`."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from psycopg.types.json import Jsonb

from skelcad.core.model import Project
from skelcad.core.project import read_spec
from skelcad.graph.db import Graph
from skelcad.graph.extract import Ent, Rel, extract_project, extract_variant
from skelcad.server.workspace import Workspace

log = logging.getLogger("skelcad.graph")


class Indexer:
    def __init__(self, graph: Graph, ws: Workspace):
        self.g = graph
        self.ws = ws

    # ---------------------------------------------------------------- запись

    def _state(self, c, project: str, variant: str) -> str | None:
        row = c.execute(
            "SELECT commit FROM graph_state WHERE project = %s AND variant = %s", (project, variant)
        ).fetchone()
        return row["commit"] if row else None

    def _write(self, c, project: str, variant: str, stamp: str, ents: list[Ent], rels: list[Rel]) -> None:
        c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (project,))
        c.execute("DELETE FROM graph_entity WHERE project = %s AND variant = %s", (project, variant))
        c.execute("DELETE FROM graph_relation WHERE project = %s AND variant = %s", (project, variant))
        with c.cursor() as cur:
            cur.executemany(
                "INSERT INTO graph_entity (project, variant, ref, kind, eid, name, text, data, commit) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [(project, variant, e.ref, e.kind, e.eid, e.name, e.text, Jsonb(e.data), stamp) for e in ents],
            )
            cur.executemany(
                "INSERT INTO graph_relation (project, variant, src, dst, kind, data, commit) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [(project, variant, r.src, r.dst, r.kind, Jsonb(r.data), stamp) for r in rels],
            )
        c.execute(
            "INSERT INTO graph_state (project, variant, commit, entities, relations, indexed_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) ON CONFLICT (project, variant) DO UPDATE SET "
            "commit = EXCLUDED.commit, entities = EXCLUDED.entities, relations = EXCLUDED.relations, "
            "indexed_at = now()",
            (project, variant, stamp, len(ents), len(rels)),
        )

    def _drop(self, c, project: str, variant: str | None = None) -> None:
        for t in ("graph_entity", "graph_relation", "graph_state"):
            if variant is None:
                c.execute(f"DELETE FROM {t} WHERE project = %s", (project,))
            else:
                c.execute(f"DELETE FROM {t} WHERE project = %s AND variant = %s", (project, variant))

    # ---------------------------------------------------------------- проект и варианты

    def index_project(self, name: str, force: bool = False) -> dict:
        """Уровень проекта по HEAD; варианты, которых больше нет в папке variants, удаляются из индекса."""
        from skelcad.server import layout, review  # здесь, а не наверху: server.layout импортирует core

        root = self.ws.path(name)
        head = self.ws.rev(name, "HEAD")[:12]
        with self.g.connection() as c:
            if not force and self._state(c, name, "") == head:
                return {"project": name, "commit": head, "skipped": True}
        variants = self.ws.variants(name)
        try:
            spec = read_spec(root)
        except Exception as e:  # noqa: BLE001 — проект с ошибкой в YAML всё равно виден в индексе, с текстом ошибки
            ents, rels = [Ent(f"project:{name}", "project", name, name, name, {"error": str(e)[:300]})], []
        else:
            reviews = review.list_items(self.ws, name)
            try:
                lay = layout.state(self.ws, name)
            except Exception:  # noqa: BLE001
                lay = None
            ents, rels = extract_project(name, spec, variants, reviews, lay)
        known = [v["id"] for v in variants]
        with self.g.connection() as c:
            self._write(c, name, "", head, ents, rels)
            for t in ("graph_entity", "graph_relation", "graph_state"):
                c.execute(
                    f"DELETE FROM {t} WHERE project = %s AND variant <> '' AND NOT (variant = ANY(%s))", (name, known)
                )
        return {"project": name, "commit": head, "entities": len(ents), "relations": len(rels)}

    def index_variant(self, name: str, variant: str, force: bool = False) -> dict:
        """Уровень варианта по последней сборке (out/<p>/<v>/model.yaml, report.json, <v>_sketch.json);
        без сборки — строки варианта удаляются."""
        out = self.ws.out_dir / name / variant
        model_f = out / "model.yaml"
        if not model_f.is_file():
            with self.g.connection() as c:
                self._drop(c, name, variant)
            return {"project": name, "variant": variant, "built": False}
        stamp = f"build:{model_f.stat().st_mtime_ns}"
        with self.g.connection() as c:
            if not force and self._state(c, name, variant) == stamp:
                return {"project": name, "variant": variant, "skipped": True}
        try:
            m = Project.model_validate(yaml.safe_load(model_f.read_text(encoding="utf-8")) or {})
        except Exception as e:  # noqa: BLE001 — старый комплект не читается текущей моделью: строки варианта снимаем
            log.warning("индекс связей (%s/%s): model.yaml не читается: %s", name, variant, str(e)[:200])
            with self.g.connection() as c:
                self._drop(c, name, variant)
            return {"project": name, "variant": variant, "built": True, "error": str(e)[:300]}
        report = _json(out / "report.json")
        sketch = _json(out / f"{variant}_sketch.json")
        try:
            skip = {a.id for a in read_spec(self.ws.path(name)).assumptions}
        except Exception:  # noqa: BLE001
            skip = set()
        ents, rels = extract_variant(variant, m, report, sketch, skip)
        with self.g.connection() as c:
            self._write(c, name, variant, stamp, ents, rels)
        return {"project": name, "variant": variant, "entities": len(ents), "relations": len(rels)}

    def index_all(self, force: bool = False) -> dict:
        """Все проекты и собранные варианты; проекты, которых нет на диске, удаляются из индекса."""
        names = self.ws.names()
        with self.g.connection() as c:
            for t in ("graph_entity", "graph_relation", "graph_state"):
                c.execute(f"DELETE FROM {t} WHERE NOT (project = ANY(%s))", (names,))
        done, skipped = 0, 0
        for n in names:
            try:
                r = self.index_project(n, force=force)
            except Exception as e:  # noqa: BLE001 — один сломанный проект не должен останавливать проход
                log.warning("индекс связей: проект %s пропущен: %s", n, e)
                continue
            skipped += 1 if r.get("skipped") else 0
            done += 0 if r.get("skipped") else 1
            for v in self.ws.variants(n):
                try:
                    rv = self.index_variant(n, v["id"], force=force)
                except Exception as e:  # noqa: BLE001 — сломанный комплект одного варианта не мешает остальным
                    log.warning("индекс связей: вариант %s/%s пропущен: %s", n, v["id"], e)
                    continue
                skipped += 1 if rv.get("skipped") else 0
                done += 0 if rv.get("skipped") or not rv.get("entities") else 1
        return {"projects": len(names), "indexed": done, "skipped": skipped}

    def drop_project(self, name: str) -> None:
        with self.g.connection() as c:
            self._drop(c, name)


def _json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
