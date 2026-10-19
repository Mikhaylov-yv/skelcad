"""Параметры варианта для формы workbench: слияние project.params + variants/<v>.yaml, плоские поля,
правка значений в YAML с сохранением комментариев, черновик (сборка во временном снимке) и сохранение коммитом."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from typing import Any

import yaml

Scalar = int | float | str | bool | None


def _merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def flatten(d: dict, prefix: str = "") -> list[tuple[str, Any]]:
    out = []
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.extend(flatten(v, path))
        else:
            out.append((path, v))
    return out


def _get(d: dict, path: str) -> tuple[bool, Any]:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _set(d: dict, path: str, value: Any) -> None:
    cur = d
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def field_type(v: Any) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int | float):
        return "number"
    if v is None:
        return "string"
    return "string" if isinstance(v, str) else "json"


def fields(project_params: dict, variant_params: dict) -> list[dict]:
    merged = _merge(project_params or {}, variant_params or {})
    out = []
    for path, v in flatten(merged):
        in_variant, _ = _get(variant_params or {}, path)
        out.append({"path": path, "value": v, "type": field_type(v), "source": "variant" if in_variant else "project"})
    return out


# ---------------------------------------------------------------- правка YAML с сохранением комментариев


def _yaml_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int | float):
        return repr(v) if isinstance(v, float) else str(v)
    if v is None:
        return "null"
    s = str(v)
    if re.fullmatch(r"[A-Za-z0-9_./+-]+", s) and not re.fullmatch(r"(true|false|null|yes|no|on|off)", s, re.I):
        return s
    return json.dumps(s, ensure_ascii=False)


def _replace_in_text(text: str, path: list[str], value: Any) -> str | None:
    """Найти `params.<path>` в тексте YAML и заменить скаляр.

    Блочный стиль — по отступам, flow-стиль `{k: v}` — внутри одной строки."""
    lines = text.split("\n")
    keys = ["params", *path]
    indent = -1
    i = 0
    depth = 0
    while i < len(lines) and depth < len(keys):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        cur_indent = len(ln) - len(ln.lstrip(" "))
        if cur_indent <= indent:
            return None  # вышли из блока, не найдя ключ
        m = re.match(r"^(\s*)([A-Za-z0-9_-]+)\s*:(.*)$", ln)
        if m and cur_indent > indent and m.group(2) == keys[depth]:
            rest = m.group(3)
            if depth == len(keys) - 1:
                # скаляр в блочном стиле: `key: value  # комментарий`
                mm = re.match(r"^(\s*)([^#]*?)(\s*#.*)?$", rest)
                before, old, comment = mm.group(1), mm.group(2), mm.group(3) or ""
                if old.startswith("{") or old.startswith("["):
                    return None
                lines[i] = f"{m.group(1)}{m.group(2)}:{before or ' '}{_yaml_scalar(value)}{comment}"
                return "\n".join(lines)
            if rest.strip().startswith("{"):
                # flow-стиль: {thickness: 16, edge: 45} — остаток пути внутри одной строки
                sub = keys[depth + 1 :]
                flow = rest
                pat = r"(\b" + re.escape(sub[-1]) + r"\s*:\s*)([^,}\s][^,}]*)"
                # вложенные flow-словари: ищем ключ после всех промежуточных ключей
                pos = 0
                for k in sub[:-1]:
                    j = re.search(r"\b" + re.escape(k) + r"\s*:\s*\{", flow[pos:])
                    if not j:
                        return None
                    pos += j.end()
                mm = re.search(pat, flow[pos:])
                if not mm:
                    return None
                start = pos + mm.start(2)
                end = pos + mm.end(2)
                new_rest = flow[:start] + _yaml_scalar(value) + flow[end:]
                lines[i] = f"{m.group(1)}{m.group(2)}:{new_rest}"
                return "\n".join(lines)
            indent = cur_indent
            depth += 1
        i += 1
    return None


def apply_params(text: str, changes: dict[str, Any]) -> str:
    """Применить {путь: значение} к тексту variants/<v>.yaml. Комментарии сохраняются, если ключ нашёлся;
    новый ключ — через полную перезапись YAML (без комментариев)."""
    data = yaml.safe_load(text) or {}
    for path, value in changes.items():
        new = _replace_in_text(text, path.split("."), value)
        if new is not None:
            parsed = yaml.safe_load(new) or {}
            ok, got = _get(parsed.get("params") or {}, path)
            if ok and got == value:
                text, data = new, parsed
                continue
        data.setdefault("params", {})
        _set(data["params"], path, value)
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    return text


def coerce(fields_now: list[dict], raw: dict[str, Any]) -> dict[str, Any]:
    """Значения из формы приводятся к типу текущего значения; неизвестный путь — как есть."""
    types = {f["path"]: f["type"] for f in fields_now}
    out = {}
    for path, v in raw.items():
        t = types.get(path)
        if t == "number" and isinstance(v, str):
            v = v.strip().replace(",", ".")
            if v == "":
                raise ValueError(f"«{path}»: нужно число")
            try:
                v = float(v)
            except ValueError:
                raise ValueError(f"«{path}»: нужно число, получено «{raw[path]}»") from None
            v = int(v) if v.is_integer() and "." not in raw[path].strip() else v
        elif t == "number" and isinstance(v, int | float) and not isinstance(v, bool):
            if isinstance(v, float) and v.is_integer():
                v = int(v)
        elif t == "boolean":
            v = v in (True, "true", "1", 1, "on")
        if t == "number" and not isinstance(v, int | float):
            raise ValueError(f"«{path}»: нужно число, получено «{v}»")
        out[path] = v
    return out


# ---------------------------------------------------------------- черновик и сохранение


def draft_id(variant: str, changes: dict[str, Any]) -> str:
    h = hashlib.sha1(json.dumps(changes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
    return f"{variant}-{h}"


def build_draft(srv, project: str, variant: str, changes: dict[str, Any]) -> dict:
    """Снимок HEAD → правка variants/<v>.yaml → сборка варианта во временной папке → разница с HEAD."""
    from skelcad.server.tools import Tools

    ws = srv.workspace
    tools = Tools(srv)
    vfile = next((v["file"] for v in ws.variants(project) if v["id"] == variant), None)
    if not vfile:
        raise LookupError(f"нет варианта «{variant}»")
    did = draft_id(variant, changes)
    root = ws.out_dir / project / "_drafts" / did
    src = root / "src"
    if not (src / "project.yaml").exists():
        if src.exists():
            shutil.rmtree(src)
        ws.checkout_to(project, ws.rev(project, "HEAD"), src)
        text = (src / vfile).read_text(encoding="utf-8")
        (src / vfile).write_text(apply_params(text, changes), encoding="utf-8")
    rep = root / variant / "report.json"
    if not rep.is_file():
        srv.runner.run("build", {"project_dir": str(src), "variants": [variant], "out_dir": str(root), "export": True})
    report = json.loads(rep.read_text(encoding="utf-8"))
    diff = srv.runner.run(
        "diff", {"project_dir_a": str(ws.path(project)), "project_dir_b": str(src), "variant": variant}
    )
    files = report.get("files") or {}
    head_rep = ws.out_dir / project / variant / "report.json"
    head_glb = None
    if head_rep.is_file():
        hf = json.loads(head_rep.read_text(encoding="utf-8")).get("files") or {}
        head_glb = f"/out/{project}/{hf['gltf']}" if hf.get("gltf") else None
    s = report["summary"]
    return {
        "draft": did,
        "variant": variant,
        "changes": changes,
        "file": vfile,
        "summary": s,
        "numbers": {
            "mass_kg": s.get("mass_kg"),
            "k_min": s.get("K_min"),
            "k_min_item": s.get("K_min_item"),
            "errors": (s.get("findings") or {}).get("error", 0),
            "warnings": (s.get("findings") or {}).get("warning", 0),
        },
        "diff": {k: v for k, v in diff.items() if k != "text"} | {"summary": diff.get("text", "")},
        "urls": {
            "glb": f"/out/{project}/_drafts/{did}/{files['gltf']}" if files.get("gltf") else None,
            "head_glb": head_glb,
        },
        "_tools": tools is not None,
    }


def save_params(
    srv, project: str, variant: str, changes: dict[str, Any], message: str, actor, draft: str | None
) -> dict:
    """Записать параметры в variants/<v>.yaml коммитом; если черновик собран — его артефакты становятся текущими."""
    ws = srv.workspace
    vfile = next((v["file"] for v in ws.variants(project) if v["id"] == variant), None)
    if not vfile:
        raise LookupError(f"нет варианта «{variant}»")
    text = ws.read_file(project, vfile)
    new = apply_params(text, changes)
    res = ws.write_files(project, {vfile: new}, message, actor)
    if draft:
        droot = ws.out_dir / project / "_drafts" / draft
        if (droot / variant / "report.json").is_file():
            dst = ws.out_dir / project / variant
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(droot / variant, dst)
    return res
