"""Вложения конструктора — набросок от руки, фото, экспорт из доски — в папке `attachments/` репозитория проекта (D28).

Файл коммитится от имени конструктора и живёт в истории вместе с моделью; агент получает его инструментом
`attachment(project, path)` как изображение. Растровая картинка с длинной стороной больше MAX_SIDE уменьшается при
загрузке (набросок — не архивный документ), фото поворачивается по EXIF. SVG и первая страница PDF растрируются
при выдаче агенту; файл доски `.excalidraw` отдаётся сводкой элементов (сам JSON агент читает `files_read`).
"""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from skelcad.server.workspace import Actor, Workspace, WorkspaceError

DIR = "attachments"
MAX_BYTES = 16 * 1024 * 1024  # предел загрузки (nginx skelcad.br: client_max_body_size 16m)
MAX_SIDE = 3000  # px: длинная сторона растровой картинки после загрузки
RASTER_WIDTH = 1600  # px: ширина растра SVG и страницы PDF для агента
KINDS = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".svg": "svg",
    ".pdf": "pdf",
    ".excalidraw": "excalidraw",
}
KIND_RU = {"image": "изображение", "svg": "векторный рисунок", "pdf": "PDF", "excalidraw": "файл доски Excalidraw"}
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".excalidraw": "application/json",
}
ACCEPT = ", ".join(sorted(KINDS))

_TRANSLIT = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
        "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    }
)  # fmt: skip


def slug(name: str) -> str:
    s = name.lower().translate(_TRANSLIT)
    s = re.sub(r"[^a-z0-9._-]+", "-", s).strip("-._")
    return s[:40].rstrip("-._") or "file"


def _ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ".jpg" if ext == ".jpeg" else ext


def _prepare_image(data: bytes, ext: str) -> tuple[bytes, int, int]:
    """Повернуть по EXIF, уменьшить до MAX_SIDE; перекодировать только если что-то менялось."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f"изображение не читается: {e}") from e
    orientation = im.getexif().get(0x0112, 1) if hasattr(im, "getexif") else 1
    changed = False
    if orientation not in (None, 1):
        im = ImageOps.exif_transpose(im)
        changed = True
    w, h = im.size
    if max(w, h) > MAX_SIDE:
        k = MAX_SIDE / max(w, h)
        im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        changed = True
    if not changed:
        return data, w, h
    buf = io.BytesIO()
    if ext == ".jpg":
        im.convert("RGB").save(buf, "JPEG", quality=90, optimize=True)
    elif ext == ".webp":
        im.save(buf, "WEBP", quality=90)
    else:
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue(), im.size[0], im.size[1]


def _validate(data: bytes, kind: str, filename: str) -> None:
    if kind == "svg" and b"<svg" not in data[:8192].lower():
        raise ValueError(f"«{filename}»: это не SVG")
    if kind == "pdf" and not data.startswith(b"%PDF"):
        raise ValueError(f"«{filename}»: это не PDF")
    if kind == "excalidraw":
        try:
            doc = json.loads(data)
        except ValueError as e:
            raise ValueError(f"«{filename}»: это не файл Excalidraw ({e})") from e
        if not isinstance(doc, dict) or doc.get("type") != "excalidraw":
            raise ValueError(f"«{filename}»: это не файл Excalidraw (нужен JSON с type: excalidraw)")


def add(ws: Workspace, project: str, filename: str, data: bytes, actor: Actor, note: str = "") -> dict:
    """Сохранить вложение в attachments/<дата-время>-<имя>.<ext> коммитом от имени actor."""
    ext = _ext(filename or "")
    kind = KINDS.get(ext)
    if not kind:
        raise ValueError(f"«{filename}»: допустимые файлы — {ACCEPT}")
    if not data:
        raise ValueError(f"«{filename}»: пустой файл")
    if len(data) > MAX_BYTES:
        raise ValueError(f"«{filename}»: файл больше {MAX_BYTES // 1024 // 1024} МБ")
    size: tuple[int, int] | None = None
    if kind == "image":
        data, w, h = _prepare_image(data, ext)
        size = (w, h)
    else:
        _validate(data, kind, filename)
    root = ws.path(project)
    base = f"{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M')}-{slug(Path(filename).stem)}"
    path = f"{DIR}/{base}{ext}"
    n = 2
    while (root / path).exists():
        path = f"{DIR}/{base}-{n}{ext}"
        n += 1
    what = KIND_RU[kind] + (f" {size[0]}×{size[1]}" if size else "")
    note = (note or "").strip()
    msg = f"вложение {Path(path).name}: {note}" if note else f"вложение {Path(path).name} ({what})"
    res = ws.write_files(project, {path: data}, msg, actor)
    return {"item": info(ws, project, path), "commit": res["commit"]}


def check_path(ws: Workspace, project: str, path: str) -> Path:
    """Путь вложения внутри attachments/ проекта; файл должен существовать."""
    rel = (path or "").replace("\\", "/").lstrip("/")
    if "/" not in rel:
        rel = f"{DIR}/{rel}"
    if not rel.startswith(DIR + "/") or rel.count("/") != 1:
        raise WorkspaceError(f"вложение «{path}»: ожидался путь {DIR}/<файл>")
    f = ws.path(project) / rel
    if not f.is_file():
        names = [i["path"] for i in list_items(ws, project)]
        raise WorkspaceError(f"вложения «{rel}» нет; есть: {', '.join(names) or 'ничего'}")
    return f


def info(ws: Workspace, project: str, path: str, commit: dict | None = None) -> dict:
    """Описание вложения; commit — последний коммит по файлу (если уже известен из общей истории)."""
    f = check_path(ws, project, path)
    rel = f"{DIR}/{f.name}"
    ext = _ext(f.name)
    item = {
        "path": rel,
        "name": f.name,
        "kind": KINDS.get(ext, "file"),
        "mime": MIME.get(ext, "application/octet-stream"),
        "bytes": f.stat().st_size,
        "width": None,
        "height": None,
        "author": None,
        "date": None,
    }
    if item["kind"] == "image":
        try:
            from PIL import Image

            with Image.open(f) as im:
                item["width"], item["height"] = im.size
        except Exception:  # noqa: BLE001 — размер не обязателен
            pass
    last = commit or next(iter(ws.history(project, limit=1, path=rel)), None)
    if last:
        item["author"], item["date"] = last["author"], last["date"]
    return item


def list_items(ws: Workspace, project: str) -> list[dict]:
    """Вложения проекта (из git), новые первыми — по порядку коммитов (один git log на весь список)."""
    names = {p for p in ws.files(project) if p.startswith(DIR + "/") and p.count("/") == 1}
    order: dict[str, tuple[int, dict]] = {}
    for i, c in enumerate(ws.history(project, limit=2000)):
        for f in c["files"]:
            if f in names and f not in order:
                order[f] = (i, c)
    out = []
    for p in sorted(names, key=lambda n: order.get(n, (10**9, {}))[0]):
        try:
            out.append(info(ws, project, p, order.get(p, (0, None))[1]))
        except WorkspaceError:
            continue
    return out


def remove(ws: Workspace, project: str, path: str, actor: Actor) -> dict:
    f = check_path(ws, project, path)
    rel = f"{DIR}/{f.name}"
    res = ws.write_files(project, {rel: None}, f"удалено вложение {f.name}", actor)
    return {"path": rel, "commit": res["commit"]}


def excalidraw_summary(doc: dict, limit: int = 200) -> str:
    """Элементы доски словами: тип, id, положение и размер, текст, ссылка customData.ref, привязки стрелок."""
    els = [e for e in doc.get("elements") or [] if isinstance(e, dict) and not e.get("isDeleted")]
    lines = []
    for e in els[:limit]:
        x, y = e.get("x", 0), e.get("y", 0)
        w, h = e.get("width", 0), e.get("height", 0)
        line = f"{e.get('type', '?')} {e.get('id', '')}: x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f}"
        if e.get("type") == "text" and e.get("text"):
            line += f" «{str(e['text']).strip()[:80]}»"
        if e.get("type") in ("arrow", "line"):
            sb, eb = e.get("startBinding") or {}, e.get("endBinding") or {}
            if sb.get("elementId") or eb.get("elementId"):
                line += f" {sb.get('elementId', '?')} → {eb.get('elementId', '?')}"
        if e.get("type") == "freedraw":
            line += f" точек {len(e.get('points') or [])}"
        ref = (e.get("customData") or {}).get("ref") if isinstance(e.get("customData"), dict) else None
        if ref:
            line += f" ref={ref}"
        lines.append(line)
    head = f"элементов {len(els)}" + (f" (показаны первые {limit})" if len(els) > limit else "")
    return "\n".join([head, *lines])


def image(ws: Workspace, project: str, path: str) -> dict:
    """Вложение для агента: {png: bytes | None, format, text, item}. Растр — как есть (webp → png), SVG и PDF —
    растрируются, .excalidraw — сводка элементов текстом."""
    item = info(ws, project, path)
    f = ws.path(project) / item["path"]
    kind, ext = item["kind"], _ext(f.name)
    data = f.read_bytes()
    if kind == "image":
        if ext == ".webp":
            from PIL import Image

            buf = io.BytesIO()
            Image.open(io.BytesIO(data)).convert("RGB").save(buf, "PNG")
            return {"png": buf.getvalue(), "format": "png", "text": None, "item": item}
        return {"png": data, "format": "jpeg" if ext == ".jpg" else "png", "text": None, "item": item}
    if kind == "svg":
        import resvg_py

        svg = data.decode("utf-8", "replace")
        png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=RASTER_WIDTH, background="white"))
        return {"png": png, "format": "png", "text": None, "item": item}
    if kind == "pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        try:
            pages = len(pdf)
            page = pdf[0]
            scale = max(1.0, RASTER_WIDTH / max(1.0, page.get_width()))
            pil = page.render(scale=scale).to_pil()
        finally:
            pdf.close()
        buf = io.BytesIO()
        pil.convert("RGB").save(buf, "PNG")
        return {"png": buf.getvalue(), "format": "png", "text": f"страниц {pages}, показана первая", "item": item}
    doc = json.loads(data)
    return {"png": None, "format": None, "text": excalidraw_summary(doc), "item": item}
