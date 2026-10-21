"""Правка компоновки с эскиза (M2.3 шаг 2, D22): положение и размеры сущностей скелета и обстановки меняются в
тексте project.yaml на месте (комментарии и порядок строк сохраняются), коммит от имени конструктора.

Поля по видам сущностей: datum — origin; interface — body.center / body.diameter / body.length; envelope — min /
max; surrounding plane — origin / extent / thickness, box — min / max, cylinder — center / diameter / length.
Направления (direction, normal, axis) с эскиза не меняются. Размер с эскиза (dim из <prefix>_layout.json)
правится числом: вторая сущность размера сдвигается вдоль его оси так, чтобы расстояние стало заданным.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from skelcad.core.model import Skeleton
from skelcad.server.workspace import Actor, Workspace

GROUPS = {"datum": "datums", "interface": "interfaces", "envelope": "envelopes", "surrounding": "surroundings"}
# тип поля: vec — три числа; pos — число > 0; nonneg — число >= 0
FIELDS: dict[str, dict[str, str]] = {
    "datum": {"origin": "vec"},
    "interface": {"body.center": "vec", "body.diameter": "pos", "body.length": "pos"},
    "envelope": {"min": "vec", "max": "vec"},
    "plane": {"origin": "vec", "extent": "pos", "thickness": "nonneg"},
    "box": {"min": "vec", "max": "vec"},
    "cylinder": {"center": "vec", "diameter": "pos", "length": "pos"},
}
# по какому полю сущность сдвигается (правка размера числом)
POSITION: dict[str, list[str]] = {
    "datum": ["origin"],
    "interface": ["body.center"],
    "envelope": ["min", "max"],
    "plane": ["origin"],
    "box": ["min", "max"],
    "cylinder": ["center"],
}
AXES = "XYZ"


class LayoutEditError(ValueError):
    pass


# ---------------------------------------------------------------- значения


def _num(v: Any, what: str) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float | str):
        raise LayoutEditError(f"{what}: нужно число, получено «{v}»")
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise LayoutEditError(f"{what}: нужно число, получено «{v}»") from None
    if x != x or x in (float("inf"), float("-inf")):
        raise LayoutEditError(f"{what}: нужно число")
    return round(x, 2)


def coerce(kind: str, field: str, value: Any) -> Any:
    """Значение с эскиза или из формы → число или три числа; проверка знака."""
    ftype = FIELDS[kind].get(field)
    if ftype is None:
        allowed = ", ".join(FIELDS[kind])
        raise LayoutEditError(f"поле «{field}» у «{kind}» с эскиза не правится; можно: {allowed}")
    if ftype == "vec":
        if not isinstance(value, list | tuple) or len(value) != 3:
            raise LayoutEditError(f"{field}: нужны три числа [x, y, z]")
        return [_num(c, f"{field}[{i}]") for i, c in enumerate(value)]
    x = _num(value, field)
    if ftype == "pos" and x <= 0:
        raise LayoutEditError(f"{field}: должно быть больше нуля")
    if ftype == "nonneg" and x < 0:
        raise LayoutEditError(f"{field}: не может быть отрицательным")
    return x


def fmt(v: Any) -> str:
    """Число для YAML и подписей: целое без дроби, иначе до двух знаков."""
    if isinstance(v, list | tuple):
        return "[" + ", ".join(fmt(c) for c in v) + "]"
    x = float(v)
    return str(int(round(x))) if abs(x - round(x)) < 1e-9 else f"{x:.2f}".rstrip("0").rstrip(".")


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, list | tuple) and isinstance(b, list | tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return a == b


# ---------------------------------------------------------------- сущности спецификации


def parse_ref(ref: str) -> tuple[str, str]:
    group, _, eid = (ref or "").partition(":")
    if group not in GROUPS or not eid:
        raise LayoutEditError(
            f"ссылка «{ref}»: ожидалось datum:<id> | interface:<id> | envelope:<id> | surrounding:<id>"
        )
    return group, eid


def find_entity(spec: dict, ref: str) -> tuple[str, dict]:
    """(вид сущности для FIELDS, словарь сущности) по ссылке; вид обстановки — её kind."""
    group, eid = parse_ref(ref)
    items = (spec.get("skeleton") or {}).get(GROUPS[group]) or []
    item = next((i for i in items if isinstance(i, dict) and i.get("id") == eid), None)
    if item is None:
        have = ", ".join(str(i.get("id")) for i in items if isinstance(i, dict))
        raise LayoutEditError(f"нет «{ref}» в скелете; есть: {have or 'ничего'}")
    kind = group
    if group == "surrounding":
        kind = str(item.get("kind") or "")
        if kind not in FIELDS:
            raise LayoutEditError(f"«{ref}»: тело обстановки вида «{kind}» с эскиза не правится")
    if group == "interface" and not isinstance(item.get("body"), dict):
        raise LayoutEditError(f"«{ref}»: у интерфейса нет опорного тела (body); положение задаёт его база datum")
    return kind, item


def _get(d: Any, path: list[str]) -> tuple[bool, Any]:
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return False, None
        cur = cur[p]
    return True, cur


def _set(d: dict, path: list[str], value: Any) -> None:
    cur = d
    for p in path[:-1]:
        cur = cur.setdefault(p, {})
    cur[path[-1]] = value


# ---------------------------------------------------------------- правка текста YAML на месте

_KEY = r"[A-Za-z0-9_-]+"


def _indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def _meaningful(ln: str) -> bool:
    return bool(ln.strip()) and not ln.lstrip().startswith("#")


def _find_key(lines: list[str], start: int, end: int, key: str, parent_indent: int) -> int | None:
    """Строка `key:` с отступом > parent_indent между start и end; первая строка с отступом <= parent_indent
    (после start) закрывает поиск."""
    first = True
    for i in range(start, end):
        ln = lines[i]
        if not _meaningful(ln):
            continue
        ind = _indent(ln)
        if ind <= parent_indent and not first:
            return None
        first = False
        m = re.match(rf"^\s*({_KEY})\s*:(.*)$", ln)
        if m and m.group(1) == key and ind > parent_indent:
            return i
    return None


def _block_end(lines: list[str], start: int, indent: int) -> int:
    """Конец блока, начатого строкой start с отступом indent: первая значимая строка с отступом <= indent."""
    for i in range(start + 1, len(lines)):
        if _meaningful(lines[i]) and _indent(lines[i]) <= indent:
            return i
    return len(lines)


def _items(lines: list[str], start: int, end: int) -> list[tuple[int, int]]:
    """Элементы списка `- …` между start и end: (первая строка, строка после последней)."""
    out = []
    dash_indent = None
    i = start
    while i < end:
        ln = lines[i]
        if _meaningful(ln) and re.match(r"^\s*-(\s|$)", ln):
            ind = _indent(ln)
            if dash_indent is None:
                dash_indent = ind
            if ind == dash_indent:
                j = i + 1
                while j < end and not (_meaningful(lines[j]) and _indent(lines[j]) <= dash_indent):
                    j += 1
                out.append((i, j))
                i = j
                continue
        i += 1
    return out


def _item_has_id(text: str, eid: str) -> bool:
    return re.search(rf"(^|[\s{{,])id\s*:\s*[\"']?{re.escape(eid)}[\"']?\s*(?=[,}}\s#]|$)", text, re.M) is not None


def _replace_flow(text: str, path: list[str], value: Any) -> str | None:
    """Внутри flow-записи `{…}`: путь ключей → заменить значение (скаляр или [a, b, c])."""
    pos = 0
    for k in path[:-1]:
        m = re.search(rf"(?<![A-Za-z0-9_-]){re.escape(k)}\s*:\s*\{{", text[pos:])
        if not m:
            return None
        pos += m.end()
    m = re.search(rf"(?<![A-Za-z0-9_-]){re.escape(path[-1])}\s*:\s*(\[[^\]]*\]|[^,}}\n]+)", text[pos:])
    if not m:
        return None
    s, e = pos + m.start(1), pos + m.end(1)
    old = text[s:e]
    new = fmt(value)
    if not old.lstrip().startswith("["):
        new = new + (old[len(old.rstrip()) :])  # пробелы перед `,` или `}` сохраняем
    return text[:s] + new + text[e:]


def _replace_block_field(lines: list[str], start: int, end: int, path: list[str], value: Any, parent_indent: int):
    """Поле в блочной записи элемента: `key: value  # комментарий` или `key: {flow}`; вложенный путь — через
    flow-словарь на той же строке или вложенный блок. None — не нашли или значение в блочном стиле."""
    i = _find_key(lines, start, end, path[0], parent_indent)
    if i is None:
        return None
    m = re.match(rf"^(\s*{_KEY}\s*:)(.*)$", lines[i])
    head, rest = m.group(1), m.group(2)
    mm = re.match(r"^(\s*)([^#]*?)(\s*#.*)?$", rest)
    before, body, comment = mm.group(1), mm.group(2), mm.group(3) or ""
    if len(path) == 1:
        if body.startswith("{") or body == "":
            return None
        lines[i] = f"{head}{before or ' '}{fmt(value)}{comment}"
        return lines
    if body.startswith("{"):
        new = _replace_flow(body, path[1:], value)
        if new is None:
            return None
        lines[i] = f"{head}{before}{new}{comment}"
        return lines
    if body == "":  # вложенный блок
        return _replace_block_field(
            lines, i + 1, _block_end(lines, i, _indent(lines[i])), path[1:], value, _indent(lines[i])
        )
    return None


def replace_field(text: str, group_key: str, eid: str, path: list[str], value: Any) -> str | None:
    """skeleton → <group_key> → элемент с id → поле path: заменить значение в тексте. None — не получилось."""
    lines = text.split("\n")
    sk = _find_key(lines, 0, len(lines), "skeleton", -1)
    if sk is None:
        return None
    sk_end = _block_end(lines, sk, _indent(lines[sk]))
    gk = _find_key(lines, sk + 1, sk_end, group_key, _indent(lines[sk]))
    if gk is None:
        return None
    g_end = _block_end(lines, gk, _indent(lines[gk]))
    for a, b in _items(lines, gk + 1, g_end):
        chunk = "\n".join(lines[a:b])
        if not _item_has_id(chunk, eid):
            continue
        first = re.sub(r"^\s*-\s*", "", lines[a])
        if first.lstrip().startswith("{"):  # flow-элемент (может занимать несколько строк)
            new = _replace_flow(chunk, path, value)
            if new is None:
                return None
            return "\n".join(lines[:a] + new.split("\n") + lines[b:])
        # блочный элемент: первая строка `- key: value` — ключи с отступом тире + 2
        dash = _indent(lines[a])
        body_lines = list(lines)
        body_lines[a] = " " * (dash + 2) + first  # тире заменяем пробелами, чтобы искать ключи единообразно
        res = _replace_block_field(body_lines, a, b, path, value, dash + 1)
        if res is None:
            return None
        res[a] = " " * dash + "- " + res[a][dash + 2 :]
        return "\n".join(res)
    return None


# ---------------------------------------------------------------- применение правок


def apply_edits(text: str, edits: list[dict]) -> tuple[str, list[str]]:
    """edits: [{ref, set: {поле: значение}}] → новый текст project.yaml и строки «что изменилось».
    Поле правится на месте; если не нашлось в тексте — файл переписывается целиком (без комментариев)."""
    spec = yaml.safe_load(text) or {}
    applied: list[str] = []
    rewrite = False
    for ed in edits:
        ref = str(ed.get("ref") or "")
        kind, item = find_entity(spec, ref)
        group, eid = parse_ref(ref)
        changes = ed.get("set") or {}
        if not isinstance(changes, dict) or not changes:
            raise LayoutEditError(f"«{ref}»: нет изменений (set)")
        for field, raw in changes.items():
            path = str(field).split(".")
            value = coerce(kind, str(field), raw)
            ok, old = _get(item, path)
            if ok and _same(old, value):
                continue
            new_text = None if rewrite else replace_field(text, GROUPS[group], eid, path, value)
            if new_text is not None:
                parsed = yaml.safe_load(new_text) or {}
                _, got = _get(find_entity(parsed, ref)[1], path)
                if _same(got, value):
                    text, spec = new_text, parsed
                    _, item = find_entity(spec, ref)
                else:
                    new_text = None
            if new_text is None:
                _set(item, path, value)
                rewrite = True
            applied.append(f"{ref} {field} {fmt(old) if ok else '—'} → {fmt(value)}")
    if not applied:
        raise LayoutEditError("значения не изменились")
    if rewrite:
        text = yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=110)
    validate(spec)
    return text, applied


def validate(spec: dict) -> None:
    try:
        sk = Skeleton.model_validate(spec.get("skeleton") or {})
    except Exception as e:  # noqa: BLE001 — текст ошибки валидации уходит конструктору
        raise LayoutEditError(f"скелет после правки не читается: {str(e)[:300]}") from e
    for e in sk.envelopes:
        if any(e.min[i] > e.max[i] for i in range(3)):
            raise LayoutEditError(f"envelope:{e.id}: min должен быть не больше max по каждой оси")
    for b in sk.surroundings:
        lo, hi = b.bbox()
        if any(lo[i] > hi[i] for i in range(3)):
            raise LayoutEditError(f"surrounding:{b.id}: min должен быть не больше max по каждой оси")


def edit(ws: Workspace, project: str, edits: list[dict], actor: Actor, message: str | None = None) -> dict:
    """Применить правки к project.yaml и закоммитить от имени actor."""
    text = ws.read_file(project, "project.yaml")
    new, applied = apply_edits(text, edits)
    msg = (message or "").strip() or ("компоновка с эскиза: " + "; ".join(applied))
    res = ws.write_files(project, {"project.yaml": new}, msg[:200], actor)
    return {"commit": res["commit"], "applied": applied}


# ---------------------------------------------------------------- размер числом


def _position(kind: str, item: dict, k: int) -> float:
    """Координата сущности вдоль оси k для знака сдвига: origin / center / середина min–max."""
    fields = POSITION[kind]
    vals = []
    for f in fields:
        ok, v = _get(item, f.split("."))
        if ok and isinstance(v, list | tuple) and len(v) == 3:
            vals.append(float(v[k]))
    if not vals:
        raise LayoutEditError(f"у сущности нет положения ({', '.join(fields)})")
    return sum(vals) / len(vals)


def dim_edits(spec: dict, dims: list[dict], dim_id: str, value: Any) -> tuple[list[dict], str]:
    """Правки для размера dim_id → value: вторая сущность размера сдвигается вдоль оси размера.
    Возвращает (edits, описание)."""
    dim = next((d for d in dims if d.get("id") == dim_id), None)
    if dim is None:
        have = ", ".join(str(d.get("id")) for d in dims)
        raise LayoutEditError(f"нет размера «{dim_id}» на компоновке; есть: {have or 'ничего'}")
    if dim.get("kind") != "linear" or dim.get("value") is None or len(dim.get("refs") or []) != 2:
        raise LayoutEditError(f"размер «{dim_id}» числом не правится (не линейный)")
    new = _num(value, "размер")
    if new <= 0:
        raise LayoutEditError("размер должен быть больше нуля")
    k = AXES.index(str(dim["axis"]))
    ref_a, ref_b = dim["refs"]
    kind_a, item_a = find_entity(spec, ref_a)
    kind_b, item_b = find_entity(spec, ref_b)
    sign = 1.0 if _position(kind_b, item_b, k) >= _position(kind_a, item_a, k) else -1.0
    delta = sign * (new - float(dim["value"]))
    if abs(delta) < 1e-6:
        raise LayoutEditError("значение размера не изменилось")
    changes: dict[str, list[float]] = {}
    for f in POSITION[kind_b]:
        ok, v = _get(item_b, f.split("."))
        if ok and isinstance(v, list | tuple) and len(v) == 3:
            moved = [float(c) for c in v]
            moved[k] += delta
            changes[f] = moved
    if not changes:
        raise LayoutEditError(f"«{ref_b}»: нечего сдвигать")
    ax = dim["axis"]
    what = f"размер {dim_id} ({ax}): {fmt(dim['value'])} → {fmt(new)}, сдвиг {ref_b} на {fmt(delta)} по {ax}"
    return [{"ref": ref_b, "set": changes}], what


def edit_dim(ws: Workspace, project: str, dims: list[dict], dim_id: str, value: Any, actor: Actor, message=None):
    spec = ws.spec(project)
    edits, what = dim_edits(spec, dims, dim_id, value)
    return edit(ws, project, edits, actor, message or f"компоновка с эскиза: {what}")
