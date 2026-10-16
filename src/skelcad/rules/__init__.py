"""Контракт плагинов и реестр.

Плагин — Python-модуль, который объявляет списки функций:
  RULES:    rule(project, ctx) -> list[Finding]                — правила над моделью (без геометрии)
  CHECKS:   check(project, geometry, ctx) -> list[Finding]     — проверки на геометрии
  CALCS:    calc(project, geometry, ctx) -> list[CalcItem]     — оценочные расчёты
  METRICS:  metric(project, geometry, calc_items, ctx) -> list[Metric]  — метрики для сравнения вариантов
Генератор — модуль с функцией generate(project, params, ctx) -> GenResult.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from skelcad.context import Context, MissingStandardError
from skelcad.core.findings import CalcItem, Finding
from skelcad.core.model import Assumption, Project, Scalar, Unit


class Metric(BaseModel):
    id: str
    title: str
    value: float | str
    better: str | None = None  # "min" | "max" | None


@dataclass
class GenResult:
    """Результат генератора: узлы, производные параметры и допущения (topic, text)."""

    units: list[Unit]
    derived: dict[str, Scalar] = field(default_factory=dict)
    assumptions: list[Assumption] = field(default_factory=list)


Rule = Callable[[Project, Context], list[Finding]]
Check = Callable[[Project, Any, Context], list[Finding]]
Calc = Callable[[Project, Any, Context], list[CalcItem]]
MetricFn = Callable[[Project, Any, list[CalcItem], Context], list[Metric]]


def load_module(path: Path, name: str | None = None) -> ModuleType:
    """Загрузить модуль плагина/генератора из файла (без песочницы — M0)."""
    name = name or f"skelcad_plugin_{path.stem}_{abs(hash(str(path.resolve())))}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"не удалось загрузить модуль {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@dataclass
class PluginSet:
    rules: list[Rule] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    calcs: list[Calc] = field(default_factory=list)
    metrics: list[MetricFn] = field(default_factory=list)

    def add_module(self, mod: ModuleType) -> None:
        self.rules += getattr(mod, "RULES", [])
        self.checks += getattr(mod, "CHECKS", [])
        self.calcs += getattr(mod, "CALCS", [])
        self.metrics += getattr(mod, "METRICS", [])

    @classmethod
    def collect(cls, ctx: Context, project_modules: list[ModuleType] = (), builtin: bool = True) -> PluginSet:
        ps = cls()
        if builtin:
            from skelcad.rules import generic, geometric

            ps.add_module(generic)
            ps.add_module(geometric)
        ps.rules += ctx.standard_rules()
        for m in project_modules:
            ps.add_module(m)
        return ps


def _missing(fn: Callable, err: Exception, source: str) -> Finding:
    return Finding(
        level="warning", code="MISSING-STD", ref="project", source=source, message=f"{fn.__name__}: пропущено — {err}"
    )


def run_rules(ps: PluginSet, project: Project, ctx: Context) -> list[Finding]:
    out = []
    for r in ps.rules:
        try:
            out += r(project, ctx)
        except MissingStandardError as e:
            out.append(_missing(r, e, "rules"))
    return out


def run_checks(ps: PluginSet, project: Project, geometry, ctx: Context) -> list[Finding]:
    out = []
    for c in ps.checks:
        try:
            out += c(project, geometry, ctx)
        except MissingStandardError as e:
            out.append(_missing(c, e, "checks"))
    return out


def run_calcs(ps: PluginSet, project: Project, geometry, ctx: Context) -> tuple[list[CalcItem], list[Finding]]:
    items, skipped = [], []
    for c in ps.calcs:
        try:
            items += c(project, geometry, ctx)
        except MissingStandardError as e:
            skipped.append(_missing(c, e, "calc"))
    return items, skipped


def run_metrics(ps: PluginSet, project: Project, geometry, items: list[CalcItem], ctx: Context) -> list[Metric]:
    out = []
    for m in ps.metrics:
        try:
            out += m(project, geometry, items, ctx)
        except MissingStandardError:
            pass
    return out
