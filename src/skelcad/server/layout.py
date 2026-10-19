"""Компоновка на сервере: состояние согласования (layout.yaml → `approved`), сравнение со согласованным
состоянием, отметка «Компоновка согласована» коммитом конструктора. Сам эскиз строит воркер (op layout),
кэш по коммиту — в Tools.layout. Отметка живёт в отдельном файле: агент переписывает project.yaml целиком
и не должен её терять."""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from skelcad.core.model import Requirements, Skeleton, layout_hash
from skelcad.core.project import LAYOUT_FILE
from skelcad.server.workspace import Actor, Workspace, WorkspaceError, git

GROUPS = ("datums", "interfaces", "envelopes", "surroundings")


def spec_hash(spec: dict) -> str:
    sk = Skeleton.model_validate(spec.get("skeleton") or {})
    rq = Requirements.model_validate(spec.get("requirements") or {})
    return layout_hash(sk, rq)


def _entities(spec: dict) -> dict[str, dict]:
    sk = spec.get("skeleton") or {}
    out = {}
    for group in GROUPS:
        for e in sk.get(group) or []:
            if isinstance(e, dict) and e.get("id"):
                out[f"{group[:-1]}:{e['id']}"] = e
    return out


def diff_since(ws: Workspace, project: str, commit: str, spec_now: dict) -> dict | None:
    """Что изменилось в скелете и требованиях с согласованного коммита: добавлено / удалено / изменено по id."""
    p = git(ws.path(project), "show", f"{commit}:project.yaml", check=False)
    if p.returncode != 0:
        return None
    try:
        then = yaml.safe_load(p.stdout) or {}
    except yaml.YAMLError:
        return None
    a, b = _entities(then), _entities(spec_now)
    return {
        "added": sorted(set(b) - set(a)),
        "removed": sorted(set(a) - set(b)),
        "changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
        "requirements": (then.get("requirements") or {}) != (spec_now.get("requirements") or {}),
    }


def state(ws: Workspace, project: str) -> dict:
    """none — не согласована; approved — согласована и не менялась; changed — менялась после согласования;
    invalid — скелет или требования не читаются (ошибка в тексте)."""
    spec = ws.spec(project)
    try:
        h = spec_hash(spec)
    except Exception as e:  # noqa: BLE001 — ошибка валидации показывается конструктору текстом
        return {"state": "invalid", "error": str(e)[:500], "hash": None, "approved": None, "diff": None}
    approved = read_approval(ws, project)
    if approved is None:
        ap = spec.get("layout")  # старый способ: раздел в project.yaml
        if isinstance(ap, dict) and ap.get("hash"):
            approved = {k: ap.get(k) for k in ("by", "at", "commit", "hash")}
    st = "none" if approved is None else "approved" if approved["hash"] == h else "changed"
    out = {"state": st, "hash": h, "approved": approved, "diff": None}
    if st == "changed" and approved and approved.get("commit"):
        out["diff"] = diff_since(ws, project, approved["commit"], spec)
    return out


def brief(ws: Workspace, project: str) -> dict:
    st = state(ws, project)
    ap = st.get("approved") or {}
    return {"state": st["state"], "by": ap.get("by"), "at": ap.get("at")}


def describe(st: dict) -> str:
    ap = st.get("approved") or {}
    who = f"{ap.get('by')}, {str(ap.get('at') or '')[:10]}"
    return {
        "none": "компоновка не согласована конструктором",
        "approved": f"компоновка согласована ({who})",
        "changed": f"компоновка изменена после согласования ({who}) — нужно согласовать заново",
        "invalid": f"скелет или требования не читаются: {st.get('error')}",
    }[st["state"]]


def read_approval(ws: Workspace, project: str) -> dict | None:
    try:
        data = yaml.safe_load(ws.read_file(project, LAYOUT_FILE)) or {}
    except (WorkspaceError, yaml.YAMLError):
        return None
    rec = data.get("approved") if isinstance(data, dict) else None
    if isinstance(rec, dict) and rec.get("hash"):
        return {k: rec.get(k) for k in ("by", "at", "commit", "hash")}
    return None


def approve(ws: Workspace, project: str, actor: Actor) -> dict:
    """Записать отметку согласования в layout.yaml и закоммитить от имени конструктора."""
    spec = ws.spec(project)
    h = spec_hash(spec)
    head = ws.rev(project, "HEAD")[:12]
    rec = {"by": actor.name, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "commit": head, "hash": h}
    text = (
        "# Согласование компоновки конструктором (кнопка «Компоновка согласована» в рабочем месте).\n"
        "# hash — скелет, обстановка и требования на момент согласования; файл конструктора, агент его не меняет.\n"
        + yaml.safe_dump({"approved": rec}, allow_unicode=True, sort_keys=False)
    )
    res = ws.write_files(project, {LAYOUT_FILE: text}, f"Компоновка согласована ({actor.name})", actor)
    return {"approval": rec, "commit": res["commit"], **state(ws, project)}
