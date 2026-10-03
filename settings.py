from __future__ import annotations

import json
import os
from pathlib import Path

THEMES = ("system", "light", "dark")
THRESHOLD_MIN, THRESHOLD_MAX = 50, 100

DEFAULTS = {"theme": "system", "last_root": "", "threshold": 85}


def settings_path() -> Path:
    base = os.environ.get("APPDATA")
    return (Path(base) if base else Path.home()) / "ModDeleter" / "settings.json"


def load(path: str | Path | None = None) -> dict:
    result = dict(DEFAULTS)
    try:
        raw = json.loads(Path(path or settings_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    if not isinstance(raw, dict):
        return result
    if raw.get("theme") in THEMES:
        result["theme"] = raw["theme"]
    if isinstance(raw.get("last_root"), str):
        result["last_root"] = raw["last_root"]
    threshold = raw.get("threshold")
    if isinstance(threshold, int) and not isinstance(threshold, bool):
        result["threshold"] = max(THRESHOLD_MIN, min(THRESHOLD_MAX, threshold))
    return result


def save(data: dict, path: str | Path | None = None) -> bool:
    target = Path(path or settings_path())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True
