"""Постановка задач рабочему процессу.

Две реализации одного интерфейса `Runner.run(op, args, timeout) -> result`:
  SubprocessRunner — подпроцесс `python -I -m skelcad.worker --once` здесь же (разработка, тесты, CLI);
  QueueRunner      — файловая очередь на общем томе: сервер кладёт <id>.json в jobs/new/,
                     контейнер-воркер (`skelcad worker --queue`) забирает, исполняет в подпроцессе
                     с лимитами и кладёт ответ в jobs/done/<id>.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class JobError(RuntimeError):
    """Задача не выполнена: ошибка кода проекта, таймаут или сбой воркера."""


@dataclass
class Limits:
    timeout_s: int = int(os.environ.get("SKELCAD_JOB_TIMEOUT_S", "180"))
    cpu_s: int = int(os.environ.get("SKELCAD_LIMIT_CPU_S", "170"))
    mem_mb: int = int(os.environ.get("SKELCAD_LIMIT_MEM_MB", "8192"))


def _raise_from(response: dict) -> Any:
    if response.get("ok"):
        return response["result"]
    msg = response.get("error", "ошибка воркера")
    tb = response.get("traceback")
    raise JobError(f"{msg}\n{tb}" if tb else msg)


def run_subprocess(request: dict, limits: Limits, cwd: Path | None = None) -> dict:
    """Запустить воркер подпроцессом с лимитами и вернуть его ответ (dict)."""
    cmd = [
        sys.executable,
        "-I",
        "-m",
        "skelcad.worker",
        "--once",
        "--cpu",
        str(limits.cpu_s),
        "--mem",
        str(limits.mem_mb),
    ]
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
    }
    for k in ("VIRTUAL_ENV", "PYTHONPATH", "SSL_CERT_FILE"):
        if k in os.environ:
            env[k] = os.environ[k]
    try:
        p = subprocess.run(
            cmd,
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=limits.timeout_s,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"превышен лимит времени {limits.timeout_s} с — задача прервана"}
    if not p.stdout.strip():
        tail = (p.stderr or "")[-2000:]
        return {"ok": False, "error": f"воркер завершился без ответа (код {p.returncode})", "traceback": tail}
    try:
        resp = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "воркер вернул не JSON", "traceback": p.stdout[-2000:]}
    if p.stderr.strip():
        resp["stderr"] = p.stderr[-4000:]
    return resp


class SubprocessRunner:
    def __init__(self, limits: Limits | None = None):
        self.limits = limits or Limits()

    def run(self, op: str, args: dict, timeout_s: int | None = None) -> Any:
        lim = Limits(timeout_s or self.limits.timeout_s, self.limits.cpu_s, self.limits.mem_mb)
        return _raise_from(run_subprocess({"op": op, "args": args}, lim))


class QueueRunner:
    def __init__(self, queue_dir: Path, limits: Limits | None = None, poll_s: float = 0.2):
        self.q = Path(queue_dir)
        self.limits = limits or Limits()
        self.poll_s = poll_s
        for d in ("new", "claimed", "done"):
            (self.q / d).mkdir(parents=True, exist_ok=True)

    def alive(self, max_age_s: float = 30) -> bool:
        hb = self.q / "heartbeat"
        return hb.exists() and time.time() - hb.stat().st_mtime < max_age_s

    def run(self, op: str, args: dict, timeout_s: int | None = None) -> Any:
        timeout_s = timeout_s or self.limits.timeout_s
        if not self.alive():
            raise JobError(f"воркер не запущен или не отвечает (нет heartbeat в {self.q}); проверьте контейнер worker")
        jid = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        tmp = self.q / "new" / f".{jid}.json.tmp"
        req = self.q / "new" / f"{jid}.json"
        tmp.write_text(
            json.dumps({"op": op, "args": args, "timeout_s": timeout_s}, ensure_ascii=False), encoding="utf-8"
        )
        tmp.rename(req)  # атомарно: воркер не увидит недописанный файл
        done = self.q / "done" / f"{jid}.json"
        deadline = time.monotonic() + timeout_s + 30  # воркер сам прерывает по timeout_s; запас на очередь
        while time.monotonic() < deadline:
            if done.exists():
                try:
                    resp = json.loads(done.read_text(encoding="utf-8"))
                finally:
                    done.unlink(missing_ok=True)
                return _raise_from(resp)
            time.sleep(self.poll_s)
        req.unlink(missing_ok=True)
        raise JobError(f"воркер не ответил за {timeout_s} с (очередь {self.q}); проверьте, запущен ли контейнер worker")


def queue_loop(queue_dir: Path, cpu_s: int | None = None, mem_mb: int | None = None) -> int:
    """Цикл контейнера-воркера: забирать задачи из new/, исполнять подпроцессом, отвечать в done/."""
    q = Path(queue_dir)
    for d in ("new", "claimed", "done"):
        (q / d).mkdir(parents=True, exist_ok=True)
    # задачи, застрявшие в claimed/ после падения воркера, возвращаем в очередь
    for f in (q / "claimed").glob("*.json"):
        f.rename(q / "new" / f.name)
    print(f"worker: очередь {q}, лимиты cpu={cpu_s}s mem={mem_mb}MB", file=sys.stderr, flush=True)
    hb, last_hb = q / "heartbeat", 0.0
    while True:
        if time.time() - last_hb > 5:
            hb.touch()
            last_hb = time.time()
        files = sorted(p for p in (q / "new").glob("*.json") if not p.name.startswith("."))
        if not files:
            time.sleep(0.3)
            continue
        src = files[0]
        claimed = q / "claimed" / src.name
        try:
            src.rename(claimed)
        except FileNotFoundError:
            continue  # забрал другой воркер
        try:
            request = json.loads(claimed.read_text(encoding="utf-8"))
            lim = Limits(
                timeout_s=int(request.get("timeout_s") or Limits().timeout_s),
                cpu_s=cpu_s or Limits().cpu_s,
                mem_mb=mem_mb or Limits().mem_mb,
            )
            t0 = time.monotonic()
            resp = run_subprocess({"op": request["op"], "args": request["args"]}, lim)
            print(
                f"worker: {src.stem} {request['op']} ok={resp.get('ok')} {time.monotonic() - t0:.1f}s",
                file=sys.stderr,
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            resp = {"ok": False, "error": f"сбой воркера: {type(e).__name__}: {e}"}
        tmp = q / "done" / f".{src.name}.tmp"
        tmp.write_text(json.dumps(resp, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.rename(q / "done" / src.name)
        claimed.unlink(missing_ok=True)


def make_runner() -> SubprocessRunner | QueueRunner:
    """Runner по окружению: SKELCAD_JOBS=<папка очереди> -> QueueRunner, иначе подпроцесс."""
    qdir = os.environ.get("SKELCAD_JOBS")
    return QueueRunner(Path(qdir)) if qdir else SubprocessRunner()
