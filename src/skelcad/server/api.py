"""/api для workbench: обзор проектов с числами последней сборки каждого варианта."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from skelcad.server.auth import current_actor
from skelcad.server.workspace import Workspace


def variant_overview(out_dir: Path, project: str, variant: dict) -> dict:
    """Числа из out/<project>/<variant>/report.json последней сборки; built=False, если сборки не было."""
    item = {"id": variant["id"], "title": variant.get("title", ""), "built": False}
    rep = out_dir / project / variant["id"] / "report.json"
    if not rep.is_file():
        return item
    try:
        r = json.loads(rep.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return item
    s = r.get("summary") or {}
    f = s.get("findings") or {}
    item.update(
        built=True,
        built_at=datetime.fromtimestamp(rep.stat().st_mtime, tz=UTC).isoformat(timespec="seconds"),
        mass_kg=s.get("mass_kg"),
        k_min=s.get("K_min"),
        k_min_item=s.get("K_min_item"),
        errors=f.get("error", 0),
        warnings=f.get("warning", 0),
        info=f.get("info", 0),
    )
    return item


def project_overview(ws: Workspace, out_dir: Path, name: str, tasks=None) -> dict:
    from skelcad.server import layout

    info = ws.info(name)
    info["variants"] = [variant_overview(out_dir, name, v) for v in ws.variants(name)]
    info["layout"] = layout.brief(ws, name)
    active = tasks.active(name) if tasks is not None else None
    info["state"] = "agent" if active else "constructor"
    info["task"] = {"id": active["id"], "status": active["status"], "text": active["text"]} if active else None
    info["unreviewed"] = commits(ws, name, limit=200)["unreviewed"]
    return info


def projects_overview(ws: Workspace, out_dir: Path, tasks=None) -> dict:
    items = [project_overview(ws, out_dir, n, tasks) for n in ws.names()]
    return {
        "summary": f"проектов: {len(items)}" + (": " + ", ".join(i["name"] for i in items) if items else ""),
        "projects": items,
        "templates": ws.templates_list(),
    }


class NotBuilt(LookupError):
    """Вариант ещё не собран: нет out/<project>/<variant>/report.json."""


def variant_report(ws: Workspace, out_dir: Path, project: str, variant: str) -> dict:
    """Полный отчёт последней сборки варианта + ссылки на артефакты (относительно /out/<project>/)."""
    if project not in ws.names():
        raise LookupError(f"нет проекта «{project}»")
    ids = [v["id"] for v in ws.variants(project)]
    if variant not in ids:
        raise LookupError(f"нет варианта «{variant}» в проекте «{project}»; есть: {', '.join(ids) or 'нет'}")
    rep = out_dir / project / variant / "report.json"
    if not rep.is_file():
        raise NotBuilt(f"вариант «{variant}» ещё не собран")
    r = json.loads(rep.read_text(encoding="utf-8"))
    files = r.get("files") or {}
    base = f"/out/{project}/"
    r["urls"] = {
        "glb": base + files["gltf"] if files.get("gltf") else None,
        "step": base + files["assembly_step"] if files.get("assembly_step") else None,
        "svg": {k: base + v for k, v in (files.get("svg") or {}).items()},
        "sketch": {k: base + v for k, v in (files.get("sketch") or {}).items()},
    }
    r["sketch"] = None
    sj = out_dir / project / files["sketch_json"] if files.get("sketch_json") else None
    if sj and sj.is_file():
        try:
            r["sketch"] = json.loads(sj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            r["sketch"] = None
    r["built_at"] = datetime.fromtimestamp(rep.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
    # геометрия может быть старше отчёта: сборка без экспорта (build export=False) переносит ссылки прошлой сборки
    glb = out_dir / project / files["gltf"] if files.get("gltf") else None
    r["geometry_at"] = None
    if glb and glb.is_file():
        r["geometry_at"] = datetime.fromtimestamp(glb.stat().st_mtime, tz=UTC).isoformat(timespec="seconds")
    return r


# ---------------------------------------------------------------- компоновка


def layout_view(tools, project: str, variant: str | None) -> dict:
    """Компоновочный эскиз (кэш по коммиту) и состояние согласования."""
    from skelcad.server import layout

    res = tools.layout(project, variant or None)
    res["approval"] = layout.state(tools.ws, project)
    return res


def layout_approve(ws: Workspace, project: str) -> dict:
    """«Компоновка согласована» — коммит от имени пользователя рабочего места."""
    from skelcad.server import layout

    return layout.approve(ws, project, current_actor("workbench"))


# ---------------------------------------------------------------- лента коммитов

AGENT_RE = re.compile(r"^SkelCAD agent \((.+)\)$")


def commit_kind(c: dict) -> str:
    if c["message"].startswith('Revert "') or c["message"].startswith("Откат "):
        return "revert"
    if AGENT_RE.match(c["author"]):
        return "agent"
    if c["author"] == "SkelCAD":
        return "system"
    return "user"


def commits(ws: Workspace, project: str, limit: int = 50) -> dict:
    """История с отметками «просмотрено» (заметки git) и счётчиком непросмотренных коммитов агента."""
    items = ws.history(project, limit=limit)
    notes = ws.notes(project)
    head = ws.rev(project, "HEAD") if items else None
    unreviewed = 0
    for c in items:
        c["kind"] = commit_kind(c)
        c["is_head"] = c["hash"] == head
        note = notes.get(c["hash"])
        c["reviewed"] = None
        if note:
            try:
                c["reviewed"] = json.loads(note)
            except ValueError:
                c["reviewed"] = {"by": "?", "at": None, "raw": note}
        if c["kind"] == "agent" and not c["reviewed"]:
            unreviewed += 1
    return {"commits": items, "unreviewed": unreviewed, "head": head}


def set_reviewed(ws: Workspace, project: str, commit: str, reviewed: bool, who: str) -> dict:
    actor = current_actor("workbench")
    if reviewed:
        note = json.dumps({"by": who, "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}, ensure_ascii=False)
        ws.note_set(project, commit, note, actor)
        return {"reviewed": json.loads(note)}
    ws.note_set(project, commit, None, actor)
    return {"reviewed": None}


def _commit_dir(out_dir: Path, project: str, full: str) -> Path:
    d = out_dir / project / "_commits" / full[:12]
    d.mkdir(parents=True, exist_ok=True)
    return d


def commit_diff(tools, out_dir: Path, project: str, commit: str, variant: str | None) -> dict:
    """Разница parent → commit по варианту; результат кэшируется в out/<p>/_commits/<hash>/<v>.diff.json."""
    ws = tools.ws
    full = ws.rev(project, commit)
    variant = variant or (ws.variants(project) or [{"id": None}])[0]["id"]
    if not variant:
        raise LookupError("в проекте нет вариантов")
    cache = _commit_dir(out_dir, project, full) / f"{variant}.diff.json"
    if cache.is_file():
        d = json.loads(cache.read_text(encoding="utf-8"))
        d["cached"] = True
        return d
    parent = ws.rev(project, full + "~1") if _has_parent(ws, project, full) else None
    if parent is None:
        d = {
            "variant": variant,
            "a": None,
            "b": full,
            "summary": "первый коммит проекта: сравнивать не с чем",
            "entities": {},
            "geometry": {},
            "deltas": {},
            "findings": {"added": [], "removed": []},
        }
    else:
        res = tools.diff(project, variant, parent, full)
        d = {"variant": variant, "a": parent, "b": full, **res}
    cache.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    d["cached"] = False
    return d


def _has_parent(ws: Workspace, project: str, full: str) -> bool:
    from skelcad.server.workspace import git

    return git(ws.path(project), "rev-parse", "--verify", "-q", full + "~1", check=False).returncode == 0


def commit_model(srv, project: str, commit: str, variant: str) -> dict:
    """GLB состояния варианта на коммите: HEAD — из текущей сборки, иначе сборка снимка в out/<p>/_commits/<hash>/."""
    ws = srv.workspace
    full = ws.rev(project, commit)
    if full == ws.rev(project, "HEAD"):
        rep = ws.out_dir / project / variant / "report.json"
        if rep.is_file():
            files = json.loads(rep.read_text(encoding="utf-8")).get("files") or {}
            if files.get("gltf"):
                return {"url": f"/out/{project}/{files['gltf']}", "commit": full, "built": False}
    d = _commit_dir(ws.out_dir, project, full)
    rep = d / variant / "report.json"
    built = False
    if not rep.is_file():
        snap = ws.snapshot(project, full)
        srv.runner.run("build", {"project_dir": str(snap), "variants": [variant], "out_dir": str(d), "export": True})
        built = True
    files = json.loads(rep.read_text(encoding="utf-8")).get("files") or {}
    if not files.get("gltf"):
        raise LookupError("сборка не дала glTF")
    return {"url": f"/out/{project}/_commits/{full[:12]}/{files['gltf']}", "commit": full, "built": built}


# ---------------------------------------------------------------- сравнение вариантов


def compare(tools, out_dir: Path, project: str, variants: list[str] | None = None) -> dict:
    """Таблица метрик по вариантам (как инструмент compare) + числа, ссылки на GLB и эскизы каждого варианта,
    строки различающихся размеров (из <v>_sketch.json) и параметров вариантов."""
    from skelcad.server import params as P

    res = tools.compare(project, variants)
    ws = tools.ws
    spec = ws.spec(project)
    cols = []
    dims_by: dict[str, dict[str, dict]] = {}
    params_by: dict[str, dict[str, object]] = {}
    for v in res["variants"]:
        item = variant_overview(out_dir, project, {"id": v, "title": ""})
        rep = out_dir / project / v / "report.json"
        glb = None
        sketch_urls: dict[str, str] = {}
        sketch_views: dict = {}
        if rep.is_file():
            r = json.loads(rep.read_text(encoding="utf-8"))
            item["title"] = r.get("title", "")
            files = r.get("files") or {}
            glb = f"/out/{project}/{files['gltf']}" if files.get("gltf") else None
            sketch_urls = {k: f"/out/{project}/{p}" for k, p in (files.get("sketch") or {}).items()}
            sj = out_dir / project / files["sketch_json"] if files.get("sketch_json") else None
            if sj and sj.is_file():
                try:
                    sk = json.loads(sj.read_text(encoding="utf-8"))
                    sketch_views = sk.get("views") or {}
                    dims_by[v] = {d["id"]: d for d in sk.get("dims") or [] if d.get("value") is not None}
                except (OSError, ValueError):
                    pass
        item["glb"] = glb
        item["sketch"] = sketch_urls
        item["sketch_views"] = sketch_views
        try:
            vspec = next((x for x in ws.variants(project) if x["id"] == v), None)
            vparams = yaml.safe_load((ws.path(project) / vspec["file"]).read_text(encoding="utf-8")) if vspec else {}
            params_by[v] = {
                f["path"]: f["value"] for f in P.fields(spec.get("params") or {}, (vparams or {}).get("params") or {})
            }
        except (OSError, ValueError, TypeError):
            params_by[v] = {}
        cols.append(item)
    titles = {v["id"]: v.get("title", "") for v in ws.variants(project)}
    for c in cols:
        c["title"] = c["title"] or titles.get(c["id"], "")
    names = [c["id"] for c in cols]
    # размеры: один id в двух и более вариантах с разными значениями
    dim_rows = []
    ids = list(dict.fromkeys(i for d in dims_by.values() for i in d))
    for did in ids:
        vals = {v: dims_by[v][did] for v in names if v in dims_by and did in dims_by[v]}
        if len(vals) < 2 or len({round(float(x["value"]), 2) for x in vals.values()}) < 2:
            continue
        first = next(iter(vals.values()))
        dim_rows.append(
            {
                "id": did,
                "axis": first.get("axis", ""),
                "views": sorted({x["view"] for x in vals.values()}),
                "values": {v: (vals[v]["text"] if v in vals else None) for v in names},
            }
        )
    param_rows = []
    for path in dict.fromkeys(k for d in params_by.values() for k in d):
        vals = {v: params_by.get(v, {}).get(path) for v in names}
        if len({json.dumps(x, sort_keys=True, ensure_ascii=False) for x in vals.values()}) > 1:
            param_rows.append({"path": path, "values": vals})
    return {
        "summary": res["summary"],
        "variants": cols,
        "rows": res["rows"],
        "dim_rows": dim_rows,
        "param_rows": param_rows,
    }


# ---------------------------------------------------------------- параметры варианта (форма, черновик, сохранение)


def variant_params(ws: Workspace, project: str, variant: str) -> dict:
    from skelcad.server import params as P

    spec = ws.spec(project)
    v = next((x for x in ws.variants(project) if x["id"] == variant), None)
    if not v:
        raise LookupError(f"нет варианта «{variant}»")
    vdata = yaml.safe_load(ws.read_file(project, v["file"])) or {}
    return {
        "variant": variant,
        "file": v["file"],
        "fields": P.fields(spec.get("params") or {}, vdata.get("params") or {}),
    }


def variant_draft(srv, project: str, variant: str, raw: dict) -> dict:
    from skelcad.server import params as P

    cur = variant_params(srv.workspace, project, variant)["fields"]
    changes = P.coerce(cur, raw)
    if not changes:
        raise ValueError("нет изменённых параметров")
    out = P.build_draft(srv, project, variant, changes)
    out.pop("_tools", None)
    return out


def variant_save(srv, project: str, variant: str, raw: dict, message: str, draft: str | None) -> dict:
    from skelcad.server import params as P

    cur = variant_params(srv.workspace, project, variant)["fields"]
    changes = P.coerce(cur, raw)
    if not changes:
        raise ValueError("нет изменённых параметров")
    if not message.strip():
        raise ValueError("нужно сообщение: что и зачем изменено")
    return P.save_params(srv, project, variant, changes, message.strip(), current_actor("workbench"), draft)
