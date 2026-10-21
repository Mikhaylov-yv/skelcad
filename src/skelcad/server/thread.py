"""Разговор по проекту (M2.5, D32): одна лента из задач конструктора агенту, ответов агента (отчёт, картинка,
на которую он смотрел) и служебных записей из коммитов конструктора и внешних агентов. Ничего нового не хранится:
лента выводится из очереди задач и истории git."""

from __future__ import annotations

import re
from datetime import datetime

from skelcad.server import api
from skelcad.server.tasks import TaskError, TaskStore
from skelcad.server.workspace import Workspace

WORKBENCH_AGENT = "SkelCAD agent (workbench-agent)"
AGENT_RE = re.compile(r"^SkelCAD agent \((.+)\)$")
CLIP = 600


def _first_para(text: str, limit: int = CLIP) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    return cut[: cut.rfind(" ")] + "…" if " " in cut else cut + "…"


def task_images(store: TaskStore, task_id: str, limit: int = 3) -> list[str]:
    """Последние картинки, которые агент получил от инструментов (tool_result.images) — ссылками."""
    try:
        ev = store.events(task_id, 0, 2000)["events"]
    except (TaskError, OSError):
        return []
    names: list[str] = []
    for e in ev:
        if e.get("type") == "tool_result" and isinstance(e.get("images"), list):
            names.extend(x for x in e["images"] if isinstance(x, str))
    return [f"/api/tasks/{task_id}/files/{n}" for n in names[-limit:]]


def task_messages(store: TaskStore, task: dict) -> list[dict]:
    out = [
        {
            "id": f"you:{task['id']}",
            "who": "you",
            "at": task.get("created"),
            "by": task.get("user"),
            "text": task.get("text") or "",
            "attachments": task.get("attachments") or [],
            "task": task["id"],
        }
    ]
    status = task.get("status")
    if status in ("done", "failed", "stopped", "limit"):
        res = task.get("result") or ""
        err = task.get("error")
        fallback = {"stopped": "Остановлено.", "limit": "Остановлено по лимиту шагов."}.get(status, "")
        text = res if status == "done" else (err or res or fallback)
        out.append(
            {
                "id": f"agent:{task['id']}",
                "who": "agent",
                "at": task.get("finished") or task.get("updated"),
                "status": status,
                "text": text,
                "brief": _first_para(text),
                "images": task_images(store, task["id"]),
                "steps": task.get("steps"),
                "model": task.get("model"),
                "usage": task.get("usage"),
                "task": task["id"],
            }
        )
    return out


def commit_messages(ws: Workspace, project: str, limit: int = 100) -> list[dict]:
    """Служебные записи: коммиты конструктора (согласование, выбор, правка компоновки, вложения) и агентов,
    работавших не через очередь рабочего места (Claude Code и др.). Коммиты встроенного агента — внутри его ответов."""
    out = []
    for c in api.commits(ws, project, limit=limit)["commits"]:
        if c["author"] == WORKBENCH_AGENT:
            continue
        m = AGENT_RE.match(c["author"])
        who = f"агент {m.group(1)}" if m else c["author"]
        out.append(
            {
                "id": f"commit:{c['hash']}",
                "who": "system",
                "at": c["date"],
                "by": who,
                "text": c["message"],
                "commit": c["commit"],
                "kind": c["kind"],
                "reviewed": c.get("reviewed"),
            }
        )
    return out


RANK = {"system": 0, "you": 1, "agent": 2}


def _key(m: dict) -> tuple[float, int]:
    """Порядок: по времени в UTC (у коммитов свой часовой пояс), при равной секунде — коммит, задача, ответ."""
    try:
        ts = datetime.fromisoformat(m.get("at") or "").timestamp()
    except ValueError:
        ts = 0.0
    return ts, RANK.get(m.get("who"), 3)


def thread(ws: Workspace, store: TaskStore, project: str, limit: int = 60) -> dict:
    msgs: list[dict] = []
    for t in store.list(project, limit=limit):
        msgs.extend(task_messages(store, t))
    msgs.extend(commit_messages(ws, project))
    msgs.sort(key=_key)
    return {"messages": msgs, "active": store.active(project)}
