"""Полный цикл по варианту: модель -> геометрия -> правила/проверки/расчёт -> экспорт -> отчёт JSON."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from skelcad.context import MissingStandardError
from skelcad.core.findings import LEVEL_RU, Finding, calc_findings, sort_findings
from skelcad.core.model import PlatePart, Project, text
from skelcad.core.project import ProjectDir, save_model
from skelcad.geom.export import export_all
from skelcad.geom.generator import Geometry, generate
from skelcad.geom.views import write_views
from skelcad.rules import Metric, PluginSet, run_calcs, run_checks, run_metrics, run_rules


def blanks(m: Project) -> dict[str, int]:
    return dict(
        Counter(
            f"лист δ{p.thickness:g}" if isinstance(p, PlatePart) else f"труба {p.tube_size.replace('x', '×')}"
            for p in m.parts
        )
    )


def analyse(pd: ProjectDir, m: Project, g: Geometry) -> tuple[list[Finding], list, list[Metric]]:
    """Правила + проверки + расчёты + метрики по собранной модели и геометрии."""
    ps = PluginSet.collect(pd.ctx, pd.plugins)
    findings = run_rules(ps, m, pd.ctx) + run_checks(ps, m, g, pd.ctx)
    calc_items, skipped = run_calcs(ps, m, g, pd.ctx)
    findings += skipped + calc_findings(calc_items, "calc")
    metrics = run_metrics(ps, m, g, calc_items, pd.ctx)
    return sort_findings(findings), calc_items, metrics


def build_variant(
    pd: ProjectDir, variant: str | None, out_root: Path, export: bool = True, verbose: bool = False
) -> dict:
    log = print if verbose else (lambda *a, **k: None)
    m = pd.resolve(variant)
    name = m.variant or m.id
    lang = m.lang
    log(f"== {name}: {text(m.title, lang)}  [{pd.ctx.describe()}]")
    g = generate(m, pd.ctx)
    log(f"   геометрия: {len(g.parts)} деталей, {len(g.fasteners)} крепёжных, {len(g.bodies)} опорных тел")

    findings, calc_items, metrics = analyse(pd, m, g)

    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    save_model(m, out / "model.yaml")
    files: dict = {"parts_step": {}, "parts_stl": {}, "svg": {}}
    if export:
        files = export_all(m, g, pd.ctx, out)
        files["svg"] = {k: f"{name}/{v}" for k, v in write_views(g.assembly(m, with_purchased=True), out, name).items()}

    try:
        masses = g.masses(m, pd.ctx)
    except MissingStandardError as e:
        masses = {}
        findings.append(
            Finding(
                level="warning",
                code="MISSING-STD",
                ref="project",
                source="pipeline",
                message=f"масса не вычислена — {e}",
            )
        )
    bb = g.assembly(m, with_purchased=False).bounding_box()
    counts = Counter(f.level for f in findings)
    summary = {
        "mass_kg": round(sum(masses.values()), 2) if masses else None,
        "envelope_mm": [round(bb.size.X), round(bb.size.Y), round(bb.size.Z)],
        "parts": len(m.parts),
        "weld_length_mm": round(sum(w.length for w in m.welds)),
        "welds": len(m.welds),
        "fasteners": len(m.fasteners),
        "blanks": blanks(m),
        "K": {i.id: i.K for i in calc_items},
        "K_min": min((i.K for i in calc_items), default=None),
        "K_min_item": min(calc_items, key=lambda i: i.K).title if calc_items else None,
        "findings": {lvl: counts.get(lvl, 0) for lvl in ("error", "warning", "info")},
    }
    report = {
        "project": m.id,
        "project_title": text(pd.spec.title, lang),
        "variant": name,
        "title": text(m.title, lang),
        "description": text(m.description, lang),
        "standards": list(pd.ctx.standards),
        "summary": summary,
        "metrics": [x.model_dump() for x in metrics],
        "derived": m.derived,
        "requirements": m.requirements.model_dump(),
        "parts": [
            {
                "id": p.id,
                "name": text(p.name, lang),
                "role": p.role,
                "mass_kg": round(masses[p.id], 2) if p.id in masses else None,
            }
            for p in m.parts
        ],
        "welds": [
            {"id": w.id, "parts": list(w.parts), "leg": w.leg, "length": round(w.length), "note": w.note}
            for w in m.welds
        ],
        "calc": [i.model_dump() | {"ok": i.ok} for i in calc_items],
        "findings": [f.model_dump() for f in findings],
        "assumptions": [
            a.model_dump(include={"id", "topic", "text"}) | {"text": text(a.text, lang)} for a in m.assumptions
        ],
        "files": files,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"   масса {summary['mass_kg']} кг, габарит {summary['envelope_mm']} мм, швы {summary['weld_length_mm']} мм")
    if calc_items:
        log(f"   K_min = {summary['K_min']:.2f} ({summary['K_min_item']})")
    log("   замечания: " + ", ".join(f"{LEVEL_RU[k]} {v}" for k, v in summary["findings"].items()))
    for f in findings:
        if f.level != "info":
            log(f"   [{LEVEL_RU[f.level]}] {f.code} {f.ref}: {f.message}")
    log(f"   -> {out}")
    return report
