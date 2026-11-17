"""Maskinlokale programindstillinger uden GUI-afhængigheder."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def _settings_file() -> Path:
    override = str(os.environ.get("ELPLAN_USER_DATA_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser() / "settings.json"
    root = os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / "ElplanDWGEditor" / "settings.json"


def _recovery_file() -> Path:
    return _settings_file().parent / "recovery.elplan.json"


def load_app_settings() -> dict:
    path = _settings_file()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def save_app_settings(data: dict) -> None:
    """Gem brugerindstillinger atomisk, så en afbrudt skrivning ikke ødelægger filen."""
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def normalize_appearance_mode(value) -> str:
    """Normalize the machine-local UI appearance preference.

    Existing installations remain light until the user explicitly chooses dark
    or system mode; this preserves the historical behaviour of the application.
    """
    mode=str(value or "light").strip().lower()
    aliases={
        "lys":"light", "light":"light",
        "mørk":"dark", "mork":"dark", "dark":"dark",
        "system":"system", "windows":"system", "auto":"system", "følg windows":"system", "folg windows":"system",
    }
    return aliases.get(mode,"light")


def normalize_dark_canvas(value, default: bool = True) -> bool:
    """Normalize whether dark appearance should also use a dark CAD canvas."""
    if value is None:
        return bool(default)
    if isinstance(value,str):
        text=value.strip().lower()
        if text in {"0","false","nej","no","off"}: return False
        if text in {"1","true","ja","yes","on"}: return True
    return bool(value)


def normalize_recent_project_paths(records, limit: int = 8, existing_only: bool = False) -> list[str]:
    """Normalisér listen over senest anvendte projektfiler.

    Listen er maskinlokal og må derfor gerne indeholde absolutte stier. Dubletter
    fjernes uden at ændre rækkefølgen, og manglende filer kan filtreres fra, når
    menuen vises.
    """
    try:
        max_items=max(1,int(limit))
    except (TypeError,ValueError):
        max_items=8
    source=records if isinstance(records,(list,tuple)) else []
    out=[]; seen=set()
    for raw in source:
        value=str(raw or "").strip()
        if not value:
            continue
        p=Path(value).expanduser()
        try:
            p=p.resolve(strict=False)
        except (OSError,RuntimeError):
            p=Path(os.path.abspath(str(p)))
        key=os.path.normcase(str(p))
        if key in seen:
            continue
        if existing_only and not p.is_file():
            continue
        seen.add(key); out.append(str(p))
        if len(out)>=max_items:
            break
    return out


def normalize_cable_visual_settings(data: dict | None) -> dict:
    """Normalize and one-time repair 0.44.0-0.44.3 cable view settings.

    Those versions connected the cable-route checkbox before restoring the
    parallel-lane controls.  Restoring ``cable_snap_routes=True`` therefore
    emitted a signal while ``cable_parallel_lanes`` still had Qt's default
    ``False`` value, and that false value was immediately persisted.  The
    visual lane engine then correctly calculated nothing because its gap was
    intentionally set to zero.

    The marker makes the repair one-shot.  From 0.44.5 onward the controls are
    restored with signals blocked, so subsequent user choices are preserved.
    """
    out=dict(data or {})
    marker='cable_visual_settings_init_fixed_0444'
    if not bool(out.get(marker,False)):
        out['cable_parallel_lanes']=True
        out['cable_lane_gap_px']=10
        out['cable_bundle_badges']=True
        out['cable_focus_related']=True
        out[marker]=True
    try:
        out['cable_lane_gap_px']=max(5,min(18,int(out.get('cable_lane_gap_px',10))))
    except Exception:
        out['cable_lane_gap_px']=10
    out['cable_parallel_lanes']=bool(out.get('cable_parallel_lanes',True))
    out['cable_bundle_badges']=bool(out.get('cable_bundle_badges',True))
    out['cable_focus_related']=bool(out.get('cable_focus_related',True))
    return out
