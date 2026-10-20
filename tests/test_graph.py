"""Граф связей (M2.2, D27): словарь и извлечение сущностей и связей, индекс в Postgres (встроенный pgserver
или SKELCAD_TEST_DATABASE_URL), запросы окрестности / «где используется» / поиска, обновление после коммита и
сборки, HTTP и MCP, работа сервера без базы."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient

from skelcad.core.model import Project
from skelcad.core.project import ProjectDir, read_spec
from skelcad.graph import KINDS, RELATIONS, extract_project, extract_variant
from skelcad.pipeline import build_variant
from skelcad.server.app import create_app
from skelcad.server.tools import GraphOff, Tools, local_server

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory):
    url = os.environ.get("SKELCAD_TEST_DATABASE_URL")
    if url:
        yield url
        return
    pgserver = pytest.importorskip("pgserver")
    srv = pgserver.get_server(str(tmp_path_factory.mktemp("pg")))
    try:
        yield srv.get_uri()
    finally:
        srv.cleanup()


def fresh_db(pg_url: str, name: str) -> str:
    """Отдельная база на модуль/тест: серверы в тестах не затирают индекс друг друга."""
    try:
        with psycopg.connect(pg_url, autocommit=True) as c:
            c.execute(f"DROP DATABASE IF EXISTS {name}")
            c.execute(f"CREATE DATABASE {name}")
        head, _, tail = pg_url.partition("?")
        base = head.rsplit("/", 1)[0]
        return f"{base}/{name}" + (f"?{tail}" if tail else "")
    except psycopg.Error:
        return pg_url


# ---------------------------------------------------------------- извлечение (без базы)


def test_extract_project_bracket(bracket_dir):
    spec = read_spec(bracket_dir)
    spec.skeleton.interfaces[1].loads = {"Fv": 20.0}  # нагрузка через интерфейс → связь applies
    reviews = [{"id": "R1", "text": "кромка мала", "status": "open", "part": "base_plate", "variant": "A_fork"}]
    ents, rels = extract_project("bracket", spec, [{"id": "A_fork", "title": "A"}], reviews, {"state": "none"})
    refs = {e.ref: e for e in ents}
    expected = {
        "project:bracket",
        "datum:wall",
        "datum:axle_axis",
        "interface:wall",
        "interface:axle",
        "surrounding:wall_body",
        "load:Fv",
        "standard:gost",
        "variant:A_fork",
        "review:R1",
    }
    assert expected <= set(refs)
    triples = {(r.src, r.dst, r.kind) for r in rels}
    assert ("interface:wall", "datum:wall", "locates") in triples
    assert ("project:bracket", "interface:wall", "contains") in triples
    assert ("load:Fv", "interface:axle", "applies") in triples
    assert ("project:bracket", "load:Fh", "contains") in triples
    assert ("review:R1", "part:base_plate", "reviews") in triples
    assert ("review:R1", "variant:A_fork", "reviews") in triples
    assert refs["project:bracket"].data["layout"] == "none"
    assert refs["datum:wall"].name == "Лицевая плоскость стены" and "стены" in refs["datum:wall"].text
    assert all(e.kind in KINDS for e in ents) and all(r.kind in RELATIONS for r in rels)
    assert len({e.ref for e in ents}) == len(ents)  # без дублей


@pytest.fixture(scope="module")
def built(tmp_path_factory, bracket_dir) -> Path:
    out = tmp_path_factory.mktemp("out")
    build_variant(ProjectDir(bracket_dir), "A_fork", out, export=False)
    return out / "A_fork"


def test_extract_variant_bracket(built: Path):
    m = Project.model_validate(yaml.safe_load((built / "model.yaml").read_text(encoding="utf-8")))
    report = json.loads((built / "report.json").read_text(encoding="utf-8"))
    ents, rels = extract_variant("A_fork", m, report, None)
    refs = {e.ref: e for e in ents}
    assert any(r.startswith("unit:") for r in refs) and any(r.startswith("part:") for r in refs)
    assert any("/hole:" in r for r in refs)
    assert "material:St3sp" in refs
    assert any(r.startswith("item:anchor/") for r in refs)
    kinds = {r.kind for r in rels}
    assert {"contains", "mounts", "fastens", "made_of", "selects", "checks"} <= kinds
    f = next(r for r in rels if r.kind == "fastens" and "/hole:" in r.dst)
    assert f.src.startswith("fastener:") and f.dst.startswith("part:")
    mount = next(r for r in rels if r.kind == "mounts")
    assert mount.src.startswith("unit:") and mount.dst.startswith("interface:")
    part = next(e for e in ents if e.kind == "part")
    assert part.data["mass_kg"] is not None and part.data["material"] == "St3sp"
    assert all(e.kind in KINDS for e in ents) and all(r.kind in RELATIONS for r in rels)


# ---------------------------------------------------------------- индекс и запросы


@pytest.fixture(scope="module")
def srv(pg_url, tmp_path_factory):
    s = local_server(tmp_path_factory.mktemp("data"), database_url=fresh_db(pg_url, "skelcad_t1"))
    assert s.graph is not None, "граф не открылся"
    s.workspace.seed(["bracket", "pipe_support", "plate"])  # create → слушатель → индекс
    yield s
    s.graph.close()


def test_index_after_seed_and_queries(srv):
    t = Tools(srv)
    st = t.graph_stats()
    assert st["entities"] > 0 and {"bracket", "pipe_support", "plate"} <= {x["project"] for x in st["state"]}
    res = t.links("bracket", "interface:wall")
    refs = {n["ref"] for n in res["nodes"]}
    assert {"datum:wall", "project:bracket"} <= refs
    assert res["root"]["name"] and "привязан к базе" in res["summary"]
    res_in = t.links("bracket", "datum:wall", direction="in")
    assert "interface:wall" in {n["ref"] for n in res_in["nodes"]}
    res_k = t.links("bracket", "interface:wall", kinds=["contains"])
    assert "datum:wall" not in {n["ref"] for n in res_k["nodes"]}
    hits = t.search("стен")["hits"]
    assert any(h["ref"] == "surrounding:wall_body" and h["project"] == "bracket" for h in hits)
    assert t.search("wall", kind="datum", project="bracket")["hits"][0]["ref"] == "datum:wall"
    with pytest.raises(ValueError):
        t.links("bracket", "interface:wall", kinds=["bogus"])
    with pytest.raises(ValueError):
        t.search("x")


def test_index_after_build_and_where_used(srv):
    t = Tools(srv)
    t.build("bracket", "A_fork", export=False)
    res = t.links("bracket", "interface:wall", variant="A_fork")
    assert any(n["kind"] == "unit" for n in res["nodes"]) and any(e["kind"] == "mounts" for e in res["edges"])
    t.build("bracket", "B_hub", export=False)
    allv = t.links("bracket", "interface:wall")  # без варианта: узел один раз, варианты в подписи
    assert allv["summary"].count("unit:bracket") == 1 and "[A_fork, B_hub]" in allv["summary"]
    wu = t.where_used("item:anchor/M16")
    assert wu["by_project"].get("bracket", 0) > 0 and any(u["kind"] == "selects" for u in wu["uses"])
    part = t.search("plate", project="bracket", kind="part")["hits"][0]["ref"]
    near = t.links("bracket", part, variant="A_fork", hops=2)
    kinds = {n["kind"] for n in near["nodes"]}
    assert {"hole", "material", "unit"} <= kinds
    assert near["root"]["variants"] == ["A_fork"]
    # без варианта видны все варианты, где есть деталь
    assert "A_fork" in t.links("bracket", part)["root"]["variants"]


def test_index_updates_after_commit_and_reindex(srv):
    t = Tools(srv)
    text = t.files_read("bracket", "project.yaml")["content"]
    new = text.replace('name: "Лицевая плоскость стены"', 'name: "Плоскость стены (изменено)"')
    assert new != text
    t.files_write("bracket", {"project.yaml": new}, "переименована база wall", client="test")
    node = next(n for n in t.links("bracket", "datum:wall")["nodes"] if n["ref"] == "datum:wall")
    assert "изменено" in node["name"]
    r = t.reindex("bracket")
    assert r["project"]["entities"] > 0 and any(v.get("entities") for v in r["variants"])
    assert t.reindex()["projects"] == 3


def test_http_and_mcp(pg_url, tmp_path_factory, monkeypatch):
    monkeypatch.delenv("SKELCAD_TOKENS", raising=False)
    monkeypatch.delenv("SKELCAD_AGENT_TOKEN", raising=False)
    monkeypatch.setenv("SKELCAD_SEED", "bracket")
    monkeypatch.setenv("SKELCAD_AUTH", "none")
    s = local_server(tmp_path_factory.mktemp("http"), database_url=fresh_db(pg_url, "skelcad_t2"))
    with TestClient(create_app(s)) as c:
        assert c.get("/health").json()["graph"] == "ok"
        r = c.get("/api/graph/search", params={"q": "wall"})
        assert r.status_code == 200 and r.json()["hits"]
        r = c.get("/api/projects/bracket/graph/links", params={"ref": "interface:wall", "kinds": "locates"})
        assert r.status_code == 200 and any(n["ref"] == "datum:wall" for n in r.json()["nodes"])
        assert c.get("/api/projects/bracket/graph/where-used", params={"ref": "datum:wall"}).json()["uses"]
        assert c.get("/api/graph/stats").json()["entities"] > 0
        assert c.post("/api/graph/reindex", params={"project": "bracket"}).status_code == 200
        assert c.get("/api/graph/search", params={"q": "x"}).status_code == 400
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        hdr = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        names = {x["name"] for x in c.post("/mcp", json=body, headers=hdr).json()["result"]["tools"]}
        assert {"links", "where_used", "search"} <= names


def test_server_without_graph(tmp_path, monkeypatch):
    monkeypatch.delenv("SKELCAD_TOKENS", raising=False)
    monkeypatch.setenv("SKELCAD_SEED", "")
    s = local_server(tmp_path)
    assert s.graph is None and s.indexer is None
    with pytest.raises(GraphOff):
        Tools(s).search("wall")
    with TestClient(create_app(s)) as c:
        assert c.get("/health").json()["graph"] == "off"
        assert c.get("/api/graph/search", params={"q": "wall"}).status_code == 503
