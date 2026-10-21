"""Папки и узлы рабочего места (M2.5, D32): <data>/workspace.yaml — список папок и размещение проектов
(folder — папка, parent — проект-родитель для узла изделия). Это организация рабочего места, а не модель
изделия, поэтому живёт рядом с проектами, а не в project.yaml и не в git проекта."""

from __future__ import annotations

import os
import re
import secrets
import threading
from pathlib import Path

import yaml

FILE = "workspace.yaml"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}  # fmt: skip


class MetaError(ValueError):
    pass


def slug(title: str, limit: int = 24) -> str:
    out = "".join(TRANSLIT.get(ch, ch) for ch in title.lower())
    out = re.sub(r"[^a-z0-9]+", "_", out).strip("_")
    return out[:limit] or "folder"


class Meta:
    """Файл небольшой, читается целиком на каждый запрос; запись атомарная под замком."""

    def __init__(self, root: Path):
        self.path = Path(root) / FILE
        self._lock = threading.Lock()

    # ---------- файл ----------

    def load(self) -> dict:
        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        folders = [f for f in (data.get("folders") or []) if isinstance(f, dict) and f.get("id")]
        projects = {k: v for k, v in (data.get("projects") or {}).items() if isinstance(v, dict)}
        return {"folders": folders, "projects": projects}

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(".yaml.tmp")
        tmp.write_text(
            "# Папки и узлы рабочего места SkelCAD: организация, не модель изделия (D32).\n"
            + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    # ---------- папки ----------

    def folders(self) -> list[dict]:
        return self.load()["folders"]

    def folder(self, fid: str) -> dict:
        for f in self.folders():
            if f["id"] == fid:
                return f
        raise MetaError(f"нет папки «{fid}»")

    def folder_create(self, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            raise MetaError("назовите папку")
        with self._lock:
            data = self.load()
            if any(f.get("title") == title for f in data["folders"]):
                raise MetaError(f"папка «{title}» уже есть")
            base = slug(title)
            fid = base
            while any(f["id"] == fid for f in data["folders"]):
                fid = f"{base}_{secrets.token_hex(2)}"
            rec = {"id": fid, "title": title}
            data["folders"].append(rec)
            self._save(data)
            return rec

    def folder_rename(self, fid: str, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            raise MetaError("назовите папку")
        with self._lock:
            data = self.load()
            for f in data["folders"]:
                if f["id"] == fid:
                    f["title"] = title
                    self._save(data)
                    return f
        raise MetaError(f"нет папки «{fid}»")

    def folder_delete(self, fid: str, names: list[str]) -> None:
        """Удалить пустую папку; names — существующие проекты (в папке их быть не должно)."""
        with self._lock:
            data = self.load()
            if not any(f["id"] == fid for f in data["folders"]):
                raise MetaError(f"нет папки «{fid}»")
            inside = [n for n in names if (data["projects"].get(n) or {}).get("folder") == fid]
            if inside:
                raise MetaError(f"папка не пуста: {', '.join(sorted(inside))} — перенесите или удалите проекты")
            data["folders"] = [f for f in data["folders"] if f["id"] != fid]
            for v in data["projects"].values():
                if v.get("folder") == fid:
                    v["folder"] = None
            self._save(data)

    # ---------- размещение проектов ----------

    def project(self, name: str) -> dict:
        rec = self.load()["projects"].get(name) or {}
        return {"folder": rec.get("folder"), "parent": rec.get("parent")}

    def place(self, name: str, names: list[str], folder: str | None = ..., parent: str | None = ...) -> dict:  # type: ignore[assignment]
        """Положить проект в папку и/или под родителя; «...» — не менять. Узел наследует папку родителя."""
        with self._lock:
            data = self.load()
            rec = dict(data["projects"].get(name) or {})
            if parent is not ...:
                if parent:
                    if parent == name:
                        raise MetaError("узел не может быть родителем самому себе")
                    if parent not in names:
                        raise MetaError(f"нет проекта «{parent}»")
                    chain, cur = set(), parent  # проверка цикла по цепочке родителей
                    while cur:
                        if cur == name:
                            raise MetaError("цикл: проект уже стоит выше в составе изделия")
                        if cur in chain:
                            break
                        chain.add(cur)
                        cur = (data["projects"].get(cur) or {}).get("parent")
                    rec["parent"] = parent
                    rec["folder"] = (data["projects"].get(parent) or {}).get("folder")
                else:
                    rec["parent"] = None
            if folder is not ... and (parent is ... or not parent):
                if folder and not any(f["id"] == folder for f in data["folders"]):
                    raise MetaError(f"нет папки «{folder}»")
                rec["folder"] = folder or None
            data["projects"][name] = rec
            self._save(data)
            return {"folder": rec.get("folder"), "parent": rec.get("parent")}

    def forget(self, name: str) -> None:
        with self._lock:
            data = self.load()
            if name in data["projects"]:
                del data["projects"][name]
                for v in data["projects"].values():
                    if v.get("parent") == name:
                        v["parent"] = None
                self._save(data)

    def children(self, name: str, names: list[str]) -> list[str]:
        pr = self.load()["projects"]
        return [n for n in names if (pr.get(n) or {}).get("parent") == name]

    def tree(self, names: list[str]) -> dict:
        """Папки с корневыми проектами и дерево узлов:
        {folders: [{id, title, projects: [...]}], loose: [...], children: {name: [...]}}."""
        data = self.load()
        pr = data["projects"]
        children: dict[str, list[str]] = {}
        roots = []
        for n in names:
            rec = pr.get(n) or {}
            p = rec.get("parent")
            if p and p in names:
                children.setdefault(p, []).append(n)
            else:
                roots.append(n)
        folders = [
            {**f, "projects": [n for n in roots if (pr.get(n) or {}).get("folder") == f["id"]]} for f in data["folders"]
        ]
        known = {f["id"] for f in data["folders"]}
        loose = [n for n in roots if (pr.get(n) or {}).get("folder") not in known]
        return {"folders": folders, "loose": loose, "children": children}
