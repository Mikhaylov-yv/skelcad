"""CLI: skelcad build | check | compare | schema | check-env | standards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _project(path: str):
    from skelcad.core.project import ProjectDir

    return ProjectDir(Path(path))


def _variants(pd, names: list[str] | None) -> list[str | None]:
    if names:
        return names
    vs = [v.id for v in pd.variants()]
    return vs or [None]


def cmd_build(args) -> int:
    from skelcad.pipeline import build_variant

    pd = _project(args.project)
    out = Path(args.out) if args.out else pd.root / "out"
    reports = [build_variant(pd, v, out, export=not args.no_export, verbose=True) for v in _variants(pd, args.variant)]
    if len(reports) > 1 or args.compare:
        from skelcad.compare import write_compare

        print(f"Сравнение: {write_compare(reports, out)}")
    return 1 if any(r["summary"]["findings"]["error"] for r in reports) else 0


def cmd_check(args) -> int:
    """Правила, проверки и расчёт без экспорта артефактов; код возврата 1 при ошибках."""
    from skelcad.core.findings import LEVEL_RU
    from skelcad.geom.generator import generate
    from skelcad.pipeline import analyse

    pd = _project(args.project)
    rc = 0
    for v in _variants(pd, args.variant):
        m = pd.resolve(v)
        g = generate(m, pd.ctx)
        findings, items, _ = analyse(pd, m, g)
        print(f"== {m.variant or m.id}")
        for f in findings:
            if args.all or f.level != "info":
                print(f"   [{LEVEL_RU[f.level]}] {f.code} {f.ref}: {f.message}")
        for it in items:
            print(f"   K {it.id} = {it.K:.2f} (треб. {it.K_req:g}) {'ok' if it.ok else 'НЕТ'}")
        rc |= int(any(f.level == "error" for f in findings))
    return rc


def cmd_schema(args) -> int:
    from skelcad.core.model import Project
    from skelcad.core.project import ProjectSpec, VariantSpec

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, model in (("project-spec", ProjectSpec), ("variant-spec", VariantSpec), ("model", Project)):
        (out / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{out / f'{name}.schema.json'}")
    return 0


def cmd_standards(args) -> int:
    from skelcad.context import discover_standards

    found = discover_standards()
    if not found:
        print("пакеты стандартов не установлены")
    for name, mod in found.items():
        tables = sorted(p.stem for p in Path(mod.DATA_DIR).glob("*.yaml"))
        print(
            f"{name}: {getattr(mod, 'NAME', '')}; таблицы: {', '.join(tables)}; "
            f"правил: {len(getattr(mod, 'RULES', []))}"
        )
    return 0


def cmd_check_env(args) -> int:
    """Куб -> STEP и glTF, обратное чтение файлов."""
    import build123d as bd
    import trimesh

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"build123d {bd.__version__}, trimesh {trimesh.__version__}")
    cube = bd.Box(10, 10, 10)
    step, glb = out_dir / "cube.step", out_dir / "cube.glb"
    bd.export_step(cube, step)
    bd.export_gltf(cube, glb, binary=True)
    vol = bd.import_step(step).volume
    assert abs(vol - 1000) < 1e-6, f"объём STEP {vol} != 1000"
    print(f"STEP ok: {step.name}, объём {vol:.3f} мм³")
    scene = trimesh.load(glb)
    assert all(abs(e - 0.01) < 1e-6 for e in scene.extents), f"габарит glTF {scene.extents}"
    mesh = scene.to_geometry()
    mesh.merge_vertices()
    assert mesh.is_watertight, "сетка glTF не замкнута"
    print(f"glTF ok: {glb.name}, габарит {scene.extents} м, сетка замкнута")
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="skelcad", description="SkelCAD — среда совместного конструирования")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="построить вариант(ы): модель, геометрия, проверки, артефакты, отчёт")
    b.add_argument("project", help="папка проекта с project.yaml")
    b.add_argument("-v", "--variant", action="append", help="имя варианта (по умолчанию все)")
    b.add_argument("-o", "--out", help="папка результатов (по умолчанию <project>/out)")
    b.add_argument("--no-export", action="store_true", help="без STEP/glTF/STL/SVG")
    b.add_argument("--compare", action="store_true", help="страница сравнения даже для одного варианта")
    b.set_defaults(fn=cmd_build)

    c = sub.add_parser("check", help="правила, проверки и расчёт без экспорта")
    c.add_argument("project")
    c.add_argument("-v", "--variant", action="append")
    c.add_argument("--all", action="store_true", help="показывать и информационные замечания")
    c.set_defaults(fn=cmd_check)

    s = sub.add_parser("schema", help="выгрузить JSON Schema спецификации проекта, варианта и модели")
    s.add_argument("-o", "--out", default="docs/schema")
    s.set_defaults(fn=cmd_schema)

    st = sub.add_parser("standards", help="установленные пакеты стандартов")
    st.set_defaults(fn=cmd_standards)

    e = sub.add_parser("check-env", help="проверка среды (куб -> STEP, glTF)")
    e.add_argument("-o", "--out", default=".tmp/envcheck")
    e.set_defaults(fn=cmd_check_env)

    args = ap.parse_args(argv)
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
