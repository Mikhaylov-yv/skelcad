"""Инструменты агента — реализации поверх ядра, без привязки к MCP SDK.

Каждый инструмент возвращает словарь; поле `summary` — одна строка для человека и агента,
остальное — данные. Тяжёлое (код проекта, OCCT) исполняется через Runner в воркере.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skelcad.context import Context, discover_standards
from skelcad.core.findings import LEVEL_RU
from skelcad.server.auth import current_actor
from skelcad.server.jobs import JobError, SubprocessRunner, make_runner
from skelcad.server.workspace import Workspace, WorkspaceError

ToolError = (WorkspaceError, JobError, ValueError, KeyError, LookupError)


@dataclass
class Server:
    workspace: Workspace
    runner: Any = field(default_factory=make_runner)
    public_url: str = os.environ.get("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")

    @classmethod
    def from_env(cls) -> Server:
        data = Path(os.environ.get("SKELCAD_DATA", ".tmp/data"))
        return cls(workspace=Workspace(data))

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
        return {
            "summary": f"{project}: «{spec.get('title', '')}», варианты: {vnames}{note}; {layout.describe(lay)}",
            "spec": spec,
            "variants": variants,
            "files": files,
            "review_open": len(open_items),
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


def local_server(data: Path) -> Server:
    """Сервер для CLI и тестов: подпроцесс-воркер, данные в папке."""
    return Server(workspace=Workspace(data), runner=SubprocessRunner())
