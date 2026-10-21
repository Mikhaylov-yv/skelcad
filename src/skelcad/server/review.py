"""Замечания конструктора агенту — `review.yaml` в корне проекта (коммитится, как всё остальное).

Запись: {id: R1, text, variant?, part?, point? [x, y, z] мм, stroke? {view, points: [[x, y, z], …]}, author,
created, status: open | resolved, answer?, resolved_by?, resolved_at?}. Конструктор ставит пометку в workbench
(деталь + точка + текст) или обводит место на компоновочном эскизе росчерком (M2.3: точки в координатах модели
и вид), агент читает `review_list` и закрывает `review_resolve` с ответом; конструктор может закрыть сам.
"""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from skelcad.server.workspace import Actor, Workspace, WorkspaceError

FILE = "review.yaml"
VIEWS = ("main", "left", "top")
MAX_STROKE_POINTS = 400


def clean_stroke(stroke: dict | None) -> dict | None:
    """Росчерк из рабочего места: вид и точки модели (мм, до 0,5); None — росчерка нет."""
    if not stroke:
        return None
    if not isinstance(stroke, dict):
        raise ValueError("stroke: ожидался объект {view, points}")
    view = str(stroke.get("view") or "")
    if view not in VIEWS:
        raise ValueError(f"stroke.view: ожидалось {' | '.join(VIEWS)}, получено «{view}»")
    pts = stroke.get("points")
    if not isinstance(pts, list) or len(pts) < 2:
        raise ValueError("stroke.points: нужны хотя бы две точки [x, y, z]")
    out = []
    for p in pts[:MAX_STROKE_POINTS]:
        if not isinstance(p, list | tuple) or len(p) != 3:
            raise ValueError("stroke.points: каждая точка — три числа [x, y, z]")
        q = [round(float(c) * 2) / 2 for c in p]
        if not out or q != out[-1]:
            out.append(q)
    if len(out) < 2:
        raise ValueError("stroke.points: все точки совпадают")
    return {"view": view, "points": out}


def describe_stroke(stroke: dict) -> str:
    """Росчерк словами для агента: вид, число точек, габарит в мм."""
    pts = stroke.get("points") or []
    if not pts:
        return "росчерк без точек"
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    box = "; ".join(f"{a}={lo[i]:g}…{hi[i]:g}" for i, a in enumerate("XYZ") if hi[i] - lo[i] > 0.5)
    return f"росчерк на виде {stroke.get('view')}: точек {len(pts)}, габарит {box or 'точка'} мм"


def _load(ws: Workspace, project: str) -> list[dict]:
    try:
        data = yaml.safe_load(ws.read_file(project, FILE)) or {}
    except WorkspaceError:
        return []
    items = data.get("items") if isinstance(data, dict) else data
    return [i for i in (items or []) if isinstance(i, dict) and i.get("id")]


def _dump(items: list[dict]) -> str:
    head = "# Замечания конструктора агенту. Открытые — status: open; агент отвечает review_resolve.\n"
    return head + yaml.safe_dump({"items": items}, allow_unicode=True, sort_keys=False, width=100)


def list_items(ws: Workspace, project: str, status: str | None = None) -> list[dict]:
    items = _load(ws, project)
    return [i for i in items if not status or i.get("status", "open") == status]


def add(
    ws: Workspace,
    project: str,
    text: str,
    actor: Actor,
    variant: str | None = None,
    part: str | None = None,
    point: list[float] | None = None,
    stroke: dict | None = None,
) -> dict:
    if not (text or "").strip():
        raise ValueError("нужен текст замечания")
    stroke = clean_stroke(stroke)
    if stroke and not point:
        point = stroke["points"][0]
    items = _load(ws, project)
    n = 1 + max((int(i["id"][1:]) for i in items if str(i["id"]).startswith("R") and i["id"][1:].isdigit()), default=0)
    item = {
        "id": f"R{n}",
        "text": text.strip(),
        "status": "open",
        "author": actor.name,
        "created": datetime.now(tz=UTC).isoformat(timespec="seconds"),
    }
    if variant:
        item["variant"] = variant
    if part:
        item["part"] = part
    if point:
        item["point"] = [round(float(x), 1) for x in point[:3]]
    if stroke:
        item["stroke"] = stroke
    items.append(item)
    where = f" ({part})" if part else (" (росчерк)" if stroke else "")
    res = ws.write_files(project, {FILE: _dump(items)}, f"замечание {item['id']}{where}: {item['text'][:60]}", actor)
    return {"item": item, "commit": res["commit"]}


def resolve(ws: Workspace, project: str, item_id: str, answer: str, actor: Actor) -> dict:
    items = _load(ws, project)
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        raise LookupError(f"нет замечания «{item_id}»; есть: {', '.join(i['id'] for i in items) or 'нет'}")
    if item.get("status") == "resolved":
        raise ValueError(f"замечание {item_id} уже закрыто")
    item["status"] = "resolved"
    item["answer"] = (answer or "").strip()
    item["resolved_by"] = actor.name
    item["resolved_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    res = ws.write_files(project, {FILE: _dump(items)}, f"ответ на {item_id}: {item['answer'][:60]}", actor)
    return {"item": item, "commit": res["commit"]}
