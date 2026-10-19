"""Разница двух состояний проекта (двух коммитов) по одному варианту:
сущности модели по id, геометрия деталей (объёмы, смещения), сводка (масса, габарит, швы, K, замечания).

Вход — две разрешённые модели и их геометрии; откуда они (снимки коммитов) — забота сервера.
"""

from __future__ import annotations

import json
from typing import Any

import build123d as bd

from skelcad.core.model import Project
from skelcad.geom.generator import Geometry

ENTITY_LISTS = {
    "parts": lambda d: d["parts"],
    "welds": lambda d: d["welds"],
    "fasteners": lambda d: d["fasteners"],
    "assumptions": lambda d: d.get("assumptions", []),
    "datums": lambda d: d.get("skeleton", {}).get("datums", []),
    "interfaces": lambda d: d.get("skeleton", {}).get("interfaces", []),
    "envelopes": lambda d: d.get("skeleton", {}).get("envelopes", []),
    "units": lambda d: [{k: v for k, v in u.items() if k not in ("parts", "joints")} for u in d.get("units", [])],
}
DICTS = ("requirements", "derived")


def _short(v: Any, n: int = 80) -> Any:
    s = json.dumps(v, ensure_ascii=False, default=str)
    return v if len(s) <= n else s[: n - 1] + "…"


def _changed_fields(a: dict, b: dict) -> dict:
    out = {}
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out[k] = [_short(a.get(k)), _short(b.get(k))]
    return out


def diff_entities(da: dict, db: dict) -> dict:
    out = {}
    for name, get in ENTITY_LISTS.items():
        la = {e["id"]: e for e in get(da) if isinstance(e, dict) and "id" in e}
        lb = {e["id"]: e for e in get(db) if isinstance(e, dict) and "id" in e}
        added = sorted(set(lb) - set(la))
        removed = sorted(set(la) - set(lb))
        changed = {i: _changed_fields(la[i], lb[i]) for i in sorted(set(la) & set(lb)) if la[i] != lb[i]}
        if added or removed or changed:
            out[name] = {"added": added, "removed": removed, "changed": changed}
    for name in DICTS:
        ch = _changed_fields(da.get(name) or {}, db.get(name) or {})
        if ch:
            out[name] = {"changed": ch}
    return out


def _vol(s: bd.Shape) -> float:
    return float(sum(x.volume for x in s.solids()))


def diff_geometry(ga: Geometry, gb: Geometry, changed_parts: set[str]) -> dict:
    out = {}
    for pid in sorted(set(ga.parts) | set(gb.parts)):
        sa, sb = ga.parts.get(pid), gb.parts.get(pid)
        if sa is None or sb is None:
            s = sa or sb
            out[pid] = {"status": "removed" if sb is None else "added", "volume_mm3": round(_vol(s), 1)}
            continue
        va, vb = _vol(sa), _vol(sb)
        ca, cb = sa.center(bd.CenterOf.MASS), sb.center(bd.CenterOf.MASS)
        rec = {
            "volume_a_mm3": round(va, 1),
            "volume_b_mm3": round(vb, 1),
            "d_volume_mm3": round(vb - va, 1),
            "centroid_shift_mm": round(float((cb - ca).length), 2),
            "size_a": [round(x, 1) for x in sa.bounding_box().size],
            "size_b": [round(x, 1) for x in sb.bounding_box().size],
        }
        if pid in changed_parts or abs(vb - va) > 1 or rec["centroid_shift_mm"] > 0.01:
            try:
                common = sa & sb
                vc = _vol(common) if common else 0.0
                rec["added_mm3"] = round(vb - vc, 1)
                rec["removed_mm3"] = round(va - vc, 1)
            except Exception:  # noqa: BLE001 — булева операция OCCT может не пройти; остальное уже есть
                rec["boolean"] = "не вычислено"
            out[pid] = rec
    return out


def diff_summary(sa: dict, sb: dict) -> dict:
    """Сводки report.json двух состояний -> дельты."""
    out = {}
    for k in ("mass_kg", "weld_length_mm", "parts", "welds", "fasteners", "K_min"):
        a, b = sa.get(k), sb.get(k)
        if a != b:
            out[k] = {
                "a": a,
                "b": b,
                "delta": round(b - a, 3) if isinstance(a, int | float) and isinstance(b, int | float) else None,
            }
    if sa.get("envelope_mm") != sb.get("envelope_mm"):
        out["envelope_mm"] = {"a": sa.get("envelope_mm"), "b": sb.get("envelope_mm")}
    ka, kb = sa.get("K") or {}, sb.get("K") or {}
    kd = {i: {"a": ka.get(i), "b": kb.get(i)} for i in sorted(set(ka) | set(kb)) if ka.get(i) != kb.get(i)}
    if kd:
        out["K"] = kd
    return out


def diff_findings(fa: list[dict], fb: list[dict]) -> dict:
    key = lambda f: (f["level"], f["code"], f["ref"])
    sa, sb = {key(f): f for f in fa}, {key(f): f for f in fb}
    fmt = lambda f: f"[{f['level']}] {f['code']} {f['ref']}: {f['message']}"
    return {
        "added": [fmt(sb[k]) for k in sorted(set(sb) - set(sa)) if k[0] != "info"],
        "removed": [fmt(sa[k]) for k in sorted(set(sa) - set(sb)) if k[0] != "info"],
    }


def diff_all(ma: Project, ga: Geometry, ra: dict, mb: Project, gb: Geometry, rb: dict) -> dict:
    """ra/rb — отчёты (как report.json: summary, findings) для обоих состояний."""
    from skelcad.worker import model_dict

    ents = diff_entities(model_dict(ma), model_dict(mb))
    changed_parts = set((ents.get("parts") or {}).get("changed") or {})
    geom = diff_geometry(ga, gb, changed_parts)
    summ = diff_summary(ra["summary"], rb["summary"])
    finds = diff_findings(ra["findings"], rb["findings"])
    lines = []
    for name, d in ents.items():
        bits = []
        if d.get("added"):
            bits.append("добавлено " + ", ".join(d["added"]))
        if d.get("removed"):
            bits.append("удалено " + ", ".join(d["removed"]))
        if d.get("changed"):
            bits.append(
                "изменено "
                + ", ".join(
                    f"{i} ({', '.join(f)})" if isinstance(f, dict) else f"{i} {f[0]}→{f[1]}"
                    for i, f in d["changed"].items()
                )
            )
        lines.append(f"{name}: " + "; ".join(bits))
    for k, v in summ.items():
        if k == "K":
            lines.append("K: " + ", ".join(f"{i} {x['a']}→{x['b']}" for i, x in v.items()))
        elif k == "envelope_mm":
            lines.append(f"габарит: {v['a']} → {v['b']}")
        else:
            lines.append(f"{k}: {v['a']} → {v['b']}" + (f" ({v['delta']:+})" if v.get("delta") is not None else ""))
    if finds["added"]:
        lines.append("новые замечания: " + " | ".join(finds["added"]))
    if finds["removed"]:
        lines.append("ушли замечания: " + " | ".join(finds["removed"]))
    return {
        "text": "\n".join(lines) or "различий в модели и сводке нет",
        "entities": ents,
        "geometry": geom,
        "deltas": summ,
        "findings": finds,
    }
