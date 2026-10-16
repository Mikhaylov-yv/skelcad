"""Замечания правил/проверок/расчётов и расчётные позиции — общий формат для всех плагинов."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel

Level = Literal["error", "warning", "info"]
LEVEL_ORDER: tuple[str, ...] = ("error", "warning", "info")
LEVEL_RU = {"error": "ошибка", "warning": "предупреждение", "info": "информация"}


class Finding(BaseModel):
    """Одно замечание. `ref` — ссылка на элемент модели: part:base_plate/hole:a00, weld:w_1, unit:u1."""

    level: Level
    code: str  # код правила: R-EDGE, C-INTERFERE, K-bend_wall
    ref: str
    message: str
    source: str  # имя плагина/пакета, выдавшего замечание: rules.gost, checks.core, calc.bracket


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: LEVEL_ORDER.index(f.level))


class CalcItem(BaseModel):
    """Расчётная позиция: формула, значения, действующее/предельное, запас K."""

    id: str
    title: str
    formula: str
    values: dict[str, float | str]
    demand: float  # действующее
    capacity: float  # предельное
    unit: str
    K: float  # запас = capacity / demand
    K_req: float
    ref: str

    @property
    def ok(self) -> bool:
        return self.K >= self.K_req


def calc_item(
    id_: str, title: str, formula: str, values: dict, demand: float, capacity: float, unit: str, k_req: float, ref: str
) -> CalcItem:
    k = capacity / demand if demand > 0 else math.inf
    return CalcItem(
        id=id_,
        title=title,
        formula=formula,
        values={k_: round(v, 3) if isinstance(v, float) else v for k_, v in values.items()},
        demand=round(demand, 2),
        capacity=round(capacity, 2),
        unit=unit,
        K=round(k, 2),
        K_req=k_req,
        ref=ref,
    )


def calc_findings(items: list[CalcItem], source: str) -> list[Finding]:
    out = []
    for it in items:
        if it.K < 1.0:
            lvl, word = "error", "не обеспечена прочность"
        elif it.K < it.K_req:
            lvl, word = "warning", "запас меньше требуемого"
        else:
            lvl, word = "info", "запас достаточен"
        out.append(
            Finding(
                level=lvl,
                code=f"K-{it.id}",
                ref=it.ref,
                source=source,
                message=f"{it.title}: K = {it.K:.2f} (треб. {it.K_req:g}) — {word}",
            )
        )
    return out
