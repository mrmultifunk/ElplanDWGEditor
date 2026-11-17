"""Fælles normalisering af visuelle domæneværdier."""

from __future__ import annotations

from elplan_core.constants import DEFAULT_SYMBOL_COLOR


def normalize_hex_color(value: str, fallback: str = DEFAULT_SYMBOL_COLOR) -> str:
    """Returnér en gyldig #RRGGBB-farve."""
    txt = str(value or "").strip()
    if len(txt) == 7 and txt.startswith("#"):
        try:
            int(txt[1:], 16)
            return txt.lower()
        except ValueError:
            pass
    return fallback.lower()
