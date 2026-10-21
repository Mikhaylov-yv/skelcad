"""Решения конструктора по проекту, которые агент не трогает: выбранный вариант (decisions.yaml в репозитории
проекта, коммит от имени конструктора). Как layout.yaml для согласования компоновки (D21), так и здесь — отдельный
файл, потому что агент переписывает project.yaml целиком."""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from skelcad.server.workspace import Actor, Workspace, WorkspaceError

FILE = "decisions.yaml"


def read(ws: Workspace, project: str) -> dict:
    try:
        data = yaml.safe_load(ws.read_file(project, FILE)) or {}
    except (WorkspaceError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def chosen_variant(ws: Workspace, project: str) -> str | None:
    rec = read(ws, project).get("variant")
    vid = rec.get("id") if isinstance(rec, dict) else rec
    if not vid:
        return None
    return vid if any(v["id"] == vid for v in ws.variants(project)) else None


def choose(ws: Workspace, project: str, variant: str, actor: Actor) -> dict:
    """Выбрать вариант для комплекта; пустой variant — снять выбор."""
    variants = [v["id"] for v in ws.variants(project)]
    if variant and variant not in variants:
        raise WorkspaceError(f"нет варианта «{variant}»; есть: {', '.join(variants) or 'ничего'}")
    data = read(ws, project)
    if variant:
        data["variant"] = {"id": variant, "by": actor.name, "at": datetime.now(tz=UTC).isoformat(timespec="seconds")}
        msg = f"Выбран вариант {variant} ({actor.name})"
    else:
        data.pop("variant", None)
        msg = f"Выбор варианта снят ({actor.name})"
    text = "# Решения конструктора (кнопки рабочего места); файл конструктора, агент его не меняет.\n" + yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False
    )
    res = ws.write_files(project, {FILE: text}, msg, actor)
    return {"variant": variant or None, "commit": res["commit"]}
