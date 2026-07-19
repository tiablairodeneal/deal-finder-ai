from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CRITERIA_PATH = Path("acquisition_criteria.json")


def load_criteria(path: str | Path = DEFAULT_CRITERIA_PATH) -> dict[str, Any]:
    criteria_path = Path(path)
    with criteria_path.open("r", encoding="utf-8") as file:
        return json.load(file)

