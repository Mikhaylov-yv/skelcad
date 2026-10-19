"""Проекты на сервере: папка `projects/<имя>` — git-репозиторий с project.yaml.

Любое изменение файлов проекта — коммит. Автор коммита агента: «SkelCAD agent (<клиент>)»,
клиент — имя токена, по которому пришёл запрос. Конструктор, если работает через git, коммитит
под своим именем. История отвечает на вопрос «кто что сделал»; откат — `revert`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
FORBIDDEN_TOP = {".git", "out", ".gitea", ".github"}
GITIGNORE = "out/\n__pycache__/\n*.pyc\n.tmp/\n"


class WorkspaceError(ValueError):
    pass


def default_templates_dir() -> Path:
    env = os.environ.get("SKELCAD_TEMPLATES")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "examples"


@dataclass
class Actor:
    name: str
    email: str

    @classmethod
    def agent(cls, client: str) -> Actor:
        return cls(f"SkelCAD agent ({client})", "agent@skelcad")

    @classmethod
    def system(cls) -> Actor:
        return cls("SkelCAD", "skelcad@localhost")

    def env(self) -> dict:
        return {
            "GIT_AUTHOR_NAME": self.name,
            "GIT_AUTHOR_EMAIL": self.email,
            "GIT_COMMITTER_NAME": self.name,
            "GIT_COMMITTER_EMAIL": self.email,
        }


def git(root: Path, *args: str, actor: Actor | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ | {"GIT_TERMINAL_PROMPT": "0", "LANG": "C.UTF-8"}
    if actor:
        env |= actor.env()
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args[:2])}: {p.stderr.strip() or p.stdout.strip()}")
    return p


class Workspace:
    def __init__(self, root: Path, templates: Path | None = None):
        self.root = Path(root).resolve()
        self.projects_dir = self.root / "projects"
        self.out_dir = self.root / "out"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.templates = templates or default_templates_dir()

    # ---------- проекты ----------

    def path(self, name: str) -> Path:
        if not NAME_RE.match(name or ""):
            raise WorkspaceError(f"недопустимое имя проекта «{name}»: строчные буквы, цифры, «-», «_»")
        p = self.projects_dir / name
        if not (p / "project.yaml").exists():
            raise WorkspaceError(f"проект «{name}» не найден; есть: {', '.join(self.names()) or 'ничего'}")
        return p

    def names(self) -> list[str]:
        return sorted(p.name for p in self.projects_dir.iterdir() if (p / "project.yaml").exists())

    def spec(self, name: str) -> dict:
        return yaml.safe_load((self.path(name) / "project.yaml").read_text(encoding="utf-8")) or {}

    def variants(self, name: str) -> list[dict]:
        vdir = self.path(name) / "variants"
        out = []
        for f in sorted(vdir.glob("*.yaml")) if vdir.is_dir() else []:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            out.append({"id": d.get("id", f.stem), "title": d.get("title", ""), "file": f"variants/{f.name}"})
        return out

    def info(self, name: str) -> dict:
        spec = self.spec(name)
        last = self.history(name, limit=1)
        return {
            "name": name,
            "title": spec.get("title", ""),
            "standards": spec.get("standards", []),
            "variants": [v["id"] for v in self.variants(name)],
            "last_commit": last[0] if last else None,
        }

    def templates_list(self) -> list[str]:
        return (
            sorted(p.name for p in self.templates.iterdir() if (p / "project.yaml").exists())
            if self.templates.is_dir()
            else []
        )

    def create(
        self, name: str, template: str | None = None, actor: Actor | None = None, origin: str | None = None
    ) -> dict:
        if not NAME_RE.match(name or ""):
            raise WorkspaceError(f"недопустимое имя проекта «{name}»: строчные буквы, цифры, «-», «_»")
        dst = self.projects_dir / name
        if dst.exists():
            raise WorkspaceError(f"проект «{name}» уже есть")
        if template and template != "empty":
            src = self.templates / template
            if not (src / "project.yaml").exists():
                raise WorkspaceError(f"нет шаблона «{template}»; есть: {', '.join(self.templates_list())}, empty")
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", "__pycache__", ".git", ".tmp"))
            spec = yaml.safe_load((dst / "project.yaml").read_text(encoding="utf-8")) or {}
            if spec.get("id") != name:
                spec["id"] = name
                (dst / "project.yaml").write_text(
                    yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8"
                )
        else:
            dst.mkdir()
            (dst / "project.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": name,
                        "title": name,
                        "lang": "ru",
                        "standards": [],
                        "requirements": {},
                        "skeleton": {},
                        "params": {},
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            (dst / "variants").mkdir()
        (dst / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
        actor = actor or Actor.system()
        git(dst, "init", "-q", "-b", "main")
        git(dst, "add", "-A")
        git(dst, "commit", "-q", "-m", f"Проект {name}" + (f" из шаблона {template}" if template else ""), actor=actor)
        if origin:
            git(dst, "remote", "add", "origin", origin)
            self.push(name)
        return self.info(name)

    def seed(self, names: list[str]) -> list[str]:
        """Завести проекты-примеры, которых ещё нет (при старте сервера)."""
        made = []
        for n in names:
            if n and n not in self.names() and n in self.templates_list():
                self.create(n, template=n)
                made.append(n)
        return made

    # ---------- файлы ----------

    def _rel(self, name: str, path: str) -> Path:
        root = self.path(name)
        rel = Path(path.replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise WorkspaceError(f"путь «{path}» должен быть относительным внутри проекта")
        if rel.parts[0] in FORBIDDEN_TOP:
            raise WorkspaceError(f"путь «{path}» недоступен для записи")
        full = (root / rel).resolve()
        if root.resolve() not in full.parents and full != root.resolve():
            raise WorkspaceError(f"путь «{path}» выходит за пределы проекта")
        return full

    def read_file(self, name: str, path: str) -> str:
        f = self._rel(name, path)
        if not f.is_file():
            raise WorkspaceError(f"файла «{path}» нет; файлы проекта: {', '.join(self.files(name)[:40])}")
        return f.read_text(encoding="utf-8")

    def files(self, name: str) -> list[str]:
        p = git(self.path(name), "ls-files").stdout.split()
        return sorted(p)

    def write_files(self, name: str, files: dict[str, str], message: str, actor: Actor) -> dict:
        if not files:
            raise WorkspaceError("нет файлов для записи")
        if not (message or "").strip():
            raise WorkspaceError("нужно сообщение коммита: что и зачем изменено")
        root = self.path(name)
        written = []
        for path, content in files.items():
            f = self._rel(name, path)
            f.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                if f.exists():
                    f.unlink()
            else:
                f.write_text(content, encoding="utf-8")
            written.append(f.relative_to(root).as_posix())
        git(root, "add", "-A", "--", *written)
        if not git(root, "status", "--porcelain", "--", *written).stdout.strip():
            raise WorkspaceError("содержимое не изменилось — коммит не нужен")
        git(root, "commit", "-q", "-m", message, actor=actor)
        self.push(name)
        return {"commit": self.history(name, limit=1)[0], "files": written}

    # ---------- история ----------

    def history(self, name: str, limit: int = 20, path: str | None = None) -> list[dict]:
        root = self.path(name)
        args = ["log", f"-n{limit}", "--format=%x1e%h%x1f%H%x1f%an%x1f%aI%x1f%s", "--name-only"]
        if path:
            args += ["--", path]
        p = git(root, *args, check=False)
        if p.returncode != 0:
            return []
        out = []
        for chunk in p.stdout.split("\x1e"):
            if not chunk.strip():
                continue
            head, _, body = chunk.partition("\n")
            short, full, author, date, subject = head.split("\x1f")
            out.append(
                {
                    "commit": short,
                    "hash": full,
                    "author": author,
                    "date": date,
                    "message": subject,
                    "files": [ln for ln in body.split("\n") if ln.strip()],
                }
            )
        return out

    NOTES_REF = "skelcad"

    def notes(self, name: str) -> dict[str, str]:
        """Заметки git (ref notes/skelcad) по полным хешам: {hash: текст}. Одна строка на заметку."""
        p = git(self.path(name), "log", f"--notes={self.NOTES_REF}", "--format=%x1e%H%x1f%N", check=False)
        out: dict[str, str] = {}
        for chunk in p.stdout.split("\x1e"):
            if "\x1f" not in chunk:
                continue
            full, _, note = chunk.partition("\x1f")
            note = note.strip()
            if note:
                out[full.strip()] = note
        return out

    def note_set(self, name: str, commit: str, text: str | None, actor: Actor) -> None:
        """text=None — убрать заметку."""
        full = self.rev(name, commit)
        root = self.path(name)
        if text is None:
            git(root, "notes", f"--ref={self.NOTES_REF}", "remove", "--ignore-missing", full, actor=actor)
        else:
            git(root, "notes", f"--ref={self.NOTES_REF}", "add", "-f", "-m", text, full, actor=actor)

    def revert(self, name: str, commit: str, actor: Actor, message: str | None = None) -> dict:
        root = self.path(name)
        if not re.fullmatch(r"[0-9a-fA-F]{4,40}|HEAD(~\d+)?", commit or ""):
            raise WorkspaceError(f"ожидался хеш коммита, получено «{commit}»")
        p = git(root, "revert", "--no-edit", commit, actor=actor, check=False)
        if p.returncode != 0:
            git(root, "revert", "--abort", check=False)
            raise WorkspaceError(f"откат {commit} не прошёл (конфликт?): {p.stderr.strip()[:500]}")
        if message:
            git(root, "commit", "-q", "--amend", "-m", message, actor=actor)
        self.push(name)
        return {"commit": self.history(name, limit=1)[0]}

    # ---------- origin (необязательно: конструктор может работать со своим клоном) ----------

    def has_origin(self, name: str) -> bool:
        return git(self.path(name), "remote", "get-url", "origin", check=False).returncode == 0

    def pull(self, name: str) -> str | None:
        """fetch + fast-forward из origin; конфликт — ошибка, без тихого слияния."""
        if not self.has_origin(name):
            return None
        root = self.path(name)
        git(root, "fetch", "-q", "origin")
        p = git(root, "merge", "--ff-only", "-q", "origin/main", check=False)
        if p.returncode != 0:
            raise WorkspaceError(
                f"проект {name}: история разошлась с origin (на сервере и у конструктора разные коммиты); "
                "разрешите вручную: git pull --rebase / git push в клоне конструктора"
            )
        return self.rev(name, "HEAD")[:7]

    def push(self, name: str) -> None:
        if not self.has_origin(name):
            return
        p = git(self.path(name), "push", "-q", "origin", "HEAD:main", check=False)
        if p.returncode != 0:
            raise WorkspaceError(f"проект {name}: push в origin не прошёл: {p.stderr.strip()[:300]}")

    def show(self, name: str, commit: str) -> str:
        return git(self.path(name), "show", "--stat", "--format=%h %an %aI%n%s%n", commit).stdout

    def diff_files(self, name: str, a: str, b: str) -> str:
        return git(self.path(name), "diff", "--stat", a, b).stdout

    def rev(self, name: str, ref: str) -> str:
        p = git(self.path(name), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        if p.returncode != 0:
            raise WorkspaceError(f"нет коммита «{ref}» в проекте {name}")
        return p.stdout.strip()

    def snapshot(self, name: str, ref: str) -> Path:
        """Папка со снимком проекта на коммите (кэш в <data>/snapshots/<проект>/<hash>). HEAD — сам проект."""
        full = self.rev(name, ref)
        if full == self.rev(name, "HEAD"):
            return self.path(name)
        dst = self.root / "snapshots" / name / full[:12]
        if not (dst / "project.yaml").exists():
            self.checkout_to(name, full, dst)
        return dst

    def checkout_to(self, name: str, commit: str, dst: Path) -> Path:
        """Снимок проекта на коммите в отдельную папку (для diff между состояниями)."""
        root = self.path(name)
        dst.mkdir(parents=True, exist_ok=True)
        p = subprocess.run(
            f"git -C {root} archive --format=tar {commit} | tar -x -C {dst}",
            shell=True,
            capture_output=True,
            text=True,
        )
        if p.returncode != 0:
            raise WorkspaceError(f"нет коммита {commit}: {p.stderr.strip()[:300]}")
        return dst
