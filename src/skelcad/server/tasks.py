"""Задачи агенту из workbench: файловая очередь /data/tasks/<id>/ (task.json, status.json, events.jsonl, stop).

Сервер создаёт задачу и читает события; контейнер agent (skelcad agent --queue) забирает задачи и ведёт
цикл с моделью. Пока задача в очереди или выполняется — проект «у агента»: правки из workbench закрыты.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path

ACTIVE = ("queued", "running")
MIMES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}


class TaskError(ValueError):
    pass


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


class TaskStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, task_id: str) -> Path:
        if not task_id or "/" in task_id or task_id.startswith("."):
            raise TaskError(f"неверный id задачи «{task_id}»")
        d = self.root / task_id
        if not (d / "task.json").is_file():
            raise TaskError(f"нет задачи «{task_id}»")
        return d

    def create(
        self,
        project: str,
        text: str,
        user: str,
        variant: str | None = None,
        max_steps: int = 60,
        attachments: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict:
        """attachments — пути вложений проекта (attachments/<файл>), которые агент получит с задачей как изображения;
        provider / model — провайдер модели из providers.json и модель (пусто — умолчания провайдера, D29)."""
        if not (text or "").strip():
            raise TaskError("нужен текст задачи")
        atts = [str(a).strip() for a in (attachments or []) if str(a).strip()]
        if any(not a.startswith("attachments/") or a.count("/") != 1 for a in atts):
            raise TaskError("вложения задачи — пути attachments/<файл> из проекта")
        if (a := self.active(project)) is not None:
            raise TaskError(f"проект уже у агента: задача {a['id']} ({a['status']}); дождитесь или остановите её")
        # миллисекунды в ключе: list() и claim() сортируют по имени папки, две задачи в одну секунду шли вразнобой
        tid = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S-%f")[:-3] + "-" + secrets.token_hex(2)
        d = self.root / tid
        d.mkdir(parents=True)
        task = {
            "id": tid,
            "project": project,
            "variant": variant,
            "text": text.strip(),
            "user": user,
            "created": _now(),
            "max_steps": max_steps,
            "attachments": atts,
            "provider": (provider or "").strip() or None,
            "model": (model or "").strip() or None,
        }
        (d / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "events.jsonl").touch()
        self._status(d, {"status": "queued", "updated": _now()})
        return self.get(tid)

    def _status(self, d: Path, st: dict) -> None:
        tmp = d / "status.json.tmp"
        tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, d / "status.json")

    def get(self, task_id: str) -> dict:
        d = self._dir(task_id)
        task = json.loads((d / "task.json").read_text(encoding="utf-8"))
        try:
            st = json.loads((d / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {"status": "queued"}
        task.update(st)
        task["stop_requested"] = (d / "stop").exists()
        return task

    def list(self, project: str | None = None, limit: int = 20) -> list[dict]:
        out = []
        for d in sorted(self.root.iterdir(), reverse=True):
            if not (d / "task.json").is_file():
                continue
            t = self.get(d.name)
            if project and t["project"] != project:
                continue
            out.append(t)
            if len(out) >= limit:
                break
        return out

    def active(self, project: str) -> dict | None:
        for t in self.list(project, limit=50):
            if t["status"] in ACTIVE:
                return t
        return None

    def stop(self, task_id: str) -> dict:
        d = self._dir(task_id)
        (d / "stop").touch()
        t = self.get(task_id)
        if t["status"] == "queued":  # ещё не взята агентом — закрываем сразу
            self._status(d, {"status": "stopped", "updated": _now(), "result": "остановлена до запуска"})
        return self.get(task_id)

    def events(self, task_id: str, since: int = 0, limit: int = 500) -> dict:
        d = self._dir(task_id)
        lines = (d / "events.jsonl").read_text(encoding="utf-8").splitlines()
        chunk = lines[since : since + limit]
        events = []
        for ln in chunk:
            try:
                events.append(json.loads(ln))
            except ValueError:
                continue
        return {"events": events, "next": since + len(chunk), "total": len(lines), "task": self.get(task_id)}

    # ---------- корзина: задачи уходят и возвращаются вместе с проектом (M2.5)

    def archive(self, project: str, dst: Path) -> int:
        """Перенести все задачи проекта в dst (папка корзины проекта); возвращает их число."""
        n = 0
        for d in list(self.root.iterdir()):
            try:
                task = json.loads((d / "task.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if task.get("project") != project:
                continue
            dst.mkdir(parents=True, exist_ok=True)
            shutil.move(str(d), str(dst / d.name))
            n += 1
        return n

    def unarchive(self, src: Path) -> int:
        n = 0
        if not src.is_dir():
            return 0
        for d in list(src.iterdir()):
            if (d / "task.json").is_file() and not (self.root / d.name).exists():
                shutil.move(str(d), str(self.root / d.name))
                n += 1
        return n

    # ---------- со стороны агента

    def claim(self) -> dict | None:
        """Взять первую задачу в очереди (атомарно через O_EXCL-файл claimed)."""
        for d in sorted(self.root.iterdir()):
            if not (d / "task.json").is_file():
                continue
            try:
                st = json.loads((d / "status.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if st.get("status") != "queued":
                continue
            try:
                fd = os.open(d / "claimed", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            except FileExistsError:
                continue
            self._status(d, {"status": "running", "started": _now(), "updated": _now(), "steps": 0})
            return self.get(d.name)
        return None

    def event(self, task_id: str, kind: str, **data) -> None:
        d = self._dir(task_id)
        rec = {"t": _now(), "type": kind, **data}
        with (d / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def progress(self, task_id: str, steps: int) -> None:
        d = self._dir(task_id)
        st = self.get(task_id)
        self._status(d, {k: st[k] for k in ("status", "started") if k in st} | {"steps": steps, "updated": _now()})

    def stop_requested(self, task_id: str) -> bool:
        return (self._dir(task_id) / "stop").exists()

    FILE_RE = re.compile(r"^[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp|svg)$")

    def save_file(self, task_id: str, name: str, data: bytes) -> str | None:
        """Картинка, которую агент получил от инструмента (компоновка, вид, вложение), — файлом в папке задачи;
        рабочее место показывает её в ходе работы (GET /api/tasks/{id}/files/{name})."""
        if not self.FILE_RE.match(name) or not data:
            return None
        try:
            (self._dir(task_id) / name).write_bytes(data)
        except OSError:
            return None
        return name

    def file_path(self, task_id: str, name: str) -> tuple[Path, str]:
        if not self.FILE_RE.match(name):
            raise TaskError(f"неверное имя файла «{name}»")
        f = self._dir(task_id) / name
        if not f.is_file():
            raise TaskError(f"у задачи {task_id} нет файла «{name}»")
        return f, MIMES[f.suffix.lower().lstrip(".")]

    def finish(self, task_id: str, status: str, result: str | None = None, error: str | None = None, **extra) -> None:
        d = self._dir(task_id)
        st = self.get(task_id)
        self._status(
            d,
            {
                "status": status,
                "started": st.get("started"),
                "finished": _now(),
                "updated": _now(),
                "steps": st.get("steps", 0),
                "result": result,
                "error": error,
                **extra,
            },
        )
