"""Параметры варианта: плоские поля с источником, правка YAML с сохранением комментариев, приведение типов."""

from __future__ import annotations

import yaml

from skelcad.server import params as P

VARIANT = """id: A_fork
title: "A. Вилка"
params:
  topology: fork
  members:
    gap: 100             # расстояние между щеками в свету
    cheek_thickness: 12
  base_plate: {thickness: 16, edge: 45, corner_radius: 10}   # плита
assumptions:
  - "Расточка после сварки."
"""


def test_fields_merge_and_source():
    f = P.fields({"material": "St3sp", "members": {"gap": 80, "lug": 25}}, {"members": {"gap": 100}})
    by = {x["path"]: x for x in f}
    assert by["members.gap"] == {"path": "members.gap", "value": 100, "type": "number", "source": "variant"}
    assert by["members.lug"]["source"] == "project" and by["material"]["type"] == "string"


def test_apply_keeps_comments_block_and_flow():
    new = P.apply_params(VARIANT, {"members.gap": 120, "base_plate.edge": 50, "topology": "fork2"})
    assert "# расстояние между щеками в свету" in new and "# плита" in new
    d = yaml.safe_load(new)["params"]
    assert d["members"]["gap"] == 120 and d["base_plate"]["edge"] == 50 and d["topology"] == "fork2"
    assert d["base_plate"]["thickness"] == 16 and d["members"]["cheek_thickness"] == 12
    assert "assumptions" in new and "Расточка" in new


def test_apply_new_key_falls_back_to_dump():
    new = P.apply_params(VARIANT, {"members.lug_ring": 30})
    d = yaml.safe_load(new)
    assert d["params"]["members"]["lug_ring"] == 30 and d["params"]["members"]["gap"] == 100
    assert d["assumptions"] == ["Расточка после сварки."]


def test_coerce_types():
    f = [{"path": "a", "type": "number"}, {"path": "b", "type": "string"}, {"path": "c", "type": "boolean"}]
    assert P.coerce(f, {"a": "12", "b": "M20", "c": "true"}) == {"a": 12, "b": "M20", "c": True}
    assert P.coerce(f, {"a": "12,5"}) == {"a": 12.5}
    try:
        P.coerce(f, {"a": "abc"})
    except ValueError as e:
        assert "число" in str(e)
    else:
        raise AssertionError("ожидалась ошибка")
