"""Инструменты агента — реализации поверх ядра, без привязки к MCP SDK.

Каждый инструмент возвращает словарь; поле `summary` — одна строка для человека и агента,
остальное — данные. Тяжёлое (код проекта, OCCT) исполняется через Runner в воркере.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skelcad.context import Context, discover_standards
from skelcad.core.findings import LEVEL_RU
from skelcad.graph import Graph, Indexer
from skelcad.graph import query as gq
from skelcad.graph.extract import KINDS, RELATIONS
from skelcad.server.auth import current_actor
from skelcad.server.jobs import JobError, SubprocessRunner, make_runner
from skelcad.server.workspace import Workspace, WorkspaceError

log = logging.getLogger("skelcad.server")

ToolError = (WorkspaceError, JobError, ValueError, KeyError, LookupError)


class GraphOff(RuntimeError):
    """Граф связей не настроен (нет SKELCAD_DATABASE_URL) или недоступен."""


@dataclass
class Server:
    workspace: Workspace
    runner: Any = field(default_factory=make_runner)
    public_url: str = os.environ.get("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
    graph: Any = None  # skelcad.graph.Graph | None — индекс связей в Postgres (M2.2, D27)
    database_url: str | None = None  # URL Postgres или «embedded»; граф открывается при старте или позже (ensure_graph)
    indexer: Any = field(default=None, init=False, repr=False)
    _graph_retry_at: float = field(default=0.0, init=False, repr=False)
    _graph_opening: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.graph is not None:
            self._attach_graph()
        elif self.database_url:
            self.ensure_graph(wait=True)  # при старте — синхронно: сервер поднимается уже с индексом

    @classmethod
    def from_env(cls) -> Server:
        data = Path(os.environ.get("SKELCAD_DATA", ".tmp/data"))
        return cls(workspace=Workspace(data), database_url=os.environ.get("SKELCAD_DATABASE_URL") or None)

    def _attach_graph(self) -> None:
        self.indexer = Indexer(self.graph, self.workspace)
        self.workspace.listeners.append(self._on_commit)

    def ensure_graph(self, wait: bool = False) -> Any:
        """Граф настроен, но не открыт (база была недоступна при старте): повторная попытка не чаще раза в 30 с,
        в фоне — /health и инструменты не ждут базу; при успехе — индексатор, слушатель коммитов и полный проход.
        Возвращает Graph или None (как есть сейчас)."""
        if (
            self.graph is None
            and self.database_url
            and not self._graph_opening
            and time.monotonic() >= self._graph_retry_at
        ):
            self._graph_retry_at = time.monotonic() + 30
            self._graph_opening = True
            late = not wait
            t = threading.Thread(target=self._open_graph, args=(late,), name="graph-open", daemon=True)
            t.start()
            if wait:
                t.join()
        return self.graph

    def _open_graph(self, late: bool) -> None:
        try:
            g = Graph.open(self.database_url, self.workspace.root)
            if g is None:
                return
            self.graph = g
            self._attach_graph()
            if late:  # сервер уже работает — полный проход здесь же, в фоне
                try:
                    r = self.indexer.index_all()
                    log.info(
                        "граф связей (поздний старт): проектов %s, проиндексировано %s", r["projects"], r["indexed"]
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("граф связей (поздний старт): %s", e)
        finally:
            self._graph_opening = False

    def graph_status(self) -> str:
        """off — не настроен; ok — отвечает; error — настроен, но недоступен (повтор при следующем вызове)."""
        if not self.database_url and self.graph is None:
            return "off"
        g = self.ensure_graph()  # недоступна — попытка в фоне, ответ сразу
        return "ok" if g is not None and g.ok() else "error"

    def _on_commit(self, project: str) -> None:
        try:
            self.indexer.index_project(project)
        except Exception as e:  # noqa: BLE001 — индекс не должен ломать коммит
            log.warning("индекс связей (%s): %s", project, e)

    def index_variant(self, project: str, variant: str) -> None:
        """После сборки варианта: уровень варианта в индексе (ошибка индекса не ломает сборку)."""
        if self.indexer is None:
            return
        try:
            self.indexer.index_variant(project, variant)
        except Exception as e:  # noqa: BLE001
            log.warning("индекс связей (%s/%s): %s", project, variant, e)

    def out_dir(self, project: str) -> Path:
        d = self.workspace.out_dir / project
        d.mkdir(parents=True, exist_ok=True)
        return d

    def url(self, project: str, rel: str) -> str:
        return f"{self.public_url}/out/{project}/{rel}"


def _lvl(counts: dict) -> str:
    return ", ".join(f"{LEVEL_RU[k]} {v}" for k, v in counts.items())


def _finding_line(f: dict) -> str:
    return f"[{LEVEL_RU.get(f['level'], f['level'])}] {f['code']} {f['ref']}: {f['message']}"


class Tools:
    def __init__(self, srv: Server):
        self.srv = srv
        self.ws = srv.workspace

    # ---------------------------------------------------------------- проекты

    def project_list(self) -> dict:
        items = [self.ws.info(n) for n in self.ws.names()]
        return {
            "summary": f"проектов: {len(items)}" + (": " + ", ".join(i["name"] for i in items) if items else ""),
            "projects": items,
            "templates": self.ws.templates_list(),
        }

    def project_create(
        self, name: str, template: str | None = None, client: str = "agent", origin: str | None = None
    ) -> dict:
        info = self.ws.create(name, template=template, actor=current_actor(client), origin=origin)
        return {"summary": f"создан проект «{name}»" + (f" из шаблона {template}" if template else ""), "project": info}

    def project_read(self, project: str, section: str | None = None) -> dict:
        spec = self.ws.spec(project)
        variants = self.ws.variants(project)
        if section:
            if section == "variants":
                data = variants
            elif section in spec:
                data = spec[section]
            else:
                raise WorkspaceError(f"нет раздела «{section}»; есть: {', '.join(list(spec) + ['variants'])}")
            return {"summary": f"{project}: раздел {section}", "section": section, "data": data}
        files = self.ws.files(project)
        vnames = ", ".join(v["id"] for v in variants) or "нет"
        from skelcad.server import layout, review

        open_items = review.list_items(self.ws, project, "open")
        note = f"; открытых замечаний конструктора: {len(open_items)} (см. review_list)" if open_items else ""
        lay = layout.state(self.ws, project)
        atts = [f for f in files if f.startswith("attachments/")]
        anote = f"; вложений конструктора: {len(atts)} (см. attachment)" if atts else ""
        return {
            "summary": f"{project}: «{spec.get('title', '')}», варианты: {vnames}{note}{anote}; {layout.describe(lay)}",
            "spec": spec,
            "variants": variants,
            "files": files,
            "review_open": len(open_items),
            "attachments": atts,
            "layout": lay,
        }

    def _fresh(self, project: str) -> str:
        self.ws.pull(project)
        return str(self.ws.path(project))

    def model_query(self, project: str, variant: str | None = None, path: str | None = None) -> dict:
        self._fresh(project)
        res = self.srv.runner.run(
            "query", {"project_dir": str(self.ws.path(project)), "variant": variant, "path": path or ""}
        )
        what = f"{project}/{variant or 'база'}" + (f" → {path}" if path else " (сводка)")
        return {"summary": what, "data": res}

    # ---------------------------------------------------------------- файлы и история

    def files_read(self, project: str, path: str) -> dict:
        content = self.ws.read_file(project, path)
        return {"summary": f"{project}/{path}: {len(content.splitlines())} строк", "path": path, "content": content}

    def files_write(self, project: str, files: dict[str, str | None], message: str, client: str = "agent") -> dict:
        res = self.ws.write_files(project, files, message, current_actor(client))
        c = res["commit"]
        return {"summary": f"коммит {c['commit']} «{c['message']}»: {', '.join(res['files'])}", **res}

    def history(self, project: str, limit: int = 20, path: str | None = None) -> dict:
        items = self.ws.history(project, limit=limit, path=path)
        lines = [f"{i['commit']} {i['date'][:16]} {i['author']}: {i['message']}" for i in items]
        return {"summary": "\n".join(lines) or "история пуста", "commits": items}

    def revert(self, project: str, commit: str, message: str | None = None, client: str = "agent") -> dict:
        res = self.ws.revert(project, commit, current_actor(client), message=message)
        return {"summary": f"откат {commit} → коммит {res['commit']['commit']}", **res}

    # ---------------------------------------------------------------- замечания конструктора

    def review_list(self, project: str, status: str | None = "open") -> dict:
        from skelcad.server import review

        items = review.list_items(project=project, ws=self.ws, status=None if status == "all" else status)
        lines = [
            f"{i['id']} [{i.get('status', 'open')}]"
            + (f" {i['variant']}" if i.get("variant") else "")
            + (f" {i['part']}" if i.get("part") else "")
            + (f" @{i['point']}" if i.get("point") else "")
            + f": {i['text']}"
            + (f" — ответ: {i['answer']}" if i.get("answer") else "")
            for i in items
        ]
        return {"summary": "\n".join(lines) or "замечаний нет", "items": items}

    def review_resolve(self, project: str, id: str, answer: str, client: str = "agent") -> dict:  # noqa: A002
        from skelcad.server import review

        res = review.resolve(self.ws, project, id, answer, current_actor(client))
        return {"summary": f"{id} закрыто: {res['item']['answer']}", **res}

    def review_add(
        self,
        project: str,
        text: str,
        variant: str | None = None,
        part: str | None = None,
        point: list[float] | None = None,
        client: str = "agent",
    ) -> dict:
        from skelcad.server import review

        res = review.add(self.ws, project, text, current_actor(client), variant=variant, part=part, point=point)
        return {"summary": f"{res['item']['id']}: {res['item']['text']}", **res}

    # ---------------------------------------------------------------- вложения конструктора (M2.3, D28)

    def attachments(self, project: str) -> dict:
        from skelcad.server import attachments as A

        items = A.list_items(self.ws, project)
        lines = [
            f"{i['path']} ({A.KIND_RU.get(i['kind'], i['kind'])}"
            + (f" {i['width']}×{i['height']}" if i.get("width") else "")
            + f", {i['bytes'] // 1024} КБ)"
            for i in items
        ]
        return {"summary": "\n".join(lines) or "вложений нет", "items": items}

    def attachment_add(self, project: str, filename: str, data: bytes, note: str = "", client: str = "agent") -> dict:
        from skelcad.server import attachments as A

        res = A.add(self.ws, project, filename, data, current_actor(client), note)
        return {"summary": f"вложение {res['item']['path']}: коммит {res['commit']['commit']}", **res}

    def attachment_remove(self, project: str, path: str, client: str = "agent") -> dict:
        from skelcad.server import attachments as A

        res = A.remove(self.ws, project, path, current_actor(client))
        return {"summary": f"удалено вложение {res['path']}: коммит {res['commit']['commit']}", **res}

    def attachment_path(self, project: str, path: str) -> dict:
        from skelcad.server import attachments as A

        f = A.check_path(self.ws, project, path)
        return {"file": f, "mime": A.MIME.get(A._ext(f.name), "application/octet-stream")}

    def attachment(self, project: str, path: str) -> dict:
        """Для агента: вложение как изображение (PNG/JPEG base64) или сводка текстом (.excalidraw)."""
        from skelcad.server import attachments as A

        res = A.image(self.ws, project, path)
        it = res["item"]
        head = f"{project}/{it['path']}: {A.KIND_RU.get(it['kind'], it['kind'])}" + (
            f" {it['width']}×{it['height']}" if it.get("width") else ""
        )
        if it.get("author"):
            head += f"; добавил {it['author']} {str(it['date'])[:10]}"
        lines = [head]
        if res.get("text"):
            lines.append(res["text"])
        return {
            "summary": "\n".join(lines),
            "item": it,
            "format": res.get("format"),
            "png_base64": base64.b64encode(res["png"]).decode() if res.get("png") else None,
        }

    # ---------------------------------------------------------------- контекст

    def _ctx(self, project: str) -> Context:
        spec = self.ws.spec(project)
        stds = list(
            dict.fromkeys((spec.get("standards") or []) + ((spec.get("requirements") or {}).get("standards") or []))
        )
        return Context(stds, spec.get("tables") or {})

    def standards_list(self) -> dict:
        found = discover_standards()
        items = []
        for name, mod in found.items():
            tables = sorted(p.stem for p in Path(mod.DATA_DIR).glob("*.yaml"))
            items.append(
                {
                    "name": name,
                    "title": getattr(mod, "NAME", ""),
                    "tables": tables,
                    "rules": len(getattr(mod, "RULES", [])),
                }
            )
        return {
            "summary": "пакеты стандартов: " + (", ".join(i["name"] for i in items) or "не установлены"),
            "standards": items,
        }

    def context_tables(self, project: str) -> dict:
        ctx = self._ctx(project)
        names: list[str] = list(ctx.local_tables)
        for std in ctx.standards.values():
            names += [p.stem for p in Path(std.DATA_DIR).glob("*.yaml")]
        names = list(dict.fromkeys(names))
        tables = {}
        for n in names:
            t = ctx.table(n)
            keys = list(t) if isinstance(t, dict) else []
            tables[n] = {
                "keys": keys[:60],
                "count": len(keys),
                "fields": sorted({k for v in t.values() if isinstance(v, dict) for k in v})[:30]
                if isinstance(t, dict)
                else [],
            }
        return {"summary": "таблицы: " + ", ".join(f"{n} ({tables[n]['count']})" for n in names), "tables": tables}

    def context_lookup(self, project: str, table: str, key: str) -> dict:
        rec = self._ctx(project).lookup(table, key)
        return {"summary": f"{table}[{key}]", "record": rec}

    def context_search(self, project: str, query: str, table: str | None = None) -> dict:
        ctx = self._ctx(project)
        q = query.lower()
        names = (
            [table]
            if table
            else list(ctx.local_tables)
            + [p.stem for s in ctx.standards.values() for p in Path(s.DATA_DIR).glob("*.yaml")]
        )
        hits = []
        for n in dict.fromkeys(names):
            t = ctx.table(n)
            if not isinstance(t, dict):
                continue
            for k, v in t.items():
                blob = f"{k} {v}".lower()
                if q in blob:
                    hits.append({"table": n, "key": k, "record": v})
                if len(hits) >= 50:
                    break
        return {"summary": f"«{query}»: совпадений {len(hits)}", "hits": hits}

    # ---------------------------------------------------------------- граф связей (M2.2, D27)

    def _graph(self):
        g = self.srv.ensure_graph()
        if g is None:
            if self.srv.database_url:
                raise GraphOff("граф связей недоступен: база Postgres не отвечает, повторное подключение идёт в фоне")
            raise GraphOff("граф связей не настроен: задайте SKELCAD_DATABASE_URL (URL Postgres или embedded)")
        return g

    def links(
        self,
        project: str,
        ref: str,
        variant: str | None = None,
        hops: int = 1,
        kinds: list[str] | None = None,
        direction: str = "both",
    ) -> dict:
        self.ws.path(project)
        res = gq.links(self._graph(), project, ref, variant, hops, kinds, direction)
        return {"summary": gq.describe_links(res), **res}

    def where_used(self, ref: str, project: str | None = None) -> dict:
        if project:
            self.ws.path(project)
        res = gq.where_used(self._graph(), ref, project)
        lines = [
            f"{u['project']}{'/' + u['variant'] if u['variant'] else ''}: {u['src']}"
            + (f" «{u['name']}»" if u["name"] else "")
            + f" — {RELATIONS.get(u['kind'], u['kind'])}"
            for u in res["uses"]
        ]
        where = ", ".join(f"{k} ({v})" for k, v in res["by_project"].items())
        head = f"{ref}: использований {len(res['uses'])}" + (f" — {where}" if where else "")
        return {"summary": "\n".join([head, *lines[:60]]), **res}

    def search(self, query: str, project: str | None = None, kind: str | None = None, limit: int = 50) -> dict:
        if project:
            self.ws.path(project)
        res = gq.search(self._graph(), query, project, kind, limit)
        lines = [
            f"{h['project']}{'/' + h['variant'] if h['variant'] else ''}: {h['ref']}"
            + (f" «{h['name']}»" if h["name"] else "")
            + f" ({KINDS.get(h['kind'], h['kind'])})"
            for h in res["hits"]
        ]
        head = f"«{query}»: найдено {len(res['hits'])}" + (" (список обрезан)" if res["truncated"] else "")
        return {"summary": "\n".join([head, *lines[:60]]), **res}

    def graph_stats(self, project: str | None = None) -> dict:
        if project:
            self.ws.path(project)
        res = gq.stats(self._graph(), project)
        return {"summary": f"граф связей: сущностей {res['entities']}, связей {res['relations']}", **res}

    def reindex(self, project: str | None = None) -> dict:
        """Пересобрать индекс (проект или все): после смены словаря связей или если индекс разошёлся."""
        self._graph()
        if project:
            r = self.srv.indexer.index_project(project, force=True)
            vs = [self.srv.indexer.index_variant(project, v["id"], force=True) for v in self.ws.variants(project)]
            return {"summary": f"{project}: индекс пересобран (вариантов {len(vs)})", "project": r, "variants": vs}
        r = self.srv.indexer.index_all(force=True)
        return {"summary": f"индекс пересобран: проектов {r['projects']}", **r}

    # ---------------------------------------------------------------- сборка и проверки

    def _links(self, project: str, files: dict) -> dict:
        out = {}
        for k, v in (files or {}).items():
            if isinstance(v, dict):
                out[k] = {kk: self.srv.url(project, vv) for kk, vv in v.items()}
            elif isinstance(v, str):
                out[k] = self.srv.url(project, v)
        return out

    def _report_brief(self, project: str, r: dict, all_findings: bool = False) -> dict:
        s = r["summary"]
        fl = [f for f in r["findings"] if all_findings or f["level"] != "info"]
        k = f", K_min {s['K_min']:.2f} ({s['K_min_item']})" if s.get("K_min") is not None else ""
        line = (
            f"{r['variant']}: масса {s['mass_kg']} кг, габарит {'×'.join(map(str, s['envelope_mm']))} мм, "
            f"деталей {s['parts']}, швы {s['weld_length_mm']} мм{k}; замечания: {_lvl(s['findings'])}"
        )
        return {
            "variant": r["variant"],
            "title": r.get("title"),
            "line": line,
            "summary": s,
            "metrics": r.get("metrics", []),
            "calc": [
                {"id": c["id"], "title": c["title"], "K": c["K"], "K_req": c["K_req"], "ok": c["ok"]}
                for c in r.get("calc", [])
            ],
            "findings": [_finding_line(f) for f in fl],
            "files": self._links(project, r.get("files")),
        }

    def build(self, project: str, variant: str | None = None, export: bool = True) -> dict:
        reports = self.srv.runner.run(
            "build",
            {
                "project_dir": self._fresh(project),
                "variants": [variant] if variant else None,
                "out_dir": str(self.srv.out_dir(project)),
                "export": export,
            },
        )
        for r in reports:
            self.srv.index_variant(project, r["variant"])
        briefs = [self._report_brief(project, r) for r in reports]
        return {"summary": "\n".join(b["line"] for b in briefs), "variants": briefs}

    def check(self, project: str, variant: str | None = None, scope: str = "all", all: bool = False) -> dict:  # noqa: A002
        if scope not in ("all", "rules", "geometry", "calc"):
            raise ValueError("scope: all | rules | geometry | calc")
        res = self.srv.runner.run(
            "check",
            {"project_dir": self._fresh(project), "variants": [variant] if variant else None, "scope": scope},
        )
        out, lines = {}, []
        for v, d in res.items():
            fl = [f for f in d["findings"] if all or f["level"] != "info"]
            counts = {lvl: sum(1 for f in d["findings"] if f["level"] == lvl) for lvl in ("error", "warning", "info")}
            kmin = min(d["calc"], key=lambda c: c["K"]) if d["calc"] else None
            lines.append(
                f"{v}: {_lvl(counts)}"
                + (f"; K_min {kmin['K']:.2f} ({kmin['title']}, треб. {kmin['K_req']:g})" if kmin else "")
            )
            out[v] = {
                "counts": counts,
                "findings": [_finding_line(f) for f in fl],
                "calc": [
                    {
                        "id": c["id"],
                        "title": c["title"],
                        "K": c["K"],
                        "K_req": c["K_req"],
                        "ok": c["ok"],
                        "formula": c["formula"],
                    }
                    for c in d["calc"]
                ],
                "metrics": d.get("metrics", []),
            }
        return {"summary": "\n".join(lines), "variants": out}

    def compare(self, project: str, variants: list[str] | None = None, rebuild: bool = False) -> dict:
        from skelcad.compare import _rows

        res = self.srv.runner.run(
            "compare",
            {
                "project_dir": self._fresh(project),
                "variants": variants,
                "out_dir": str(self.srv.out_dir(project)),
                "rebuild": rebuild,
            },
        )
        reports = res["reports"]
        names = [r["variant"] for r in reports]
        for n in names:
            self.srv.index_variant(project, n)
        rows = []
        for row in _rows(reports):
            best = [names[i] for i in row.get("best") or []]
            rows.append({"metric": row["title"], "values": dict(zip(names, row["values"], strict=False)), "best": best})
        lines = [
            f"{r['metric']}: "
            + "; ".join(f"{n}={v}" for n, v in r["values"].items())
            + (f" (лучший: {', '.join(r['best'])})" if r.get("best") else "")
            for r in rows
        ]
        return {
            "summary": "\n".join(lines),
            "variants": names,
            "rows": rows,
            "page": self.srv.url(project, "compare.html"),
        }

    # ---------------------------------------------------------------- измерения и виды

    def measure(self, project: str, variant: str | None, op: str, args: dict | None = None) -> dict:
        res = self.srv.runner.run(
            "measure",
            {"project_dir": str(self.ws.path(project)), "variant": variant, "op_name": op, "op_args": args or {}},
        )
        parts = {k: v for k, v in res.items() if k not in ("model", "note")}
        return {"summary": f"{op} {args or ''}: {parts}"[:400], "result": res}

    def render(self, project: str, variant: str | None, view: str = "iso", highlight: str | None = None) -> dict:
        res = self.srv.runner.run(
            "render",
            {
                "project_dir": str(self.ws.path(project)),
                "variant": variant,
                "view": view,
                "highlight": highlight,
                "out_dir": str(self.srv.out_dir(project)),
            },
        )
        links = {k: self.srv.url(project, res[k]) for k in ("svg", "png") if res.get(k)}
        summary = f"{project}/{variant}: вид {view}" + (f", подсветка {highlight}" if highlight else "") + f" — {links}"
        if res.get("note"):
            summary += f" ({res['note']})"
        return {
            "summary": summary,
            "links": links,
            "png_base64": res.get("png_base64"),
            "svg_text": res.get("svg_text"),
        }

    def layout(self, project: str, variant: str | None = None, png: bool = True) -> dict:
        """Компоновочный эскиз (все виды) из кэша по коммиту HEAD или через воркер: out/<p>/_layout/<hash>[-<v>]/."""
        self._fresh(project)
        head = self.ws.rev(project, "HEAD")[:12]
        key = head + (f"-{variant}" if variant else "")
        d = self.srv.out_dir(project) / "_layout" / key
        jf = next(d.glob("*_layout.json"), None) if d.is_dir() else None
        res = None
        if jf is not None:
            try:
                res = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                res = None
        if res is None:
            d.mkdir(parents=True, exist_ok=True)  # воркер пишет только внутрь out_dir — родителей создаёт сервер
            res = self.srv.runner.run(
                "layout",
                {"project_dir": str(self.ws.path(project)), "variant": variant, "out_dir": str(d), "png": png},
            )
        rel = f"_layout/{key}/"
        for v in res["views"].values():
            v["svg_url"] = f"/out/{project}/{rel}{v['svg']}"
            v["png_url"] = f"/out/{project}/{rel}{v['png']}" if v.get("png") else None
        res["commit"] = head
        res["key"] = key
        return res

    def sketch(self, project: str, variant: str, png: bool = True) -> dict:
        """Эскиз варианта с размерами (все виды): кэш по коммиту HEAD или воркер; out/<p>/_sketch/<hash>-<v>/."""
        self._fresh(project)
        head = self.ws.rev(project, "HEAD")[:12]
        key = f"{head}-{variant}"
        d = self.srv.out_dir(project) / "_sketch" / key
        jf = next(d.glob("*_sketch.json"), None) if d.is_dir() else None
        res = None
        if jf is not None:
            try:
                res = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                res = None
        if res is None:
            d.mkdir(parents=True, exist_ok=True)
            res = self.srv.runner.run(
                "sketch",
                {"project_dir": str(self.ws.path(project)), "variant": variant, "out_dir": str(d), "png": png},
            )
        res["commit"] = head
        res["key"] = key
        return res

    def render_sketch(self, project: str, variant: str, view: str = "main") -> dict:
        """Для агента: PNG эскиза с размерами одного вида + размеры текстом."""
        res = self.sketch(project, variant)
        if view not in res["views"]:
            raise ValueError(f"вид «{view}»; у эскиза есть: {', '.join(res['views'])}")
        v = res["views"][view]
        d = self.srv.out_dir(project) / "_sketch" / res["key"]
        png_b64 = None
        if v.get("png") and (d / v["png"]).is_file():
            png_b64 = base64.b64encode((d / v["png"]).read_bytes()).decode()
        dims = []
        for x in res["dims"]:
            if x["view"] == view:
                dims.append(f"{x['id']} = {x['text']}" + (f" ({x['axis']})" if x.get("axis") else ""))
        lines = [
            f"{project}/{variant}: эскиз, {v['title']}",
            "размеры: " + ("; ".join(dims) or "нет"),
            *(f"примечание: {n}" for n in res.get("notes") or []),
        ]
        links = {k: self.srv.url(project, f"_sketch/{res['key']}/{v[k]}") for k in ("svg", "png") if v.get(k)}
        return {
            "summary": "\n".join(lines),
            "links": links,
            "png_base64": png_b64,
            "svg_text": None if png_b64 else (d / v["svg"]).read_text(encoding="utf-8"),
            "sketch": {k: res[k] for k in ("dims", "entities", "notes", "commit")},
        }

    def render_layout(self, project: str, variant: str | None, view: str = "main") -> dict:
        """Для агента: PNG компоновки одного вида + размеры и легенда текстом."""
        from skelcad.server import layout as L

        res = self.layout(project, variant)
        if view not in res["views"]:
            raise ValueError(f"вид «{view}»; у компоновки есть: {', '.join(res['views'])}")
        v = res["views"][view]
        d = self.srv.out_dir(project) / "_layout" / res["key"]
        png_b64 = None
        if v.get("png") and (d / v["png"]).is_file():
            png_b64 = base64.b64encode((d / v["png"]).read_bytes()).decode()
        dims = [f"{x['id']} = {x['text']} ({x['axis']})" for x in res["dims"] if x["view"] == view]
        state = L.describe(L.state(self.ws, project))
        lines = [
            f"{project}/{variant or 'база'}: компоновка, {v['title']}; {state}",
            "размеры: " + ("; ".join(dims) or "нет"),
            *res["legend"],
            *(f"примечание: {n}" for n in res.get("notes") or []),
        ]
        links = {k: self.srv.url(project, f"_layout/{res['key']}/{v[k]}") for k in ("svg", "png") if v.get(k)}
        return {
            "summary": "\n".join(lines),
            "links": links,
            "png_base64": png_b64,
            "svg_text": None if png_b64 else (d / v["svg"]).read_text(encoding="utf-8"),
            "layout": {k: res[k] for k in ("dims", "entities", "loads", "legend", "parts", "notes", "commit")},
        }

    def diff(self, project: str, variant: str | None, a: str = "HEAD~1", b: str = "HEAD") -> dict:
        da, db = self.ws.snapshot(project, a), self.ws.snapshot(project, b)
        res = self.srv.runner.run("diff", {"project_dir_a": str(da), "project_dir_b": str(db), "variant": variant})
        head = f"{project}/{variant or 'база'}: {self.ws.rev(project, a)[:7]} → {self.ws.rev(project, b)[:7]}"
        return {"summary": head + "\n" + res["text"], **{k: v for k, v in res.items() if k != "text"}}


def local_server(data: Path, database_url: str | None = None) -> Server:
    """Сервер для CLI и тестов: подпроцесс-воркер, данные в папке; database_url — граф связей (Postgres)."""
    return Server(workspace=Workspace(data), runner=SubprocessRunner(), database_url=database_url)
