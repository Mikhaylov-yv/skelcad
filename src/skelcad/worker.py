"""Рабочий процесс: исполняет код проекта (генератор, плагины, OCCT) отдельно от сервера.

Запрос — JSON на stdin: {"op": "query|build|check|compare|measure|render|layout|diff", "args": {...}}.
Ответ — JSON на stdout: {"ok": true, "result": ...} или {"ok": false, "error": "...", "traceback": "..."}.
Всё, что печатает код проекта, уходит в stderr, чтобы не портить ответ.

Запускается сервером (`skelcad.server.jobs`) с лимитами ресурсов; в M1 — подпроцесс
`python -I -m skelcad.worker --once`, в контейнере-воркере — цикл по файловой очереди.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------ срезы модели


def _select(data: Any, path: str) -> Any:
    """Срез по пути: `units[0].parts`, `parts[id=cheek_L].holes`, `skeleton.interfaces`."""
    cur = data
    for seg in [s for s in path.replace("/", ".").split(".") if s]:
        name, _, rest = seg.partition("[")
        if name:
            if isinstance(cur, dict):
                if name not in cur:
                    raise KeyError(f"нет ключа «{name}»; есть: {', '.join(list(cur)[:30])}")
                cur = cur[name]
            else:
                raise KeyError(f"«{name}»: ожидался словарь, а здесь {type(cur).__name__}")
        while rest:
            sel, _, rest = rest.partition("]")
            rest = rest.lstrip("[")
            if not isinstance(cur, list):
                raise KeyError(f"[{sel}]: ожидался список, а здесь {type(cur).__name__}")
            if "=" in sel:
                k, v = sel.split("=", 1)
                hit = [x for x in cur if isinstance(x, dict) and str(x.get(k)) == v]
                if not hit:
                    raise KeyError(
                        f"нет элемента с {k}={v}; есть {k}: {[x.get(k) for x in cur if isinstance(x, dict)]}"
                    )
                cur = hit[0] if len(hit) == 1 else hit
            else:
                cur = cur[int(sel)]
    return cur


def model_dict(project) -> dict:
    """Разрешённая модель как словарь с виртуальными ключами parts / welds / fasteners / summary."""
    d = project.model_dump(mode="json", exclude_defaults=True)
    d["parts"] = [p.model_dump(mode="json", exclude_defaults=True) for p in project.parts]
    d["welds"] = [w.model_dump(mode="json", exclude_defaults=True) for w in project.welds]
    d["fasteners"] = [f.model_dump(mode="json", exclude_defaults=True) for f in project.fasteners]
    d["summary"] = {
        "units": [u.id for u in project.units],
        "parts": [p.id for p in project.parts],
        "welds": len(project.welds),
        "fasteners": len(project.fasteners),
        "assumptions": len(project.assumptions),
        "derived": project.derived,
    }
    return d


# ------------------------------------------------------------------ операции


def _project_dir(args: dict):
    from skelcad.core.project import ProjectDir

    return ProjectDir(Path(args["project_dir"]))


def _variants(pd, names) -> list[str | None]:
    if names:
        return list(names)
    vs = [v.id for v in pd.variants()]
    return vs or [None]


def op_query(args: dict) -> Any:
    pd = _project_dir(args)
    m = pd.resolve(args.get("variant"))
    d = model_dict(m)
    path = args.get("path") or ""
    return _select(d, path) if path else d["summary"] | {"title": d.get("title"), "variant": d.get("variant")}


def op_build(args: dict) -> list[dict]:
    from skelcad.pipeline import build_variant

    pd = _project_dir(args)
    out_root = Path(args["out_dir"])
    return [
        build_variant(pd, v, out_root, export=args.get("export", True), verbose=False)
        for v in _variants(pd, args.get("variants"))
    ]


def op_check(args: dict) -> dict:
    from skelcad.geom.generator import generate
    from skelcad.pipeline import analyse

    pd = _project_dir(args)
    scope = args.get("scope") or "all"
    out = {}
    for v in _variants(pd, args.get("variants")):
        m = pd.resolve(v)
        g = generate(m, pd.ctx)
        findings, items, metrics = analyse(pd, m, g)
        if scope != "all":
            keep = {"rules": "rules", "geometry": "checks", "calc": "calc"}[scope]
            findings = [f for f in findings if f.source.split(".")[0] == keep]
            if scope != "calc":
                items = []
        out[m.variant or m.id] = {
            "findings": [f.model_dump() for f in findings],
            "calc": [i.model_dump() | {"ok": i.ok} for i in items],
            "metrics": [x.model_dump() for x in metrics],
        }
    return out


def op_compare(args: dict) -> dict:
    from skelcad.compare import write_compare
    from skelcad.pipeline import build_variant

    pd = _project_dir(args)
    out_root = Path(args["out_dir"])
    reports = []
    for v in _variants(pd, args.get("variants")):
        rep = out_root / (v or pd.spec.id) / "report.json"
        if rep.exists() and not args.get("rebuild"):
            reports.append(json.loads(rep.read_text(encoding="utf-8")))
        else:
            reports.append(build_variant(pd, v, out_root, export=True, verbose=False))
    page = write_compare(reports, out_root)
    return {"page": str(page), "reports": reports}


def _resolved(args: dict):
    from skelcad.geom.generator import generate

    pd = _project_dir(args)
    m = pd.resolve(args.get("variant"))
    return pd, m, generate(m, pd.ctx)


def op_measure(args: dict) -> Any:
    from skelcad.measure import measure

    pd, m, g = _resolved(args)
    return measure(m, g, pd.ctx, args.get("op_name") or "list", args.get("op_args") or {})


def op_render(args: dict) -> Any:
    from skelcad.render import render

    pd, m, g = _resolved(args)
    out = Path(args["out_dir"]) / (m.variant or m.id)
    return render(m, g, args.get("view") or "iso", out, args.get("highlight"), int(args.get("width") or 1200))


def op_layout(args: dict) -> dict:
    """Компоновочный эскиз по project.yaml; детали собранного варианта — тонкой линией, если генератор работает.
    Сломанный генератор или плагин компоновку не отменяет: она строится по спецификации, причина — в notes."""
    from skelcad.core.project import ProjectDir, base_project, read_spec, read_variant
    from skelcad.geom.layout import write_layout

    root = Path(args["project_dir"])
    variant = args.get("variant") or None
    notes: list[str] = []
    pd = None
    try:
        pd = ProjectDir(root)
    except Exception as e:  # noqa: BLE001 — код проекта не загрузился: компоновка по спецификации
        notes.append(f"код проекта не загрузился: {type(e).__name__}: {e}")
    spec = pd.spec if pd else read_spec(root)
    m = g = None
    if pd is not None and pd.generator is not None:
        try:
            m = pd.resolve(variant)
        except Exception as e:  # noqa: BLE001
            notes.append(f"генератор не выполнился: {type(e).__name__}: {e}")
    if m is None:
        m = base_project(spec, read_variant(root, variant) if variant else None)
    if m.parts and pd is not None:
        try:
            from skelcad.geom.generator import generate

            g = generate(m, pd.ctx)
        except Exception as e:  # noqa: BLE001
            notes.append(f"геометрия не построена: {type(e).__name__}: {e}")
    res = write_layout(m, g, Path(args["out_dir"]), m.variant or m.id, args.get("views"), args.get("png", True))
    res["notes"] = notes + res["notes"]
    return res


def op_sketch(args: dict) -> dict:
    """Эскиз варианта с размерами по текущему состоянию проекта (без полной сборки)."""
    from skelcad.geom.sketch import write_sketch

    pd, m, g = _resolved(args)
    return write_sketch(m, g, Path(args["out_dir"]), m.variant or m.id, args.get("views"), args.get("png", True))


def _report_light(pd, m, g) -> dict:
    """Сводка и замечания как в report.json, без экспорта (для diff)."""
    from skelcad.pipeline import analyse

    findings, calc_items, _ = analyse(pd, m, g)
    try:
        mass = round(sum(g.masses(m, pd.ctx).values()), 2)
    except Exception:  # noqa: BLE001 — нет таблицы материалов
        mass = None
    bb = g.assembly(m, with_purchased=False).bounding_box()
    return {
        "summary": {
            "mass_kg": mass,
            "envelope_mm": [round(bb.size.X), round(bb.size.Y), round(bb.size.Z)],
            "parts": len(m.parts),
            "welds": len(m.welds),
            "fasteners": len(m.fasteners),
            "weld_length_mm": round(sum(w.length for w in m.welds)),
            "K": {i.id: round(i.K, 3) for i in calc_items},
            "K_min": round(min((i.K for i in calc_items), default=0), 3) if calc_items else None,
        },
        "findings": [f.model_dump() for f in findings],
    }


def op_diff(args: dict) -> Any:
    from skelcad.diff import diff_all

    a = dict(args, project_dir=args["project_dir_a"])
    b = dict(args, project_dir=args["project_dir_b"])
    pda, ma, ga = _resolved(a)
    pdb, mb, gb = _resolved(b)
    return diff_all(ma, ga, _report_light(pda, ma, ga), mb, gb, _report_light(pdb, mb, gb))


OPS = {
    "query": op_query,
    "diff": op_diff,
    "build": op_build,
    "check": op_check,
    "compare": op_compare,
    "measure": op_measure,
    "render": op_render,
    "layout": op_layout,
    "sketch": op_sketch,
}


def handle(request: dict) -> dict:
    op = request.get("op")
    if op not in OPS:
        return {"ok": False, "error": f"неизвестная операция «{op}»; есть: {sorted(OPS)}"}
    t0 = time.monotonic()
    try:
        result = OPS[op](request.get("args") or {})
        return {"ok": True, "result": result, "seconds": round(time.monotonic() - t0, 2)}
    except Exception as e:  # noqa: BLE001 — любая ошибка кода проекта должна вернуться агенту текстом
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(limit=12),
            "seconds": round(time.monotonic() - t0, 2),
        }


# ------------------------------------------------------------------ лимиты и запуск

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def install_guard(allow_write: list[Path], deny_write: list[Path] = ()) -> None:
    """Audit-hook: запись файлов только в разрешённые папки (out/, временные, __pycache__);
    запуск процессов и сетевые соединения запрещены. Исключение — PermissionError (OSError):
    importlib молча пропускает невозможность записать .pyc."""
    allowed = [p.resolve() for p in allow_write] + [Path(tempfile.gettempdir()).resolve()]
    denied = [p.resolve() for p in deny_write]

    def ok(path: str) -> bool:
        try:
            rp = Path(path).resolve()
        except (OSError, RuntimeError):
            return False
        if "__pycache__" in rp.parts:
            return True
        if any(rp == d or d in rp.parents for d in denied):
            return False
        return any(rp == a or a in rp.parents for a in allowed)

    def hook(event: str, args: tuple) -> None:
        if event == "open":
            path, mode, flags = args
            writing = (mode and any(c in str(mode) for c in "wax+")) or (not mode and flags & _WRITE_FLAGS)
            if writing and isinstance(path, (str, bytes, os.PathLike)) and not ok(os.fsdecode(path)):
                raise PermissionError(
                    f"воркер: запись в «{os.fsdecode(path)}» запрещена (только out/ и временные файлы)"
                )
        elif event in ("os.remove", "os.rename", "os.unlink", "os.rmdir", "os.mkdir", "shutil.rmtree"):
            path = args[0]
            if isinstance(path, (str, bytes, os.PathLike)) and not ok(os.fsdecode(path)):
                raise PermissionError(f"воркер: изменение «{os.fsdecode(path)}» запрещено")
        elif event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.fork", "os.exec"):
            raise PermissionError("воркер: запуск процессов из кода проекта запрещён")
        elif event == "socket.connect":
            raise PermissionError("воркер: сетевые соединения из кода проекта запрещены")

    sys.addaudithook(hook)


def apply_limits(cpu_s: int | None, mem_mb: int | None) -> None:
    """Лимиты на процесс (Linux): CPU-время и адресное пространство."""
    try:
        import resource
    except ImportError:  # не Linux
        return
    if cpu_s:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
    if mem_mb:
        b = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (b, b))


def run_once(stdin=None, stdout=None) -> int:
    """Один запрос из stdin -> один ответ в stdout. stdout на время работы перенаправлен в stderr."""
    stdin = stdin or sys.stdin
    real_out = stdout or sys.stdout
    request = json.load(stdin)
    sys.stdout = sys.stderr
    try:
        args = request.get("args") or {}
        if request.get("guard", True):
            install_guard(
                [Path(args["out_dir"])] if args.get("out_dir") else [],
                [Path(args["project_dir"])] if args.get("project_dir") else [],
            )
        response = handle(request)
    finally:
        sys.stdout = real_out
    real_out.write(json.dumps(response, ensure_ascii=False, default=str))
    real_out.flush()
    return 0 if response.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="skelcad worker", description="рабочий процесс SkelCAD")
    ap.add_argument("--once", action="store_true", help="один запрос из stdin, ответ в stdout")
    ap.add_argument("--cpu", type=int, default=int(os.environ.get("SKELCAD_LIMIT_CPU_S", "0")) or None)
    ap.add_argument("--mem", type=int, default=int(os.environ.get("SKELCAD_LIMIT_MEM_MB", "0")) or None)
    ap.add_argument("--queue", help="папка файловой очереди (цикл воркера)")
    args = ap.parse_args(argv)
    if args.once:
        apply_limits(args.cpu, args.mem)
        return run_once()
    if args.queue:
        from skelcad.server.jobs import queue_loop

        return queue_loop(Path(args.queue), cpu_s=args.cpu, mem_mb=args.mem)
    ap.error("укажите --once или --queue")
    return 2


if __name__ == "__main__":
    sys.exit(main())
