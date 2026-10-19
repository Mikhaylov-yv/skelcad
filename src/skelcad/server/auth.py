"""Кто пришёл: агент по Bearer-токену (точка /mcp) или пользователь workbench.

Режим для браузера — SKELCAD_AUTH:
  proxy   — пользователь из заголовков oauth2-proxy (X-Forwarded-User / -Email / -Preferred-Username);
            без них — 401. Bearer-токен клиента принимается как запасной путь (CLI).
  tokens  — как /mcp: нужен Bearer-токен клиента (по умолчанию, если заданы SKELCAD_TOKENS).
  none    — без входа, пользователь «constructor» (разработка; на cloud — только за списком подсетей nginx).
Точка /mcp всегда по токену, если токены заданы.
"""

from __future__ import annotations

import hmac
import os
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request

from skelcad.server.workspace import Actor

MODES = ("none", "tokens", "proxy")


@dataclass(frozen=True)
class Principal:
    name: str  # имя клиента (агент) или пользователя (человек)
    kind: str  # agent | user
    email: str | None = None
    groups: tuple[str, ...] = ()
    admin: bool = False  # группа admins в Keycloak; в режиме none — все

    @property
    def is_user(self) -> bool:
        return self.kind == "user"

    def actor(self) -> Actor:
        """Автор коммитов: человек — своим именем и почтой, агент — «SkelCAD agent (<клиент>)»."""
        if self.is_user:
            return Actor(self.name, self.email or f"{self.name}@skelcad")
        return Actor.agent(self.name)


CURRENT_PRINCIPAL: ContextVar[Principal | None] = ContextVar("skelcad_principal", default=None)


def current_actor(client: str) -> Actor:
    """Actor для пишущих инструментов: пользователь workbench из контекста запроса, иначе агент по имени клиента."""
    who = CURRENT_PRINCIPAL.get()
    return who.actor() if who and who.is_user else Actor.agent(client)


def parse_tokens(raw: str | None) -> dict[str, str]:
    """«claude-code:abc;cursor:def» -> {token: client}."""
    out = {}
    for item in (raw or "").replace(",", ";").split(";"):
        item = item.strip()
        if not item:
            continue
        name, _, token = item.partition(":")
        if not token:
            raise ValueError(f"SKELCAD_TOKENS: ожидалось «имя:токен», получено «{item[:20]}»")
        out[token.strip()] = name.strip()
    return out


def web_mode(tokens: dict[str, str]) -> str:
    mode = os.environ.get("SKELCAD_AUTH") or ("tokens" if tokens else "none")
    if mode not in MODES:
        raise ValueError(f"SKELCAD_AUTH: ожидалось {' | '.join(MODES)}, получено «{mode}»")
    return mode


def client_for(request: Request, tokens: dict[str, str]) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    given = auth[7:].strip().encode()
    for token, name in tokens.items():
        if hmac.compare_digest(given, token.encode()):
            return name
    return None


def proxy_user(request: Request) -> Principal | None:
    h = request.headers
    user = h.get("x-forwarded-preferred-username") or h.get("x-forwarded-user")
    email = h.get("x-forwarded-email")
    if not user and not email:
        return None
    groups = tuple(g.strip() for g in (h.get("x-forwarded-groups") or "").split(",") if g.strip())
    return Principal(
        name=(user or email or "").strip(),
        kind="user",
        email=(email or "").strip() or None,
        groups=groups,
        admin="admins" in groups or "/admins" in groups,
    )


def resolve(request: Request, tokens: dict[str, str], mode: str) -> Principal | None:
    """None — доступ запрещён (401)."""
    if request.url.path == "/mcp":
        if not tokens:
            return Principal("anonymous", "agent")
        name = client_for(request, tokens)
        return Principal(name, "agent") if name else None
    if tokens and (name := client_for(request, tokens)):
        return Principal(name, "agent")
    if mode == "proxy":
        return proxy_user(request)
    if mode == "tokens":
        return None if tokens else Principal("anonymous", "agent")
    return Principal("constructor", "user", admin=True)
