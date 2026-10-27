from __future__ import annotations

"""Small, dependency-free helpers for robust local persistence."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: str | Path, text: str) -> Path:
    """Atomically replace *path* with UTF-8 text on the same filesystem."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target


def read_json(path: str | Path, default: Any = None) -> Any:
    """Read UTF-8 JSON and return *default* for missing or invalid files."""
    target = Path(path)
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return default


def atomic_write_json(path: str | Path, payload: Any, *, indent: int = 2) -> Path:
    text = json.dumps(payload, ensure_ascii=False, indent=indent, allow_nan=False)
    return atomic_write_text(path, text)
