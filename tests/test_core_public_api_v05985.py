from __future__ import annotations

import inspect
import json
from pathlib import Path

import core_logic as core


ROOT = Path(__file__).resolve().parents[1]


def test_core_logic_public_api_names_and_signatures_are_preserved():
    manifest = json.loads(
        (ROOT / "tests" / "golden" / "core_public_api.json").read_text(encoding="utf-8")
    )
    assert manifest["count"] == len(manifest["symbols"])
    for symbol in manifest["symbols"]:
        name = symbol["name"]
        assert hasattr(core, name), f"core_logic mangler kompatibilitetsnavnet {name}"
        value = getattr(core, name)
        if symbol["kind"] == "class":
            assert inspect.isclass(value), f"{name} er ikke længere en klasse"
        elif symbol["kind"] == "function":
            # Enkelte facadefunktioner er pakket i functools.lru_cache og er
            # derfor callable wrappers frem for rene Python-funktioner.
            assert callable(value) and not inspect.isclass(value), f"{name} er ikke længere kaldbar"
        else:
            continue
        assert str(inspect.signature(value)) == symbol["signature"], name
