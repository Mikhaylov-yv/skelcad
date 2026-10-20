"""Словарь сущностей и связей графа и извлечение их из модели: из спецификации проекта (project.yaml,
варианты, замечания конструктора, состояние компоновки) и из комплекта сборки варианта (model.yaml,
report.json, <v>_sketch.json). Чистые функции без базы.

Ссылки — в той же грамматике, что у замечаний, размеров и `data-ref` эскизов: `kind:id[/kind:id]`
(`interface:wall`, `part:base_plate/hole:a00`). Уровень проекта (variant = '') и уровень варианта; связи
уровня варианта могут вести к сущностям уровня проекта (`unit:u1 → interface:wall`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from skelcad.core.model import PlatePart, Project, TubePart, text
from skelcad.core.project import ProjectSpec

KINDS = {  # вид сущности → имя для человека
    "project": "проект",
    "variant": "вариант",
    "standard": "пакет стандартов",
    "load": "нагрузка",
    "constraint": "ограничение",
    "datum": "база",
    "interface": "интерфейс",
    "envelope": "зона",
    "surrounding": "обстановка",
    "assumption": "допущение",
    "review": "замечание конструктора",
    "unit": "узел",
    "part": "деталь",
    "hole": "отверстие",
    "weld": "шов",
    "fastener": "крепёж",
    "material": "материал",
    "item": "позиция каталога",
    "dim": "размер",
    "finding": "замечание",
    "calc": "расчёт",
    "metric": "метрика",
}

RELATIONS = {  # тип связи → как читать «src <связь> dst»
    "contains": "содержит",
    "locates": "привязан к базе",
    "mounts": "крепится к интерфейсу",
    "applies": "приложена через",
    "joins": "соединяет",
    "fastens": "крепит",
    "made_of": "материал",
    "selects": "позиция каталога",
    "uses": "пакет стандартов",
    "annotates": "размер к",
    "checks": "замечание к",
    "reviews": "замечание конструктора к",
    "computes": "расчёт по",
}


@dataclass
class Ent:
    ref: str
    kind: str
    eid: str
    name: str = ""
    text: str = ""  # строка для поиска: id, имя, роль, примечание, теги
    data: dict = field(default_factory=dict)


@dataclass
class Rel:
    src: str
    dst: str
    kind: str
    data: dict = field(default_factory=dict)


def _t(v) -> str:
    return text(v) if v else ""


def _words(*parts) -> str:
    out = []
    for p in parts:
        if p in (None, "", [], {}):
            continue
        out.append(" ".join(map(str, p)) if isinstance(p, list | tuple) else str(p))
    return " ".join(out)


def _num(x: float) -> str:
    return f"{x:g}"


def kind_of(ref: str) -> str:
    """Вид сущности по ссылке: последний `kind:` в цепочке (`part:p/hole:h` → hole)."""
    last = ref.rsplit("/", 1)[-1]
    return last.split(":", 1)[0] if ":" in last else "?"


def norm_ref(ref: str | None, fallback: str) -> str:
    """Ссылка замечания или расчёта: `kind:id` как есть; «assembly», «project», пусто → fallback."""
    r = (ref or "").strip()
    return r if ":" in r else fallback


def _dedup(ents: list[Ent], rels: list[Rel]) -> tuple[list[Ent], list[Rel]]:
    seen_e: dict[str, Ent] = {}
    for e in ents:
        seen_e.setdefault(e.ref, e)
    seen_r: dict[tuple[str, str, str], Rel] = {}
    for r in rels:
        seen_r.setdefault((r.src, r.dst, r.kind), r)
    return list(seen_e.values()), list(seen_r.values())


# ---------------------------------------------------------------- уровень проекта


def extract_project(
    name: str,
    spec: ProjectSpec,
    variants: list[dict],
    reviews: list[dict],
    layout: dict | None = None,
) -> tuple[list[Ent], list[Rel]]:
    """Сущности и связи из project.yaml: проект, пакеты стандартов, нагрузки и ограничения, скелет (базы,
    интерфейсы, зоны, обстановка), допущения, варианты, замечания конструктора."""
    ents: list[Ent] = []
    rels: list[Rel] = []
    root = f"project:{name}"
    ents.append(
        Ent(
            root,
            "project",
            name,
            _t(spec.title),
            _words(name, _t(spec.title), _t(spec.description)),
            {
                "standards": list(spec.requirements.standards),
                "generator": spec.generator,
                "layout": (layout or {}).get("state"),
                "purpose": _t(spec.requirements.purpose),
            },
        )
    )
    for s in spec.requirements.standards:
        ents.append(Ent(f"standard:{s}", "standard", s, s, s))
        rels.append(Rel(root, f"standard:{s}", "uses"))
    loads: dict[str, float] = dict(spec.requirements.loads)
    for k, v in spec.requirements.constraints.items():
        ents.append(Ent(f"constraint:{k}", "constraint", k, k, _words(k, v), {"value": v}))
        rels.append(Rel(root, f"constraint:{k}", "contains"))
    sk = spec.skeleton
    for d in sk.datums:
        ents.append(
            Ent(
                f"datum:{d.id}",
                "datum",
                d.id,
                _t(d.name),
                _words(d.id, _t(d.name), d.kind, d.note, d.tags),
                {"kind": d.kind, "origin": list(d.origin), "direction": list(d.direction or ()), "status": d.status},
            )
        )
        rels.append(Rel(root, f"datum:{d.id}", "contains"))
    for i in sk.interfaces:
        ents.append(
            Ent(
                f"interface:{i.id}",
                "interface",
                i.id,
                _t(i.name),
                _words(i.id, _t(i.name), i.kind, i.note, i.tags, [f"{k}={v}" for k, v in i.params.items()]),
                {
                    "kind": i.kind,
                    "params": dict(i.params),
                    "loads": dict(i.loads),
                    "datum": i.datum,
                    "status": i.status,
                },
            )
        )
        rels.append(Rel(root, f"interface:{i.id}", "contains"))
        if i.datum:
            rels.append(Rel(f"interface:{i.id}", f"datum:{i.datum}", "locates"))
        for k, v in i.loads.items():
            loads.setdefault(k, v)
            rels.append(Rel(f"load:{k}", f"interface:{i.id}", "applies", {"value": v}))
    for k, v in loads.items():
        ents.append(Ent(f"load:{k}", "load", k, k, _words(k, v), {"value": v}))
        rels.append(Rel(root, f"load:{k}", "contains"))
    for e in sk.envelopes:
        ents.append(
            Ent(
                f"envelope:{e.id}",
                "envelope",
                e.id,
                _t(e.name),
                _words(e.id, _t(e.name), e.kind, e.note, e.tags),
                {"kind": e.kind, "min": list(e.min), "max": list(e.max), "status": e.status},
            )
        )
        rels.append(Rel(root, f"envelope:{e.id}", "contains"))
    for b in sk.surroundings:
        lo, hi = b.bbox()
        ents.append(
            Ent(
                f"surrounding:{b.id}",
                "surrounding",
                b.id,
                _t(b.name),
                _words(b.id, _t(b.name), b.kind, b.role, b.material, b.note, b.tags),
                {
                    "kind": b.kind,
                    "role": b.role,
                    "material": b.material,
                    "bbox": [list(lo), list(hi)],
                    "status": b.status,
                },
            )
        )
        rels.append(Rel(root, f"surrounding:{b.id}", "contains"))
    for a in spec.assumptions:
        ents.append(Ent(f"assumption:{a.id}", "assumption", a.id, _t(a.text)[:80], _words(a.id, a.topic, _t(a.text))))
        rels.append(Rel(root, f"assumption:{a.id}", "contains"))
    for v in variants:
        vid = v["id"]
        ents.append(Ent(f"variant:{vid}", "variant", vid, _t(v.get("title")), _words(vid, _t(v.get("title")))))
        rels.append(Rel(root, f"variant:{vid}", "contains"))
    for r in reviews:
        rid = str(r["id"])
        ents.append(
            Ent(
                f"review:{rid}",
                "review",
                rid,
                str(r.get("text", ""))[:80],
                _words(rid, r.get("text"), r.get("status"), r.get("author"), r.get("answer")),
                {k: r.get(k) for k in ("status", "author", "variant", "part", "point", "created") if r.get(k)},
            )
        )
        rels.append(Rel(root, f"review:{rid}", "contains"))
        part = r.get("part")
        if part:
            rels.append(Rel(f"review:{rid}", part if ":" in str(part) else f"part:{part}", "reviews"))
        if r.get("variant"):
            rels.append(Rel(f"review:{rid}", f"variant:{r['variant']}", "reviews"))
    return _dedup(ents, rels)


# ---------------------------------------------------------------- уровень варианта


def extract_variant(
    variant: str,
    m: Project,
    report: dict | None = None,
    sketch: dict | None = None,
    skip_assumptions: set[str] | frozenset[str] = frozenset(),
) -> tuple[list[Ent], list[Rel]]:
    """Сущности и связи из собранной модели варианта: узлы, детали, отверстия, швы, крепёж, материалы и
    позиции каталога; из отчёта — замечания, расчёты, метрики; из эскиза — размеры."""
    ents: list[Ent] = []
    rels: list[Rel] = []
    root = f"variant:{variant}"
    report = report or {}
    masses = {p.get("id"): p.get("mass_kg") for p in report.get("parts") or []}
    for u in m.units:
        uref = f"unit:{u.id}"
        ents.append(
            Ent(
                uref,
                "unit",
                u.id,
                _t(u.name),
                _words(u.id, _t(u.name), u.note, u.tags),
                {"material": u.material, "interfaces": list(u.interfaces), "derived": dict(u.derived)},
            )
        )
        rels.append(Rel(root, uref, "contains"))
        for iid in u.interfaces:
            rels.append(Rel(uref, f"interface:{iid}", "mounts"))
        for p in u.parts:
            pref = f"part:{p.id}"
            data: dict = {"kind": p.kind, "role": p.role, "material": p.material, "mass_kg": masses.get(p.id)}
            if isinstance(p, PlatePart):
                data |= {"thickness": p.thickness, "holes": len(p.holes)}
                holes = list(p.holes)
            else:
                data |= {"tube_size": p.tube_size, "od": p.od, "wall": p.wall, "length": p.length}
                holes = [p.bore] if p.bore else []
            ents.append(
                Ent(
                    pref,
                    "part",
                    p.id,
                    _t(p.name),
                    _words(p.id, _t(p.name), p.role, p.kind, p.material, p.note, p.tags),
                    data,
                )
            )
            rels.append(Rel(uref, pref, "contains"))
            if p.material:
                mref = f"material:{p.material}"
                ents.append(Ent(mref, "material", p.material, p.material, p.material))
                rels.append(Rel(pref, mref, "made_of"))
            if isinstance(p, TubePart):
                iref = f"item:tube/{p.tube_size}"
                ents.append(
                    Ent(
                        iref,
                        "item",
                        f"tube/{p.tube_size}",
                        f"труба {p.tube_size}",
                        _words("труба", p.tube_size),
                        {"type": "tube", "size": p.tube_size},
                    )
                )
                rels.append(Rel(pref, iref, "selects"))
            for h in holes:
                href = f"{pref}/hole:{h.id}"
                hname = f"{h.purpose} Ø{_num(h.diameter)}" + (f" {h.tolerance}" if h.tolerance else "")
                ents.append(
                    Ent(
                        href,
                        "hole",
                        h.id,
                        hname,
                        _words(h.id, h.purpose, f"Ø{_num(h.diameter)}", h.tolerance, h.note),
                        {"purpose": h.purpose, "diameter": h.diameter, "tolerance": h.tolerance},
                    )
                )
                rels.append(Rel(pref, href, "contains"))
        for w in u.welds:
            wref = f"weld:{w.id}"
            ents.append(
                Ent(
                    wref,
                    "weld",
                    w.id,
                    f"{w.weld_type} {_num(w.leg)}",
                    _words(w.id, w.weld_type, f"катет {_num(w.leg)}", w.note, w.tags),
                    {"weld_type": w.weld_type, "leg": w.leg, "length": round(w.length, 1), "parts": list(w.parts)},
                )
            )
            rels.append(Rel(uref, wref, "contains"))
            for pid in w.parts:
                rels.append(Rel(wref, f"part:{pid}", "joins", {"leg": w.leg}))
        for f in u.fasteners:
            fref = f"fastener:{f.id}"
            ents.append(
                Ent(
                    fref,
                    "fastener",
                    f.id,
                    f"{f.fastener_type} {f.size}",
                    _words(f.id, f.fastener_type, f.size, f.note, f.tags),
                    {
                        "type": f.fastener_type,
                        "size": f.size,
                        "clamp_depth": f.clamp_depth,
                        "part": f.part,
                        "hole": f.hole,
                    },
                )
            )
            rels.append(Rel(uref, fref, "contains"))
            rels.append(Rel(fref, f"part:{f.part}", "fastens"))
            rels.append(Rel(fref, f"part:{f.part}/hole:{f.hole}", "fastens"))
            iref = f"item:{f.fastener_type}/{f.size}"
            ents.append(
                Ent(
                    iref,
                    "item",
                    f"{f.fastener_type}/{f.size}",
                    f"{f.fastener_type} {f.size}",
                    _words(f.fastener_type, f.size),
                    {"type": f.fastener_type, "size": f.size},
                )
            )
            rels.append(Rel(fref, iref, "selects"))
    for a in m.assumptions:
        if a.id in skip_assumptions:
            continue
        ents.append(Ent(f"assumption:{a.id}", "assumption", a.id, _t(a.text)[:80], _words(a.id, a.topic, _t(a.text))))
        rels.append(Rel(root, f"assumption:{a.id}", "contains"))
    for n, f in enumerate(report.get("findings") or [], start=1):
        fref = f"finding:{n}"
        ents.append(
            Ent(
                fref,
                "finding",
                str(n),
                f"{f.get('code')} {f.get('level')}",
                _words(f.get("code"), f.get("level"), f.get("message"), f.get("source"), f.get("ref")),
                {k: f.get(k) for k in ("level", "code", "message", "source", "ref")},
            )
        )
        rels.append(Rel(fref, norm_ref(f.get("ref"), root), "checks"))
    for c in report.get("calc") or []:
        cref = f"calc:{c.get('id')}"
        ents.append(
            Ent(
                cref,
                "calc",
                str(c.get("id")),
                str(c.get("title", "")),
                _words(c.get("id"), c.get("title"), c.get("formula")),
                {"K": c.get("K"), "K_req": c.get("K_req"), "ok": c.get("ok"), "unit": c.get("unit")},
            )
        )
        rels.append(Rel(cref, norm_ref(c.get("ref"), root), "computes"))
    for mt in report.get("metrics") or []:
        mref = f"metric:{mt.get('id')}"
        ents.append(
            Ent(
                mref,
                "metric",
                str(mt.get("id")),
                str(mt.get("title", "")),
                _words(mt.get("id"), mt.get("title"), mt.get("value")),
                {"value": mt.get("value")},
            )
        )
        rels.append(Rel(root, mref, "contains"))
    for d in (sketch or {}).get("dims") or []:
        dref = f"dim:{d.get('id')}"
        ents.append(
            Ent(
                dref,
                "dim",
                str(d.get("id")),
                str(d.get("text", "")),
                _words(d.get("id"), d.get("text"), d.get("axis"), d.get("kind")),
                {
                    "text": d.get("text"),
                    "axis": d.get("axis"),
                    "value": d.get("value"),
                    "view": d.get("view"),
                    "kind": d.get("kind"),
                },
            )
        )
        for ref in d.get("refs") or []:
            rels.append(Rel(dref, ref, "annotates"))
    return _dedup(ents, rels)
