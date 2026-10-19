"""/api для workbench: обзор проектов с числами последней сборки каждого варианта."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

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


def project_overview(ws: Workspace, out_dir: Path, name: str) -> dict:
    info = ws.info(name)
    info["variants"] = [variant_overview(out_dir, name, v) for v in ws.variants(name)]
    info["state"] = "constructor"  # «у агента» появится с задачами агенту (M2, шаг 8)
    return info


def projects_overview(ws: Workspace, out_dir: Path) -> dict:
    items = [project_overview(ws, out_dir, n) for n in ws.names()]
    return {
        "summary": f"проектов: {len(items)}" + (": " + ", ".join(i["name"] for i in items) if items else ""),
        "projects": items,
        "templates": ws.templates_list(),
    }
