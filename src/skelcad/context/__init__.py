"""Контекст знаний: пакеты стандартов и доступ к их таблицам (каталогам).

В ядре нет ни одной таблицы. Пакет стандарта — установленный Python-пакет, зарегистрированный
в entry point `skelcad.standards`; модуль пакета объявляет `NAME`, `DATA_DIR` (папка с YAML-таблицами)
и, по желанию, `RULES` (правила над моделью). Проект перечисляет нужные пакеты в
`requirements.standards`, а локальные таблицы может задать прямо в `project.yaml: tables`.

Контракт таблиц, которые ядро умеет читать (ключи — как в пилоте):
  materials[key]: grade, standard, Ry, Ru, Run, E, density (кг/м³)
  fasteners[size]: d, pitch, As, hole, nut_s, nut_e, nut_m, washer_d, washer_s, socket_od
  anchors[size]:   hef, N_Rd, V_Rd, s_min, c_min, Rbt, Rbs
  tubes:           standard, sizes[size]: od, wall
  sheet:           standard, thicknesses[]
  welds:           Rwf, beta_f, beta_z, k_min_by_t[[t_max, k_min]], k_max_factor, access_gap_min, access_depth_ratio_max
  fits:            range[lo, hi], holes[field][es, ei], shafts[field][es, ei] (мкм)
"""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType

import yaml


class MissingStandardError(LookupError):
    """Нужная таблица или запись отсутствует во всех подключённых пакетах стандартов."""


def discover_standards() -> dict[str, ModuleType]:
    """Все установленные пакеты стандартов: имя entry point -> модуль."""
    found = {}
    for ep in entry_points(group="skelcad.standards"):
        found[ep.name] = ep.load()
    return found


class Context:
    def __init__(self, standards: list[str] | None = None, tables: dict[str, dict] | None = None):
        available = discover_standards()
        self.standards: dict[str, ModuleType] = {}
        for name in standards or []:
            if name not in available:
                raise MissingStandardError(
                    f"Пакет стандарта «{name}» не установлен; доступны: {sorted(available) or 'ничего'}"
                )
            self.standards[name] = available[name]
        self.local_tables: dict[str, dict] = dict(tables or {})
        self._cache: dict[str, dict] = {}

    # ---------- таблицы ----------

    def has_table(self, name: str) -> bool:
        try:
            self.table(name)
            return True
        except MissingStandardError:
            return False

    def table(self, name: str) -> dict:
        if name in self._cache:
            return self._cache[name]
        if name in self.local_tables:
            self._cache[name] = self.local_tables[name]
            return self._cache[name]
        for std in self.standards.values():
            f = Path(std.DATA_DIR) / f"{name}.yaml"
            if f.exists():
                self._cache[name] = yaml.safe_load(f.read_text(encoding="utf-8"))
                return self._cache[name]
        raise MissingStandardError(f"Таблица «{name}» не найдена: подключены пакеты {sorted(self.standards) or 'нет'}")

    def lookup(self, table: str, key: str) -> dict:
        t = self.table(table)
        if key not in t:
            raise MissingStandardError(f"В таблице «{table}» нет записи «{key}»")
        return t[key]

    # ---------- типовые обращения ----------

    def material(self, key: str) -> dict:
        return self.lookup("materials", key)

    def fastener(self, size: str) -> dict:
        return self.lookup("fasteners", size)

    def anchor(self, size: str) -> dict:
        return self.lookup("anchors", size)

    def tube(self, size: str) -> dict:
        sizes = self.table("tubes")["sizes"]
        if size not in sizes:
            raise MissingStandardError(f"Трубы «{size}» нет в сортаменте {self.table('tubes').get('standard', '')}")
        return sizes[size]

    def welds(self) -> dict:
        return self.table("welds")

    def k_min(self, t_max: float) -> float:
        rows = self.welds()["k_min_by_t"]
        for t_lim, k in rows:
            if t_max <= t_lim:
                return k
        return rows[-1][1]

    def fit_limits(self, d: float, hole: str, shaft: str) -> tuple[float, float]:
        """(наименьший диаметр отверстия, наибольший диаметр вала) для посадки."""
        f = self.table("fits")
        lo, hi = f["range"]
        if not (lo < d <= hi):
            raise MissingStandardError(f"Таблица посадок есть только для {lo}..{hi} мм, задано {d}")
        return d + f["holes"][hole][0] / 1000, d + f["shafts"][shaft][1] / 1000

    # ---------- правила пакетов ----------

    def standard_rules(self) -> list:
        return [r for std in self.standards.values() for r in getattr(std, "RULES", [])]

    def describe(self) -> str:
        return ", ".join(f"{n} ({getattr(m, 'NAME', n)})" for n, m in self.standards.items()) or "без стандартов"
