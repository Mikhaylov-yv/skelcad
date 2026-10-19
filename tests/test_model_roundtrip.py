"""Модель сериализуется в YAML и читается обратно без потерь; JSON Schema строится."""

from pathlib import Path

import yaml

from skelcad.core.model import Project, text
from skelcad.core.project import ProjectDir, ProjectSpec, VariantSpec, save_model


def test_roundtrip_bracket(bracket_dir: Path, tmp_path: Path):
    m = ProjectDir(bracket_dir).resolve("B_hub")
    f = tmp_path / "model.yaml"
    save_model(m, f)
    back = Project.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
    assert m.layout is not None and back.layout is None  # состояние компоновки в model.yaml не пишется
    assert back == m.model_copy(update={"layout": None})
    assert back.unit("bracket").part("hub").kind == "tube"
    assert back.skeleton.interface("axle").body is not None


def test_text_helper():
    assert text("Плита") == "Плита"
    assert text({"ru": "Плита", "en": "Plate"}, "en") == "Plate"
    assert text({"en": "Plate"}, "ru") == "Plate"


def test_json_schema():
    for model in (ProjectSpec, VariantSpec, Project):
        s = model.model_json_schema()
        assert s["title"] == model.__name__ and "properties" in s
