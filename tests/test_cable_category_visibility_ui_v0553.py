from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_v0553():
    assert APP_VERSION == core.APP_VERSION == "0.59.84"


def test_cable_category_menu_has_explicit_visibility_state():
    source = Path("qt_workspace.py").read_text(encoding="utf-8")
    assert "_cable_category_menu_text" in source
    assert "'VIST' if visible else 'SKJULT'" in source
    assert "Kabelkategorier ({visible_count}/{len(categories)} vist)" in source
    assert "_cable_category_menu_toggled" in source
