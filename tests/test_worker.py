"""Воркер: таймаут, запрет записи вне out/, файловая очередь."""

from __future__ import annotations

import threading
import time

import pytest

from skelcad.server.jobs import JobError, Limits, QueueRunner, SubprocessRunner, queue_loop
from skelcad.server.tools import Tools, local_server
from skelcad.worker import _select


@pytest.fixture(scope="module")
def tools(tmp_path_factory) -> Tools:
    srv = local_server(tmp_path_factory.mktemp("data"))
    srv.workspace.seed(["bracket"])
    return Tools(srv)


def _patch_generator(tools: Tools, name: str, extra: str) -> None:
    tools.project_create(name, "bracket", client="test")
    gen = tools.files_read(name, "generators/bracket.py")["content"]
    tools.files_write(name, {"generators/bracket.py": gen + "\n" + extra}, f"правка генератора {name}")


def test_select():
    d = {"a": [{"id": "x", "v": 1}, {"id": "y", "v": 2}], "b": {"c": 3}}
    assert _select(d, "b.c") == 3
    assert _select(d, "a[1].v") == 2
    assert _select(d, "a[id=x]")["v"] == 1
    with pytest.raises(KeyError):
        _select(d, "a[id=z]")


def test_timeout_kills_hung_generator(tools: Tools):
    _patch_generator(tools, "hang", "import time\n_g = generate\ndef generate(p, params, ctx):\n    time.sleep(60)\n")
    tools.srv.runner = SubprocessRunner(Limits(timeout_s=4, cpu_s=30, mem_mb=8192))
    with pytest.raises(JobError, match="лимит времени"):
        tools.model_query("hang", "A_fork")
    tools.srv.runner = SubprocessRunner()


def test_guard_forbids_writes_outside_out(tools: Tools):
    _patch_generator(
        tools,
        "writer",
        "from pathlib import Path\n_g = generate\n"
        "def generate(p, params, ctx):\n"
        "    Path(__file__).with_name('evil.txt').write_text('x')\n"
        "    return _g(p, params, ctx)\n",
    )
    with pytest.raises(JobError, match="запрещена"):
        tools.model_query("writer", "A_fork")
    assert not (tools.ws.path("writer") / "generators" / "evil.txt").exists()


def test_guard_forbids_subprocess(tools: Tools):
    _patch_generator(
        tools, "spawn", "import subprocess\n_g = generate\ndef generate(p, params, ctx):\n    subprocess.run(['ls'])\n"
    )
    with pytest.raises(JobError, match="запуск процессов"):
        tools.model_query("spawn", "A_fork")


def test_queue_runner_roundtrip(tools: Tools, tmp_path):
    q = tmp_path / "jobs"
    with pytest.raises(JobError, match="не запущен"):
        QueueRunner(q).run("query", {})
    th = threading.Thread(target=queue_loop, args=(q,), kwargs={"cpu_s": 60, "mem_mb": 8192}, daemon=True)
    th.start()
    runner = QueueRunner(q, Limits(timeout_s=120))
    for _ in range(50):
        if runner.alive():
            break
        time.sleep(0.1)
    res = runner.run("query", {"project_dir": str(tools.ws.path("bracket")), "variant": "A_fork", "path": "summary"})
    assert "base_plate" in res["parts"]
    with pytest.raises(JobError, match="нет ключа"):
        runner.run("query", {"project_dir": str(tools.ws.path("bracket")), "variant": "A_fork", "path": "zzz"})
    assert not list((q / "new").glob("*.json")) and not list((q / "claimed").glob("*.json"))
