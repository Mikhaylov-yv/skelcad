"""Проектная модель SkelCAD — источник истины.

Уровни сверху вниз: Project → Requirements, Skeleton (datum-элементы, envelope, интерфейсы) →
Units (узлы) → Parts (детали из заготовок) и Joints (соединения). Геометрия, чертежи и отчёты —
производные от этой модели.

Единицы: длины в мм, силы в кН, масса в кг, углы в градусах. Система координат — у проекта
(`Project.coordinate_system`), все положения абсолютные.
"""

from __future__ import annotations

import hashlib
import json
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


def axis_index(vec: Vec3 | None) -> int | None:
    """Номер оси (0, 1, 2), вдоль которой направлен вектор (в любую сторону), или None, если он наклонный."""
    if not vec:
        return None
    n = math.sqrt(sum(c * c for c in vec)) or 1.0
    return next((i for i in range(3) if abs(abs(vec[i]) / n - 1.0) < 1e-6), None)


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


class SurroundingBase(Entity, Kinded):
    """Тело обстановки: не изготавливается, но ограничивает изделие и показывается на компоновочном эскизе
    (стена, пол, труба, ответная деталь, соседнее оборудование, зона обслуживания)."""

    role: str = ""  # wall | floor | ceiling | pipe | shaft | equipment | service_zone | mating_part | other
    name: Text = ""
    material: str = ""


class PlaneBody(SurroundingBase):
    """Плоская поверхность (стена, пол, потолок): квадрат 2·extent в плоскости, тело толщиной thickness за ней
    (против нормали); нормаль смотрит к изделию."""

    kind: Literal["plane"] = "plane"
    origin: Vec3
    normal: Vec3
    extent: float = 500.0
    thickness: float = 100.0

    def bbox(self) -> tuple[Vec3, Vec3]:
        """Габарит тела: квадрат 2·extent в плоскости, толщина против нормали (осевая нормаль);
        наклонная плоскость — описывающий бокс квадрата с толщиной во все стороны."""
        lo = [self.origin[i] - self.extent for i in range(3)]
        hi = [self.origin[i] + self.extent for i in range(3)]
        ax = axis_index(self.normal)
        if ax is not None:
            if self.normal[ax] > 0:
                lo[ax], hi[ax] = self.origin[ax] - self.thickness, self.origin[ax]
            else:
                lo[ax], hi[ax] = self.origin[ax], self.origin[ax] + self.thickness
        return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


class BoxBody(SurroundingBase):
    """Параллелепипед: соседнее оборудование, ответная деталь, зона обслуживания."""

    kind: Literal["box"] = "box"
    min: Vec3
    max: Vec3

    def bbox(self) -> tuple[Vec3, Vec3]:
        return self.min, self.max


class CylinderBody(SurroundingBase):
    """Цилиндр: труба, вал, колонна рядом с изделием."""

    kind: Literal["cylinder"] = "cylinder"
    center: Vec3
    axis: Vec3
    diameter: float
    length: float

    def bbox(self) -> tuple[Vec3, Vec3]:
        """Точный описывающий бокс цилиндра: по оси i полуразмер (L/2)·|a_i| + (d/2)·√(1 − a_i²)."""
        n = math.sqrt(sum(c * c for c in self.axis)) or 1.0
        a = [c / n for c in self.axis]
        half = [
            self.length / 2 * abs(a[i]) + self.diameter / 2 * math.sqrt(max(0.0, 1 - a[i] * a[i])) for i in range(3)
        ]
        lo = tuple(self.center[i] - half[i] for i in range(3))
        hi = tuple(self.center[i] + half[i] for i in range(3))
        return lo, hi


Surrounding = Annotated[PlaneBody | BoxBody | CylinderBody, Field(discriminator="kind")]


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
    surroundings: list[Surrounding] = []  # обстановка: тела вокруг изделия (стена, пол, труба, соседний узел)

    def interface(self, iid: str) -> Interface:
        return next(i for i in self.interfaces if i.id == iid)

    def datum(self, did: str) -> Datum | None:
        return next((d for d in self.datums if d.id == did), None)


class Requirements(BaseModel):
    purpose: Text = ""
    loads: dict[str, float] = {}  # именованные нагрузки, кН / кН·м
    factors: dict[str, float] = {}  # коэффициенты: gamma_dyn, …
    safety_required: float = 1.5
    environment: dict[str, Scalar] = {}
    constraints: dict[str, Scalar] = {}
    standards: list[str] = []  # пакеты стандартов, которые нужны проекту: gost, iso


# ---------- согласование компоновки ----------


class LayoutApproval(BaseModel):
    """Отметка конструктора «Компоновка согласована»: кто, когда, на каком коммите; hash — скелет с обстановкой
    и требования на момент согласования (см. layout_hash)."""

    by: str
    at: str
    commit: str = ""
    hash: str


class LayoutState(BaseModel):
    """Состояние компоновки разрешённого проекта: текущий хеш и отметка согласования (если была)."""

    hash: str
    approved: LayoutApproval | None = None

    @property
    def changed(self) -> bool:
        """Скелет, обстановка или требования менялись после согласования."""
        return self.approved is not None and self.approved.hash != self.hash


def layout_hash(skeleton: Skeleton, requirements: Requirements) -> str:
    """Хеш того, что показывает компоновочный эскиз: скелет (базы, зоны, интерфейсы, обстановка) и требования
    (без списка пакетов стандартов — он собирается из двух мест спецификации)."""
    data = {
        "skeleton": skeleton.model_dump(mode="json", exclude_defaults=True),
        "requirements": requirements.model_dump(mode="json", exclude_defaults=True, exclude={"standards"}),
    }
    return hashlib.sha1(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


# ---------- эскиз с размерами (M2.1, D18) ----------


class SketchDim(BaseModel):
    """Явный размер на эскизе: между двумя точками модели (`between`) по оси `axis` или размер сущности
    (`of` + `kind`: thickness | diameter | length). Ссылки: datum:<id>, interface:<id>, surrounding:<id>,
    part:<id>, part:<id>/hole:<hid>, fastener:<id>, point:x,y,z."""

    view: str | None = None  # main | left | top; None — на всех видах, где размер виден
    between: tuple[str, str] | None = None
    axis: Literal["X", "Y", "Z"] | None = None
    of: str | None = None
    kind: Literal["thickness", "diameter", "length"] | None = None
    text: str | None = None


class SketchSpec(BaseModel):
    """Раздел `sketch` проекта или варианта: какие виды показывать, какие автоматические размеры скрыть
    (по id из <v>_sketch.json), какие размеры добавить."""

    views: list[str] = []
    hide: list[str] = []
    dims: list[SketchDim] = []


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
    layout: LayoutState | None = Field(default=None, exclude=True)  # согласование компоновки; в YAML не пишется
    sketch: SketchSpec = Field(default_factory=SketchSpec, exclude=True)  # настройки эскиза (проект + вариант)

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
