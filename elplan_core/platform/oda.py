"""Platformadapter til lokalisering og opsætning af ODA File Converter."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import ezdxf
from ezdxf.addons import odafc

from elplan_core.settings import load_app_settings, save_app_settings


def set_oda_exec_path(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file() or p.name.lower() != "odafileconverter.exe":
        return False
    ezdxf.options.set("odafc-addon", "win_exec_path", str(p))
    settings = load_app_settings()
    settings["oda_exec_path"] = str(p)
    save_app_settings(settings)
    return True


def detect_oda_exec_path() -> str | None:
    if os.name != "nt":
        return None
    candidates: list[Path] = []
    saved = load_app_settings().get("oda_exec_path")
    if saved:
        candidates.append(Path(saved))
    try:
        current = odafc.get_win_exec_path()
        if current:
            candidates.append(Path(current))
    except Exception:
        pass
    found_on_path = shutil.which("ODAFileConverter")
    if found_on_path:
        candidates.append(Path(found_on_path))
    roots = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        val = os.environ.get(env_name)
        if val:
            roots.append(Path(val))
    for root in roots:
        oda_root = root / "ODA"
        if oda_root.is_dir():
            try:
                candidates.extend(oda_root.glob("**/ODAFileConverter.exe"))
            except OSError:
                pass
        candidates.append(root / "ODAFileConverter" / "ODAFileConverter.exe")
        candidates.append(root / "ODA File Converter" / "ODAFileConverter.exe")
    seen = set()
    for c in candidates:
        key = str(c).lower()
        if key in seen:
            continue
        seen.add(key)
        if c.is_file():
            set_oda_exec_path(c)
            return str(c)
    return None
