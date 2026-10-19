"""Загрузка проекта из папки: project.yaml + variants/<имя>.yaml + генератор + плагины.

project.yaml:
  id, title, description, lang, coordinate_system
  standards: [gost]                 пакеты стандартов
  tables: {materials: {...}}        локальные таблицы (приоритет над пакетами)
  generator: generators/x.py        модуль с generate(project, params, ctx) -> GenResult
  plugins: [plugins/calc.py, …]     модули с RULES / CHECKS / CALCS / METRICS
  requirements, skeleton, assumptions, params (параметры по умолчанию для всех вариантов)
variants/<имя>.yaml:
  id, title, description, params (сливаются поверх project.params), assumptions
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import yaml
from pydantic import BaseModel

from skelcad.context import Context
from skelcad.core.model import (
    Assumption,
    LayoutApproval,
    LayoutState,
    Project,
    Requirements,
    Skeleton,
    Text,
    layout_hash,
)
from skelcad.rules import GenResult, load_module


class ProjectSpec(BaseModel):
    id: str
    title: Text
    description: Text = ""
    lang: str = "ru"
    coordinate_system: str = ""
    standards: list[str] = []
    tables: dict[str, dict] = {}
    generator: str | None = None
    plugins: list[str] = []
    requirements: Requirements = Requirements()
    skeleton: Skeleton = Skeleton()
    assumptions: list[Assumption] = []
    params: dict = {}
    layout: LayoutApproval | None = None  # «Компоновка согласована» (ставит рабочее место конструктора)


class VariantSpec(BaseModel):
    id: str
    title: Text = ""
    description: Text = ""
    params: dict = {}
    assumptions: list[str] = []


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def read_spec(root: Path) -> ProjectSpec:
    """Спецификация проекта из project.yaml без загрузки генератора и плагинов (код проекта не исполняется)."""
    spec = ProjectSpec.model_validate(_read(Path(root) / "project.yaml"))
    spec.requirements.standards = list(dict.fromkeys(spec.standards + spec.requirements.standards))
    return spec


def read_variant(root: Path, name: str) -> VariantSpec:
    f = Path(root) / "variants" / f"{name}.yaml"
    if not f.exists():
        raise FileNotFoundError(f"вариант «{name}» не найден: {f}")
    return VariantSpec.model_validate(_read(f))


def base_project(s: ProjectSpec, variant: VariantSpec | None = None) -> Project:
    """Проект без узлов: требования, скелет, допущения, состояние компоновки — то, что есть до генератора."""
    return Project(
        id=s.id,
        title=variant.title or s.title if variant else s.title,
        description=variant.description or s.description if variant else s.description,
        lang=s.lang,
        variant=variant.id if variant else None,
        coordinate_system=s.coordinate_system,
        requirements=s.requirements.model_copy(deep=True),
        skeleton=s.skeleton.model_copy(deep=True),
        assumptions=[a.model_copy() for a in s.assumptions],
        layout=LayoutState(hash=layout_hash(s.skeleton, s.requirements), approved=s.layout),
    )


class ProjectDir:
    """Папка проекта: спецификация, варианты, контекст и загруженные модули."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.spec = read_spec(self.root)
        self.ctx = Context(self.spec.requirements.standards, self.spec.tables)
        self.generator: ModuleType | None = (
            load_module(self.root / self.spec.generator) if self.spec.generator else None
        )
        self.plugins: list[ModuleType] = [load_module(self.root / p) for p in self.spec.plugins]

    def variants(self) -> list[VariantSpec]:
        vdir = self.root / "variants"
        if not vdir.is_dir():
            return []
        return [VariantSpec.model_validate(_read(f)) for f in sorted(vdir.glob("*.yaml"))]

    def variant(self, name: str) -> VariantSpec:
        return read_variant(self.root, name)

    def base_project(self, variant: VariantSpec | None = None) -> Project:
        return base_project(self.spec, variant)

    def resolve(self, variant: VariantSpec | str | None = None) -> Project:
        """Собрать модель: база проекта + генератор(params варианта)."""
        if isinstance(variant, str):
            variant = self.variant(variant)
        project = self.base_project(variant)
        params = _merge(self.spec.params, variant.params if variant else {})
        if self.generator is None:
            return project
        res: GenResult = self.generator.generate(project, params, self.ctx)
        project.units += res.units
        project.derived.update(res.derived)
        project.assumptions += res.assumptions
        if variant:
            project.assumptions += [
                Assumption(id=f"V{i + 1}", topic="variant", text=t) for i, t in enumerate(variant.assumptions)
            ]
        return project


def save_model(project: Project, path: Path) -> None:
    """Сохранить разрешённую модель (YAML) — срез источника истины для агента и для diff."""
    data = project.model_dump(mode="json", exclude_defaults=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
