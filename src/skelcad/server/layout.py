"""Компоновка на сервере: состояние согласования (project.yaml → `layout`), сравнение со согласованным
состоянием, отметка «Компоновка согласована» коммитом конструктора. Сам эскиз строит воркер (op layout),
кэш по коммиту — в Tools.layout."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import yaml

from skelcad.core.model import Requirements, Skeleton, layout_hash
from skelcad.server.workspace import Actor, Workspace, git

GROUPS = ("datums", "interfaces", "envelopes", "surroundings")
BLOCK_RE = re.compile(r"(?m)^(#[^\n]*согласовани[^\n]*\n)?layout:[^\n]*\n(?:[ \t]+[^\n]*\n)*")
COMMENT = (
    "# согласование компоновки (кнопка «Компоновка согласована» в рабочем месте); hash — скелет, обстановка, требования"
)


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
    ap = spec.get("layout")
    approved = None
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


def approve(ws: Workspace, project: str, actor: Actor) -> dict:
    """Записать отметку согласования в project.yaml (блок `layout`) и закоммитить от имени конструктора."""
    spec = ws.spec(project)
    h = spec_hash(spec)
    head = ws.rev(project, "HEAD")[:12]
    rec = {"by": actor.name, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "commit": head, "hash": h}
    text = ws.read_file(project, "project.yaml")
    text = BLOCK_RE.sub("", text).rstrip("\n") + f"\n\n{COMMENT}\nlayout: {json.dumps(rec, ensure_ascii=False)}\n"
    parsed = yaml.safe_load(text) or {}
    if (parsed.get("layout") or {}).get("hash") != h:
        raise ValueError("не удалось записать отметку согласования в project.yaml")
    res = ws.write_files(project, {"project.yaml": text}, f"Компоновка согласована ({actor.name})", actor)
    return {"approval": rec, "commit": res["commit"], **state(ws, project)}
