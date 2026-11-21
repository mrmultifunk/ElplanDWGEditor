from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

import core_logic
import legacy_core
from elplan_catalog import predefined_articles_data
from elplan_legacy import core_api
from elplan_shared.resources import APP_ROOT


ROOT = Path(__file__).resolve().parents[1]


def test_entry_points_and_assets_stay_in_the_repository_root():
    assert {path.name for path in ROOT.glob("*.py")} == {"main.py", "core_logic.py", "legacy_core.py"}
    assert APP_ROOT == ROOT
    assert (APP_ROOT / "assets" / "app_icon.png").is_file()
    assert (APP_ROOT / "predefined_articles.json").is_file()
    # Catalogue fallback must be packaged as Python, not loaded via a second JSON path.
    assert predefined_articles_data.ARTICLES


def test_compatibility_keeps_public_and_private_exports_without_loading_tk():
    assert core_logic.Placement is legacy_core.Placement is core_api.Placement
    assert core_logic._arc_points is legacy_core._arc_points is core_api._arc_points
    frontend = ModuleType("elplan_legacy.legacy_tk_app")
    frontend.ElplanEditor = object()
    with patch.dict(sys.modules, {frontend.__name__: frontend}):
        assert legacy_core.ElplanEditor is frontend.ElplanEditor
