from __future__ import annotations

"""Compatibility module for pre-Qt integrations.

The active application imports :mod:`core_logic` directly.  Older scripts that
still import ``legacy_core`` keep access to the core API without forcing the
large Tkinter editor to load.  ``ElplanEditor`` is imported lazily only if an
old integration explicitly asks for it.
"""

import core_logic as _core
from core_logic import *  # noqa: F401,F403 - intentional compatibility export

__all__ = [name for name in dir(_core) if not name.startswith("_")] + ["ElplanEditor"]


def __getattr__(name: str):
    if name == "ElplanEditor":
        from elplan_legacy.legacy_tk_app import ElplanEditor
        return ElplanEditor
    try:
        return getattr(_core, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__():
    return sorted(set(globals()) | set(dir(_core)) | {"ElplanEditor"})
