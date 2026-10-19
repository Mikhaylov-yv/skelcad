"""Инструменты агента — реализации поверх ядра, без привязки к MCP SDK.

Каждый инструмент возвращает словарь; поле `summary` — одна строка для человека и агента,
остальное — данные. Тяжёлое (код проекта, OCCT) исполняется через Runner в воркере.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skelcad.context import Context, discover_standards
from skelcad.core.findings import LEVEL_RU
from skelcad.server.jobs import JobError, SubprocessRunner, make_runner
from skelcad.server.workspace import Actor, Workspace, WorkspaceError

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

    def project_create(self, name: str, template: str | None = None, client: str = "agent") -> dict:
        info = self.ws.create(name, template=template, actor=Actor.agent(client))
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
        return {
            "summary": f"{project}: «{spec.get('title', '')}», варианты: {vnames}",
            "spec": spec,
            "variants": variants,
            "files": files,
        }

    def model_query(self, project: str, variant: str | None = None, path: str | None = None) -> dict:
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
        res = self.ws.write_files(project, files, message, Actor.agent(client))
        c = res["commit"]
        return {"summary": f"коммит {c['commit']} «{c['message']}»: {', '.join(res['files'])}", **res}

    def history(self, project: str, limit: int = 20, path: str | None = None) -> dict:
        items = self.ws.history(project, limit=limit, path=path)
        lines = [f"{i['commit']} {i['date'][:16]} {i['author']}: {i['message']}" for i in items]
        return {"summary": "\n".join(lines) or "история пуста", "commits": items}

    def revert(self, project: str, commit: str, message: str | None = None, client: str = "agent") -> dict:
        res = self.ws.revert(project, commit, Actor.agent(client), message=message)
        return {"summary": f"откат {commit} → коммит {res['commit']['commit']}", **res}

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
                "project_dir": str(self.ws.path(project)),
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
            {"project_dir": str(self.ws.path(project)), "variants": [variant] if variant else None, "scope": scope},
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
                "project_dir": str(self.ws.path(project)),
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


def local_server(data: Path) -> Server:
    """Сервер для CLI и тестов: подпроцесс-воркер, данные в папке."""
    return Server(workspace=Workspace(data), runner=SubprocessRunner())
