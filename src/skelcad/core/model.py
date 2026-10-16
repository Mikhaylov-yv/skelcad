"""Проектная модель SkelCAD — источник истины.

Уровни сверху вниз: Project → Requirements, Skeleton (datum-элементы, envelope, интерфейсы) →
Units (узлы) → Parts (детали из заготовок) и Joints (соединения). Геометрия, чертежи и отчёты —
производные от этой модели.

Единицы: длины в мм, силы в кН, масса в кг, углы в градусах. Система координат — у проекта
(`Project.coordinate_system`), все положения абсолютные.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]

# Текст на одном или нескольких языках: "Плита" или {ru: "Плита", en: "Plate"}.
Text = str | dict[str, str]
Scalar = int | float | str
Status = Literal["draft", "proposed", "approved"]


def text(t: Text, lang: str = "ru") -> str:
    if isinstance(t, str):
        return t
    return t.get(lang) or next(iter(t.values()), "")


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dist3(a: Vec3, b: Vec3) -> float:
    return math.dist(a, b)


class Kinded(BaseModel):
    """Член размеченного объединения: поле `kind` сохраняется в YAML даже при exclude_defaults."""

    @model_serializer(mode="wrap")
    def _keep_kind(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        if isinstance(data, dict) and "kind" not in data:
            data = {"kind": self.kind, **data}
        return data


class Entity(BaseModel):
    """Общие поля любой сущности модели: идентификатор, происхождение, статус согласования, теги."""

    id: str
    source: str = "human"  # human | agent:<run>
    status: Status = "approved"
    tags: list[str] = []
    note: str = ""


# ---------- геометрические примитивы ----------


class Placement(BaseModel):
    """Плоскость эскиза детали: начало, ось u эскиза и нормаль (направление выдавливания)."""

    origin: Vec3
    u: Vec3
    normal: Vec3

    @property
    def v(self) -> Vec3:
        return cross(self.normal, self.u)

    def to_global(self, p: Vec2, w: float = 0.0) -> Vec3:
        u, v, n = self.u, self.v, self.normal
        return tuple(self.origin[i] + p[0] * u[i] + p[1] * v[i] + w * n[i] for i in range(3))


class Cylinder(BaseModel):
    """Цилиндр по центру и оси — опорное тело интерфейса (вал, ось, труба соседнего узла)."""

    center: Vec3
    axis: Vec3
    diameter: float
    length: float


class Hole(BaseModel):
    id: str
    purpose: str  # anchor, bolt, shaft_seat, part_seat, …
    diameter: float
    center: Vec2  # в координатах эскиза детали
    tolerance: str | None = None  # поле допуска, например H8
    note: str = ""


class Outline(BaseModel):
    """Контур пластины: выпуклая оболочка точек и окружностей (как эскиз в САПР)."""

    points: list[Vec2]
    circles: list[tuple[float, float, float]] = []  # (u, v, R)
    corner_radius: float = 0.0  # скругление углов (только без окружностей)


class Trim(BaseModel):
    """Обрезка тела полупространством: остаётся часть, где (p − point)·normal ≥ 0."""

    point: Vec3
    normal: Vec3
    reason: str = ""


# ---------- детали ----------


class PartBase(Entity, Kinded):
    name: Text
    role: str = ""  # смысл в узле: base_plate, cheek, rib, hub, side, cover, boss, …
    material: str
    color: str = "#8aa1b8"


class PlatePart(PartBase):
    """Деталь из листа: эскиз на плоскости + выдавливание на толщину."""

    kind: Literal["plate"] = "plate"
    thickness: float
    outline: Outline
    placement: Placement
    holes: list[Hole] = []
    trims: list[Trim] = []
    free_edges: dict[str, float] = {}  # свободные кромки (для правил устойчивости), мм


class TubePart(PartBase):
    """Деталь из трубы: типоразмер каталога, отрезок по оси, расточка после сварки."""

    kind: Literal["tube"] = "tube"
    tube_size: str  # типоразмер по каталогу, напр. "76x14"
    od: float
    wall: float
    length: float
    center: Vec3
    axis: Vec3
    bore: Hole | None = None


Part = Annotated[PlatePart | TubePart, Field(discriminator="kind")]


# ---------- соединения ----------


class WeldSegment(BaseModel):
    start: Vec3
    end: Vec3

    @property
    def length(self) -> float:
        return dist3(self.start, self.end)


class Weld(Entity, Kinded):
    kind: Literal["weld"] = "weld"
    parts: tuple[str, str]
    weld_type: Literal["fillet"] = "fillet"
    leg: float  # катет, мм
    segments: list[WeldSegment]
    access_gap: float | None = None  # ширина щели, из которой варят, мм
    access_depth: float | None = None  # глубина щели, мм

    @property
    def length(self) -> float:
        return sum(s.length for s in self.segments)


class Fastener(Entity, Kinded):
    """Крепёж через отверстие детали: анкер в основание или болт.

    `position` — точка на опорной поверхности (например, лицо стены), `axis` — направление
    от неё наружу, `clamp_depth` — расстояние по оси до плоскости прижима шайбы.
    """

    kind: Literal["fastener"] = "fastener"
    fastener_type: str = "anchor"  # anchor | bolt
    size: str  # M16
    part: str  # деталь, через которую проходит
    hole: str
    position: Vec3
    axis: Vec3 = (0.0, 1.0, 0.0)
    clamp_depth: float


Joint = Annotated[Weld | Fastener, Field(discriminator="kind")]


# ---------- скелет и требования ----------


class Datum(Entity, Kinded):
    """Базовый элемент скелета: плоскость (origin + normal), ось (origin + direction) или точка."""

    kind: Literal["plane", "axis", "point"]
    origin: Vec3
    direction: Vec3 | None = None  # нормаль плоскости или направление оси
    name: Text = ""


class Envelope(Entity, Kinded):
    """Допустимый (keep_in) или запретный (keep_out) объём — в M0 только боксы."""

    kind: Literal["keep_in", "keep_out"]
    min: Vec3
    max: Vec3
    name: Text = ""


class Interface(Entity):
    """Посадочное место к соседнему узлу: что приходит снаружи (стена, вал, фланец) и с какой нагрузкой."""

    kind: str  # mount_plane, shaft_seat, flange, …
    name: Text = ""
    datum: str | None = None  # ссылка на Datum
    body: Cylinder | None = None  # опорное тело для проверок и визуализации (вал, ось)
    params: dict[str, Scalar] = {}  # диаметр, посадка, предельные размеры и т. п.
    loads: dict[str, float] = {}  # нагрузки, приложенные через интерфейс, кН / кН·м


class Skeleton(BaseModel):
    datums: list[Datum] = []
    envelopes: list[Envelope] = []
    interfaces: list[Interface] = []

    def interface(self, iid: str) -> Interface:
        return next(i for i in self.interfaces if i.id == iid)


class Requirements(BaseModel):
    purpose: Text = ""
    loads: dict[str, float] = {}  # именованные нагрузки, кН / кН·м
    factors: dict[str, float] = {}  # коэффициенты: gamma_dyn, …
    safety_required: float = 1.5
    environment: dict[str, Scalar] = {}
    constraints: dict[str, Scalar] = {}
    standards: list[str] = []  # пакеты стандартов, которые нужны проекту: gost, iso


# ---------- узлы и проект ----------


class Assumption(Entity):
    text: Text
    topic: str = "общее"


class Unit(Entity):
    """Узел: детали и соединения; ссылается на интерфейсы скелета, не на другие узлы."""

    name: Text
    material: str = ""  # материал по умолчанию для деталей
    interfaces: list[str] = []
    parts: list[Part] = []
    joints: list[Joint] = []
    derived: dict[str, Scalar] = {}

    def part(self, pid: str) -> PlatePart | TubePart:
        return next(p for p in self.parts if p.id == pid)

    @property
    def welds(self) -> list[Weld]:
        return [j for j in self.joints if isinstance(j, Weld)]

    @property
    def fasteners(self) -> list[Fastener]:
        return [j for j in self.joints if isinstance(j, Fastener)]


class Project(BaseModel):
    """Проект (одна разрешённая конфигурация изделия — вариант)."""

    id: str
    title: Text
    description: Text = ""
    lang: str = "ru"
    variant: str | None = None  # имя варианта, если проект построен из variants/<имя>.yaml
    coordinate_system: str = ""
    requirements: Requirements = Requirements()
    skeleton: Skeleton = Skeleton()
    units: list[Unit] = []
    assumptions: list[Assumption] = []
    derived: dict[str, Scalar] = {}

    # --- навигация ---
    @property
    def parts(self) -> list[PlatePart | TubePart]:
        return [p for u in self.units for p in u.parts]

    @property
    def welds(self) -> list[Weld]:
        return [w for u in self.units for w in u.welds]

    @property
    def fasteners(self) -> list[Fastener]:
        return [f for u in self.units for f in u.fasteners]

    def part(self, pid: str) -> PlatePart | TubePart:
        return next(p for p in self.parts if p.id == pid)

    def parts_by_role(self, role: str) -> list[PlatePart | TubePart]:
        return [p for p in self.parts if p.role == role]

    def unit(self, uid: str) -> Unit:
        return next(u for u in self.units if u.id == uid)
