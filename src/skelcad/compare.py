"""Сводная HTML-страница сравнения и согласования вариантов (out/compare.html)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from skelcad.core.findings import LEVEL_RU

TEMPLATES = Path(__file__).parent / "templates"

# общие строки таблицы сравнения: (подпись, функция значения, лучше: min / max / None)
BASE_METRICS = [
    ("Масса изготавливаемых деталей, кг", lambda r: r["summary"]["mass_kg"], "min"),
    ("Габарит X×Y×Z, мм", lambda r: "×".join(map(str, r["summary"]["envelope_mm"])), None),
    ("Число деталей", lambda r: r["summary"]["parts"], "min"),
    ("Заготовки", lambda r: ", ".join(f"{k} — {v} шт" for k, v in r["summary"]["blanks"].items()), None),
    ("Длина швов, мм", lambda r: r["summary"]["weld_length_mm"], "min"),
    ("Минимальный запас K", lambda r: r["summary"]["K_min"], "max"),
]


def _rows(reports: list[dict]) -> list[dict]:
    rows = [(t, [fn(r) for r in reports], better) for t, fn, better in BASE_METRICS]
    # метрики проекта: объединяем по id, порядок — как встретились
    ids = list(dict.fromkeys(x["id"] for r in reports for x in r.get("metrics", [])))
    for mid in ids:
        cells = [next((x for x in r.get("metrics", []) if x["id"] == mid), None) for r in reports]
        first = next(c for c in cells if c)
        rows.append((first["title"], [c["value"] if c else None for c in cells], first.get("better")))
    out = []
    for title, vals, better in rows:
        best = []
        nums = [v for v in vals if isinstance(v, (int, float))]
        if better and len(nums) == len(vals) and len(set(vals)) > 1:
            target = min(vals) if better == "min" else max(vals)
            best = [i for i, v in enumerate(vals) if v == target]
        out.append({"title": title, "values": vals, "best": best})
    return out


def write_compare(reports: list[dict], out: Path) -> Path:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["num"] = lambda v: f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else v
    # общие допущения — одинаковые (id и текст) во всех вариантах
    sets = [{(a["id"], a["text"]) for a in r["assumptions"]} for r in reports]
    common_keys = set.intersection(*sets) if sets else set()
    common = [a for a in reports[0]["assumptions"] if (a["id"], a["text"]) in common_keys]
    calc_ids = [c["id"] for c in reports[0]["calc"]]
    calc_rows = []
    for cid in dict.fromkeys(c["id"] for r in reports for c in r["calc"]):
        row = {"title": next(c["title"] for r in reports for c in r["calc"] if c["id"] == cid), "cells": []}
        for r in reports:
            row["cells"].append(next((c for c in r["calc"] if c["id"] == cid), None))
        calc_rows.append(row)
    html = env.get_template("compare.html.j2").render(
        reports=reports,
        metrics=_rows(reports),
        calc_rows=calc_rows,
        calc_ids=calc_ids,
        common=common,
        level_ru=LEVEL_RU,
        project_title=reports[0].get("project_title") or reports[0]["title"],
        standards=reports[0].get("standards", []),
        generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        data_json=json.dumps(
            {"variants": [{"id": r["variant"], "title": r["title"], "glb": r["files"].get("gltf")} for r in reports]},
            ensure_ascii=False,
        ),
    )
    path = out / "compare.html"
    path.write_text(html, encoding="utf-8")
    return path
