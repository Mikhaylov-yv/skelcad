"""Провайдеры модели для встроенного агента (D29): настраиваются администратором в рабочем месте, хранятся в
`<data>/providers.json`. Ключи API шифруются (Fernet) ключом `SKELCAD_SECRET_KEY`; без него файл хранится открытым
с правами 0600 и интерфейс предупреждает. Ключ наружу не отдаётся: API показывает «задан» и последние 4 знака.

Запись: {id, title, kind: openai | claude-code, base_url, model, models: [...], key_enc | key, key_tail, created,
created_by, updated, updated_by}; `default` — id провайдера по умолчанию. Контейнер агента читает тот же файл (общий том
/data) и расшифровывает тем же `SKELCAD_SECRET_KEY`; если провайдеров нет — переменные SKELCAD_LLM_* (старый путь).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}$")
KINDS = ("openai", "claude-code")
PRESETS = [
    {
        "id": "openrouter", "title": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
        "model": "anthropic/claude-sonnet-4.5",
    },
    {"id": "openai", "title": "OpenAI", "base_url": "https://api.openai.com/v1", "model": ""},
    {"id": "deepseek", "title": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    {
        "id": "litellm", "title": "LiteLLM (этот хост, :4000)", "base_url": "http://host.docker.internal:4000/v1",
        "model": "",
    },
    {
        "id": "ollama", "title": "Ollama (этот хост, :11434)", "base_url": "http://host.docker.internal:11434/v1",
        "model": "",
    },
]  # fmt: skip
TEST_PROMPT = "Ответь одним словом: ок"


class ProviderError(ValueError):
    pass


# ---------------------------------------------------------------- шифрование ключей


def _fernet():
    secret = os.environ.get("SKELCAD_SECRET_KEY") or ""
    if not secret:
        return None
    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))


def secure() -> bool:
    """Задан ли SKELCAD_SECRET_KEY (ключи провайдеров шифруются)."""
    return _fernet() is not None


def encrypt_key(key: str) -> dict[str, str]:
    f = _fernet()
    return {"key_enc": f.encrypt(key.encode("utf-8")).decode("ascii")} if f else {"key": key}


def decrypt_key(rec: dict) -> str:
    if rec.get("key_enc"):
        f = _fernet()
        if f is None:
            raise ProviderError("ключ провайдера зашифрован, а SKELCAD_SECRET_KEY не задан — задайте тот же ключ")
        try:
            return f.decrypt(rec["key_enc"].encode("ascii")).decode("utf-8")
        except Exception as e:  # noqa: BLE001
            raise ProviderError("ключ провайдера не расшифровался: SKELCAD_SECRET_KEY другой") from e
    return str(rec.get("key") or "")


def is_openrouter(base_url: str) -> bool:
    return "openrouter.ai" in (base_url or "")


# ---------------------------------------------------------------- хранилище


class ProviderStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._mtime: float | None = None
        self._data: dict = {"providers": {}, "default": None}

    def _load(self) -> dict:
        try:
            m = self.path.stat().st_mtime
        except FileNotFoundError:
            self._data, self._mtime = {"providers": {}, "default": None}, None
            return self._data
        if m != self._mtime:
            try:
                d = json.loads(self.path.read_text(encoding="utf-8")) or {}
            except ValueError:
                d = {}
            self._data = {"providers": d.get("providers") or {}, "default": d.get("default")}
            self._mtime = m
        return self._data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        self._mtime = None

    @staticmethod
    def _public(pid: str, rec: dict, default: str | None) -> dict:
        return {
            "id": pid,
            "title": rec.get("title") or pid,
            "kind": rec.get("kind") or "openai",
            "base_url": rec.get("base_url") or "",
            "model": rec.get("model") or "",
            "models": list(rec.get("models") or []),
            "has_key": bool(rec.get("key_enc") or rec.get("key")),
            "key_tail": rec.get("key_tail") or "",
            "default": pid == default,
            "created": rec.get("created"),
            "created_by": rec.get("created_by"),
            "updated": rec.get("updated"),
            "updated_by": rec.get("updated_by"),
        }

    def list(self) -> list[dict]:
        d = self._load()
        return [self._public(pid, rec, d.get("default")) for pid, rec in sorted(d["providers"].items())]

    def get(self, pid: str) -> dict:
        d = self._load()
        if pid not in d["providers"]:
            raise ProviderError(f"нет провайдера «{pid}»; есть: {', '.join(sorted(d['providers'])) or 'ничего'}")
        return self._public(pid, d["providers"][pid], d.get("default"))

    def default_id(self) -> str | None:
        d = self._load()
        if d.get("default") in d["providers"]:
            return d["default"]
        return next(iter(sorted(d["providers"])), None)

    def upsert(self, body: dict, who: str) -> dict:
        """Создать или изменить провайдера. Ключ не прислали — старый остаётся; прислали — заменяется."""
        pid = str(body.get("id") or "").strip().lower()
        if not ID_RE.match(pid):
            raise ProviderError("id провайдера: строчные латинские буквы, цифры, «-», «_», «.», до 40 символов")
        kind = str(body.get("kind") or "openai")
        if kind not in KINDS:
            raise ProviderError(f"kind: ожидалось {' | '.join(KINDS)}")
        base_url = str(body.get("base_url") or "").strip().rstrip("/")
        if kind == "openai" and not re.match(r"^https?://[^\s/]+", base_url):
            raise ProviderError("base_url: адрес OpenAI-совместимого API, например https://openrouter.ai/api/v1")
        model = str(body.get("model") or "").strip()
        models = [str(m).strip() for m in (body.get("models") or []) if str(m).strip()]
        if model and model not in models:
            models.insert(0, model)
        d = self._load()
        data = {"providers": dict(d["providers"]), "default": d.get("default")}
        old = dict(data["providers"].get(pid) or {})
        now = datetime.now(tz=UTC).isoformat(timespec="seconds")
        rec = {
            "title": str(body.get("title") or old.get("title") or pid).strip(),
            "kind": kind,
            "base_url": base_url,
            "model": model,
            "models": models[:400],
            "created": old.get("created") or now,
            "created_by": old.get("created_by") or who,
            "updated": now,
            "updated_by": who,
        }
        key = body.get("key")
        if key is not None and str(key).strip():
            key = str(key).strip()
            rec.update(encrypt_key(key))
            rec["key_tail"] = key[-4:]
        else:
            for k in ("key", "key_enc", "key_tail"):
                if old.get(k):
                    rec[k] = old[k]
        data["providers"][pid] = rec
        if not data.get("default") or data["default"] not in data["providers"]:
            data["default"] = pid
        self._save(data)
        return self.get(pid)

    def delete(self, pid: str) -> None:
        d = self._load()
        if pid not in d["providers"]:
            raise ProviderError(f"нет провайдера «{pid}»")
        data = {"providers": dict(d["providers"]), "default": d.get("default")}
        del data["providers"][pid]
        if data["default"] == pid:
            data["default"] = next(iter(sorted(data["providers"])), None)
        self._save(data)

    def set_default(self, pid: str) -> dict:
        d = self._load()
        if pid not in d["providers"]:
            raise ProviderError(f"нет провайдера «{pid}»")
        self._save({"providers": dict(d["providers"]), "default": pid})
        return self.get(pid)

    def resolve(self, pid: str | None = None, model: str | None = None) -> dict | None:
        """Провайдер для запуска задачи: {id, title, kind, base_url, model, api_key} с расшифрованным ключом;
        None — провайдеров нет (агент берёт переменные окружения)."""
        d = self._load()
        pid = pid or self.default_id()
        if not pid:
            return None
        rec = d["providers"].get(pid)
        if rec is None:
            raise ProviderError(f"нет провайдера «{pid}»; есть: {', '.join(sorted(d['providers'])) or 'ничего'}")
        return {
            "id": pid,
            "title": rec.get("title") or pid,
            "kind": rec.get("kind") or "openai",
            "base_url": rec.get("base_url") or "",
            "model": (model or "").strip() or rec.get("model") or "",
            "api_key": decrypt_key(rec),
        }

    def key_for(self, pid: str) -> str:
        d = self._load()
        if pid not in d["providers"]:
            raise ProviderError(f"нет провайдера «{pid}»")
        return decrypt_key(d["providers"][pid])


# ---------------------------------------------------------------- проверка и список моделей (сеть)


def _client(api_key: str, base_url: str, timeout: float = 60.0):
    import httpx

    headers = {"Authorization": f"Bearer {api_key or 'none'}"}
    if is_openrouter(base_url):
        headers["X-Title"] = "SkelCAD"
    return httpx.Client(timeout=timeout, headers=headers)


def _raise_http(r, what: str) -> None:
    if r.status_code >= 400:
        text = r.text[:300].replace("\n", " ")
        hint = ""
        if r.status_code == 401:
            hint = " — ключ не принят"
        elif r.status_code == 404:
            hint = " — проверьте base_url (обычно заканчивается на /v1) и имя модели"
        raise ProviderError(f"{what}: провайдер ответил {r.status_code}{hint}: {text}")


def fetch_models(base_url: str, api_key: str) -> list[dict]:
    """GET {base_url}/models → [{id, name?, prompt?, completion?}] (цены за 1M токенов, если провайдер их отдаёт)."""
    import httpx

    base_url = (base_url or "").rstrip("/")
    try:
        with _client(api_key, base_url, timeout=30.0) as c:
            r = c.get(base_url + "/models")
    except httpx.HTTPError as e:
        raise ProviderError(f"список моделей: {type(e).__name__}: {e}") from e
    _raise_http(r, "список моделей")
    try:
        data = r.json()
    except ValueError as e:
        raise ProviderError("список моделей: ответ не JSON") from e
    items = data.get("data") if isinstance(data, dict) else data
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        rec: dict[str, Any] = {"id": str(it["id"])}
        if it.get("name"):
            rec["name"] = str(it["name"])
        pr = it.get("pricing") if isinstance(it.get("pricing"), dict) else None
        if pr:
            try:  # OpenRouter: цена за токен → за 1M токенов
                rec["prompt"] = round(float(pr.get("prompt", 0)) * 1e6, 3)
                rec["completion"] = round(float(pr.get("completion", 0)) * 1e6, 3)
            except (TypeError, ValueError):
                pass
        out.append(rec)
    out.sort(key=lambda x: x["id"])
    return out


def test_chat(base_url: str, api_key: str, model: str) -> dict:
    """Короткий запрос к модели: время ответа, текст, токены и стоимость (если провайдер отдаёт)."""
    import httpx

    base_url = (base_url or "").rstrip("/")
    if not model:
        raise ProviderError("проверка: укажите модель")
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 16,
    }
    if is_openrouter(base_url):
        body["usage"] = {"include": True}
    t0 = time.monotonic()
    try:
        with _client(api_key, base_url, timeout=60.0) as c:
            r = c.post(base_url + "/chat/completions", json=body)
    except httpx.HTTPError as e:
        raise ProviderError(f"проверка: {type(e).__name__}: {e}") from e
    _raise_http(r, "проверка")
    try:
        data = r.json()
        reply = (data["choices"][0]["message"].get("content") or "").strip()
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ProviderError(f"проверка: неожиданный ответ: {r.text[:200]}") from e
    usage = data.get("usage") or {}
    return {
        "ok": True,
        "model": data.get("model") or model,
        "reply": reply[:200],
        "seconds": round(time.monotonic() - t0, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "cost": response_cost(usage, r.headers),
    }


def response_cost(usage: dict, headers) -> float | None:
    """Стоимость ответа: OpenRouter кладёт usage.cost (при usage.include), LiteLLM — заголовок
    x-litellm-response-cost."""
    for raw in (usage.get("cost"), headers.get("x-litellm-response-cost") if headers is not None else None):
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def env_fallback() -> dict:
    """Что агент возьмёт из окружения, если провайдеров в файле нет (старый путь через compose)."""
    return {
        "base_url": os.environ.get("SKELCAD_LLM_BASE_URL") or "",
        "model": os.environ.get("SKELCAD_LLM_MODEL") or "",
        "has_key": bool(os.environ.get("SKELCAD_LLM_API_KEY")),
        "runner": os.environ.get("SKELCAD_AGENT_RUNNER") or "openai",
    }
