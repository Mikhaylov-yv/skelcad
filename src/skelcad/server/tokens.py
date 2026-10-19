"""Токены клиентов MCP, заведённые из workbench (администраторы): <data>/tokens.json.
Дополняют статические SKELCAD_TOKENS; значение токена показывается один раз при создании."""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,39}$")


class TokenError(ValueError):
    pass


class TokenStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._mtime: float | None = None
        self._data: dict[str, dict] = {}

    def _load(self) -> dict[str, dict]:
        try:
            m = self.path.stat().st_mtime
        except FileNotFoundError:
            self._data, self._mtime = {}, None
            return self._data
        if m != self._mtime:
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except ValueError:
                self._data = {}
            self._mtime = m
        return self._data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        self._mtime = None

    def tokens(self) -> dict[str, str]:
        """{token: имя клиента} для проверки входа."""
        return {v["token"]: name for name, v in self._load().items() if v.get("token")}

    def list(self) -> list[dict]:
        return [
            {"name": n, "created": v.get("created"), "created_by": v.get("created_by")}
            for n, v in sorted(self._load().items())
        ]

    def create(self, name: str, who: str, static_names: set[str] = frozenset()) -> dict:
        if not NAME_RE.match(name or ""):
            raise TokenError("имя клиента: строчные латинские буквы, цифры, «-», «_», «.», от 2 до 40 символов")
        data = dict(self._load())
        if name in data or name in static_names:
            raise TokenError(f"клиент «{name}» уже есть; отзовите его или выберите другое имя")
        token = "sk_" + secrets.token_urlsafe(30)
        data[name] = {"token": token, "created": datetime.now(tz=UTC).isoformat(timespec="seconds"), "created_by": who}
        self._save(data)
        return {"name": name, "token": token, "created": data[name]["created"], "created_by": who}

    def delete(self, name: str) -> None:
        data = dict(self._load())
        if name not in data:
            raise TokenError(f"нет клиента «{name}»")
        del data[name]
        self._save(data)
