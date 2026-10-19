"""Генератор планки: параметры варианта + скелет проекта -> узел из одной детали.

Листовая деталь с четырьмя сквозными резьбовыми отверстиями по прямоугольнику pitch_x × pitch_y;
центр планки — в начале координат, нижняя плоскость — Z=0 (база `base` скелета). Размер резьбы — из
интерфейса `mount`; параметры резьбы — из таблицы fasteners контекста (локальной или пакета стандарта),
если там нет этого размера — из params.thread. Модель Hole поля «резьба» не имеет: отверстие задаётся
по диаметру сверла, резьба — purpose=thread и note.
"""

from __future__ import annotations

from pydantic import BaseModel

from skelcad.context import Context, MissingStandardError
from skelcad.core.model import Assumption, Hole, Outline, Placement, PlatePart, Project, Unit
from skelcad.rules import GenResult

X: tuple = (1.0, 0.0, 0.0)
Z: tuple = (0.0, 0.0, 1.0)
C_PLATE = "#7f93a8"


class PlateParams(BaseModel):
    length: float = 120
    width: float = 60
    thickness: float = 10
    corner_radius: float = 5


class HoleParams(BaseModel):
    pitch_x: float = 90
    pitch_y: float = 30


class ThreadParams(BaseModel):
    """Резьба по ГОСТ 24705; tap_drill — сверло по ГОСТ 19257 (запасной источник, если нет таблицы)."""

    d: float
    pitch: float
    tap_drill: float


class Params(BaseModel):
    material: str = "St3sp"
    plate: PlateParams = PlateParams()
    holes: HoleParams = HoleParams()
    thread: ThreadParams | None = None


def thread_data(size: str, p: Params, ctx: Context) -> tuple[dict, str]:
    """Параметры резьбы: таблица fasteners, иначе params.thread."""
    try:
        f = dict(ctx.fastener(size))
        f.setdefault("tap_drill", f["d"] - f["pitch"])  # сверло под резьбу ≈ d − P
        return f, "таблица fasteners"
    except MissingStandardError:
        if p.thread is None:
            raise
        return p.thread.model_dump(), "params.thread"


def generate(project: Project, params: dict, ctx: Context) -> GenResult:
    p = Params.model_validate(params)
    mount = project.skeleton.interface("mount")
    thread = str(mount.params["thread"])
    f, source = thread_data(thread, p, ctx)
    tap, d = float(f["tap_drill"]), float(f["d"])
    pl, hp = p.plate, p.holes
    L, W, t = pl.length, pl.width, pl.thickness

    holes = [
        Hole(
            id=f"h{i}{j}",
            purpose="thread",
            diameter=tap,
            center=(x, y),
            note=f"резьба {thread}-6H сквозная, сверло Ø{tap:g}",
        )
        for i, y in enumerate((-hp.pitch_y / 2, hp.pitch_y / 2))
        for j, x in enumerate((-hp.pitch_x / 2, hp.pitch_x / 2))
    ]
    plate = PlatePart(
        id="plate",
        name=f"Планка δ{t:g} {L:g}×{W:g}, 4 отв. {thread}",
        role="plate",
        material=p.material,
        color=C_PLATE,
        thickness=t,
        outline=Outline(
            points=[(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)],
            corner_radius=pl.corner_radius,
        ),
        placement=Placement(origin=(0.0, 0.0, 0.0), u=X, normal=Z),
        holes=holes,
    )
    edge_x = (L - hp.pitch_x) / 2
    edge_y = (W - hp.pitch_y) / 2
    mount.params.update({"tap_drill": tap, "pitch": float(f["pitch"])})
    unit = Unit(
        id="plate",
        name="Планка",
        material=p.material,
        interfaces=["mount"],
        parts=[plate],
        joints=[],
        derived={
            "планка, мм": f"{L:g}×{W:g}×{t:g}",
            "отверстия": f"4 × {thread}, шаг {hp.pitch_x:g}×{hp.pitch_y:g}",
            "сверло под резьбу, мм": tap,
            "кромка от оси отверстия X / Y, мм": f"{edge_x:g} / {edge_y:g}",
            "кромка в долях d, X / Y": f"{edge_x / d:.2f} / {edge_y / d:.2f}",
            "длина свинчивания в долях d": round(t / d, 2),
            "источник параметров резьбы": source,
        },
    )
    assumptions = [
        Assumption(
            id="T1",
            topic="thread",
            text=f"Резьба {thread} (шаг {f['pitch']:g}) нарезается на проход, сверло Ø{tap:g}; "
            "в модели отверстие показано по диаметру сверла.",
        )
    ]
    return GenResult(units=[unit], derived=dict(unit.derived), assumptions=assumptions)
