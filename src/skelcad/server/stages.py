"""Этапы изделия и единственный следующий шаг (M2.5, D32): задание → компоновка → конструкция → комплект.
Состояние этапа выводится из проекта (спецификация, согласование, сборки, выбор варианта, экспорт), а не хранится.
Те же правила, что в макете docs/ui/prototypes/core.js (nextOf, stageState); у сводного узла — из дочерних."""

from __future__ import annotations

from pathlib import Path

STAGES = ("brief", "layout", "design", "kit")
STAGE_NAMES = {"brief": "Задание", "layout": "Компоновка", "design": "Конструкция", "kit": "Комплект"}
AGG_NAMES = {"brief": "Задание", "layout": "Общая компоновка", "design": "Узлы", "kit": "Сводный комплект"}
TASK_TEXT = {
    "layout": "Сделай компоновку по заданию: требования, скелет и обстановка; "
    "покажи компоновочный эскиз на согласование.",
    "design": "Сделай детали по согласованной компоновке: генератор, варианты, проверки; собери с экспортом.",
    "kit": "Собери комплект по выбранному варианту: сборка с экспортом, эскизы с размерами, отчёт.",
    "fix": "Устрани ошибки в замечаниях и подними запасы до требуемых; собери заново.",
}
JOB_TITLE = {
    "layout": "Агент строит компоновку",
    "design": "Агент делает детали",
    "kit": "Агент собирает комплект",
    "fix": "Агент устраняет ошибки",
}
K_REQ = 1.5


def _next(stage: str, kind: str, title: str, hint: str, label: str, act: str, short: str) -> dict:
    return {"stage": stage, "kind": kind, "title": title, "hint": hint, "label": label, "act": act, "short": short}


def skeleton_nonempty(spec: dict) -> bool:
    sk = spec.get("skeleton") or {}
    if not isinstance(sk, dict):
        return False
    return any(sk.get(k) for k in ("datums", "interfaces", "envelopes", "surroundings"))


def brief_done(spec: dict, has_tasks: bool) -> bool:
    req = spec.get("requirements") or {}
    return bool(spec.get("description") or (isinstance(req, dict) and req.get("purpose")) or has_tasks)


def kit_files(out_dir: Path, project: str, variant: str) -> list[dict]:
    """Файлы комплекта по варианту из последней сборки с экспортом: STEP, эскизы с размерами, виды, отчёт, модель."""
    d = out_dir / project / variant
    if not d.is_dir():
        return []
    out = []

    def add(path: Path, kind: str, title: str) -> None:
        if path.is_file():
            rel = path.relative_to(d).as_posix()
            url = f"/out/{project}/{variant}/{rel}"
            out.append({"name": path.name, "kind": kind, "title": title, "size": path.stat().st_size, "url": url})

    add(d / f"{variant}_assembly.step", "step", "сборка STEP AP242")
    views = (("main", "главный"), ("left", "слева"), ("top", "сверху"))
    for view, label in views:
        add(d / f"{variant}_sketch_{view}.png", "sketch", f"эскиз с размерами, {label}")
        add(d / f"{variant}_sketch_{view}.svg", "sketch-svg", f"эскиз с размерами, {label} (SVG)")
    for view, label in views:
        add(d / f"{variant}_{view}.svg", "view", f"вид {label}")
    add(d / "report.json", "report", "отчёт: сводка, запасы, замечания, допущения")
    add(d / "model.yaml", "model", "разрешённая модель варианта")
    add(d / f"{variant}.glb", "glb", "3D для просмотра")
    return out


def thumb_url(out_dir: Path, project: str, head: str | None, variants: list[dict], chosen: str | None) -> str | None:
    """Картинка проекта для дерева и галереи: эскиз выбранного (или первого собранного) варианта, иначе компоновка."""
    order = ([chosen] if chosen else []) + [v["id"] for v in variants if v.get("built")]
    for vid in order:
        for name in (f"{vid}_sketch_main.png", f"{vid}_main.png"):
            if (out_dir / project / vid / name).is_file():
                return f"/out/{project}/{vid}/{name}"
    if head:
        png = out_dir / project / "_layout" / head[:12] / f"{project}_layout_main.png"
        if png.is_file():
            return f"/out/{project}/_layout/{head[:12]}/{png.name}"
    return None


def running_job(info: dict, layout_state: str) -> str | None:
    """Чем занят агент, если занят: по тексту задачи, иначе по этапу проекта."""
    task = info.get("task")
    if not task:
        return None
    text = (task.get("text") or "").lower()
    for job, t in TASK_TEXT.items():
        if text.startswith(t[:30].lower()):
            return job
    if "комплект" in text:
        return "kit"
    if "ошиб" in text or "запас" in text:
        return "fix"
    return "layout" if layout_state != "approved" else "design"


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def leaf(info: dict, spec: dict, has_tasks: bool, chosen: str | None, kit: list[dict]) -> dict:
    """Состояния этапов и следующий шаг листового проекта (без узлов). info — обзор проекта (варианты с числами,
    layout.state, task)."""
    L = (info.get("layout") or {}).get("state") or "none"
    if L == "none" and skeleton_nonempty(spec):
        L = "waiting"
    variants = info.get("variants") or []
    built = [v for v in variants if v.get("built")]
    errors = sum(int(v.get("errors") or 0) for v in built)
    bdone = brief_done(spec, has_tasks)
    job = running_job(info, L)
    kit_ready = bool(kit) and any(f["kind"] == "step" for f in kit)
    # состояния этапов
    st = {
        "brief": "done" if bdone else "next",
        "layout": (
            "done"
            if L == "approved"
            else "wait"
            if L in ("waiting", "changed", "invalid")
            else "next"
            if bdone
            else "todo"
        ),
        "design": (
            "wait"
            if built and (errors or (len(built) > 1 and not chosen))
            else "done"
            if built
            else "next"
            if L == "approved"
            else "todo"
        ),
        "kit": "done" if kit_ready else ("next" if built and not errors and (chosen or len(built) == 1) else "todo"),
    }
    if job:
        st[{"fix": "design"}.get(job, job)] = "agent"
    # следующий шаг
    if job:
        stage = {"fix": "design"}.get(job, job)
        hint = info["task"].get("text") or ""
        nxt = _next(stage, "running", JOB_TITLE[job], hint, JOB_TITLE[job] + "…", "stop", "у агента")
    elif not bdone:
        nxt = _next(
            "brief",
            "agent",
            "Опишите, что нужно",
            "Назначение, нагрузки, к чему крепится; приложите набросок. Первое сообщение агенту — и есть задание: "
            "он опишет скелет и покажет компоновку.",
            "Написать агенту",
            "say",
            "задание",
        )
    elif L == "invalid":
        err = (info.get("layout") or {}).get("error") or "Ошибка в project.yaml — поручите агенту исправить."
        title = "Скелет или требования не читаются"
        nxt = _next("layout", "you", title, err, "Написать агенту", "say", "ошибка в модели")
    elif L == "none":
        nxt = _next(
            "layout",
            "agent",
            "Задание принято",
            "Агент опишет скелет и обстановку и покажет компоновку на согласование.",
            "Поручить агенту компоновку",
            "run:layout",
            "дальше: компоновка",
        )
    elif L in ("waiting", "changed"):
        nxt = _next(
            "layout",
            "you",
            "Компоновка изменена после согласования" if L == "changed" else "Компоновка ждёт вашего согласования",
            "Посмотрите эскиз и допущения. Согласуйте или поправьте прямо на эскизе. "
            "После согласования агент сразу возьмётся за детали.",
            "Согласовать компоновку",
            "approve",
            "ждёт согласования",
        )
    elif not built:
        nxt = _next(
            "design",
            "agent",
            "Компоновка согласована",
            "Агент сделает детали и варианты, проверит запасы и массу.",
            "Поручить агенту детали",
            "run:design",
            "дальше: детали",
        )
    elif errors:
        nxt = _next(
            "design",
            "you",
            f"Ошибки: {errors}",
            "Ошибки блокируют комплект. Поручите агенту устранить или поправьте параметры сами.",
            "Поручить агенту устранить",
            "run:fix",
            "ошибки",
        )
    elif len(built) > 1 and not chosen:
        n = len(built)
        nxt = _next(
            "design",
            "you",
            f"{n} {_plural(n, 'вариант готов', 'варианта готовы', 'вариантов готовы')} — выберите",
            "Сравните массу и запасы, выберите вариант для комплекта.",
            "Сравнить и выбрать",
            "choose",
            "выбрать вариант",
        )
    elif not kit_ready:
        v = chosen or built[0]["id"]
        nxt = _next(
            "kit",
            "agent",
            f"Вариант выбран: {v}",
            "Комплект: STEP, эскизы с размерами, отчёт — сборка с экспортом.",
            "Выдать комплект",
            "run:kit",
            "дальше: комплект",
        )
    else:
        nxt = _next(
            "kit",
            "done",
            "Комплект готов",
            "STEP, эскизы, отчёт — скачайте или передайте в САПР.",
            "Скачать комплект",
            "download",
            "готово",
        )
    return {"stages": st, "next": nxt, "layout_state": L, "errors": errors, "built": len(built)}


def leaf_summary(info: dict, chosen: str | None) -> dict:
    """Вклад листового узла в сводку родителя: масса и запас выбранного (или первого собранного) варианта."""
    built = [v for v in info.get("variants") or [] if v.get("built")]
    v = next((x for x in built if x["id"] == chosen), built[0] if built else None)
    return {
        "name": info["name"],
        "title": info.get("title") or info["name"],
        "mass": v.get("mass_kg") if v else None,
        "kmin": v.get("k_min") if v else None,
        "done": info["next"]["kind"] == "done",
    }


def _name(c: dict) -> str:
    return c.get("title") or c["name"]


def aggregate(info: dict, children: list[dict]) -> dict:
    """Сводный узел: задание и общая компоновка свои, «Узлы» и «Сводный комплект» — из дочерних проектов."""
    own = info["stages"]
    st = dict(own)
    kinds = [c["next"]["kind"] for c in children]
    running = [c for c in children if c["next"]["kind"] == "running"]
    waiting = [c for c in children if c["next"]["kind"] == "you"]
    agent = [c for c in children if c["next"]["kind"] == "agent"]
    all_done = bool(children) and all(k == "done" for k in kinds)
    if own["layout"] != "done":
        st["design"] = "todo"
        st["kit"] = "todo"
        nxt = dict(info["next"])
        nxt["title"] = nxt["title"].replace("Компоновка", "Общая компоновка")
    else:
        st["design"] = "agent" if running else "wait" if waiting else "done" if all_done else "next"
        st["kit"] = "done" if own["kit"] == "done" else "next" if all_done else "todo"
        if running:
            c = running[0]
            hint = c["next"].get("hint") or ""
            nxt = _next("design", "running", f"Агент работает: {_name(c)}", hint, "", "open:" + c["name"], "у агента")
        elif waiting:
            c = waiting[0]
            hint = "; ".join(f"{_name(x)}: {x['next']['label'].lower()}" for x in waiting)
            title = "Ждут вас: " + ", ".join(_name(x) for x in waiting)
            label = f"Открыть «{_name(c)}»"
            nxt = _next("design", "you", title, hint, label, "open:" + c["name"], f"ждут вас: {len(waiting)}")
        elif agent:
            c = agent[0]
            hint = "; ".join(f"{_name(x)}: {x['next']['label'].lower()}" for x in agent)
            title = "Можно поручить агенту: " + ", ".join(_name(x) for x in agent)
            label = f"Открыть «{_name(c)}»"
            nxt = _next("design", "agent", title, hint, label, "open:" + c["name"], f"дальше: узлов {len(agent)}")
        elif own["kit"] == "done":
            hint = "STEP сборки, спецификация, отчёт."
            nxt = _next("kit", "done", "Сводный комплект готов", hint, "Скачать", "download", "готово")
        else:
            hint = "Сводный комплект: STEP сборки, спецификация по узлам, отчёт."
            label = "Собрать сводный комплект"
            nxt = _next("kit", "agent", "Все узлы готовы", hint, label, "run:kit", "дальше: комплект")
    # сводка вверх по листовым узлам: лист — вклад своего варианта, сводный ребёнок — его листы
    leaves = [leaf_summary(c, c.get("chosen")) for c in children if not c.get("children")] + [
        g for c in children if c.get("children") for g in (c.get("summary") or {}).get("leaves", [])
    ]
    mass = sum(float(x.get("mass") or 0) for x in leaves)
    ks = [float(x["kmin"]) for x in leaves if x.get("kmin") is not None]
    summary = {
        "nodes": len(leaves),
        "done": sum(1 for x in leaves if x.get("done")),
        "mass_kg": round(mass, 2),
        "k_min": min(ks) if ks else None,
        "leaves": leaves,
    }
    return {"stages": st, "next": nxt, "summary": summary}
