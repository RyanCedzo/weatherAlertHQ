"""Optional save/load of raw API JSON so Stage 1 can be rerun offline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def save_fixture(data: Dict[str, Any], name: str, fixtures_dir: Path = DEFAULT_FIXTURES_DIR) -> Path:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    path = fixtures_dir / f"{name}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


def load_fixture(name: str, fixtures_dir: Path = DEFAULT_FIXTURES_DIR) -> Dict[str, Any]:
    path = fixtures_dir / f"{name}.json"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
