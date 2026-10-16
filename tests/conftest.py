from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def bracket_dir() -> Path:
    return ROOT / "examples" / "bracket"
