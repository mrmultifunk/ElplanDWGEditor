from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_v0561_version_and_category_chips():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"
    visual = (ROOT / "qt_visual_workspace.py").read_text(encoding="utf-8")
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert "class CableCategoryStrip" in visual
    assert "cableCategoryChip" in visual
    assert "categoryVisible" in visual
    assert "visibilityChanged" in visual
    assert "_refresh_cable_category_strip" in visual
    assert "QFrame#cableCategoryStrip" in theme
    assert "QToolButton#cableCategoryChip" in theme
    assert 'if hasattr(self,"_refresh_cable_category_strip")' in app


def test_cable_routes_have_graphical_flow_tab():
    source = (ROOT / "qt_cable_routes.py").read_text(encoding="utf-8")
    assert "class CableRouteFlowWidget" in source
    assert 'self.tabs.addTab(flow_page, "Flow")' in source
    assert "path.cubicTo" in source
    assert "routeSelected" in source
    assert "Klik på en node" in source
    assert "self.flow.set_groups(self._filtered_groups)" in source


def test_pl_wiring_has_physical_mounting_visuals_and_neutral_start_copy():
    source = (ROOT / "qt_pl_box.py").read_text(encoding="utf-8")
    for token in (
        "PL LOFTDÅSE · MONTAGESIDE",
        "FORDELT",
        "LAMPEUDTAG ·",
        "Ingen forbindelser laves automatisk",
        "terminal_shadow",
        "accent_pen",
    ):
        assert token in source


def test_hover_and_selection_transitions_are_short_and_presentation_only():
    source = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    assert "QVariantAnimation" in source
    assert "setDuration(120)" in source
    assert "setDuration(150)" in source
    assert "_hover_progress" in source
    assert "_selection_progress" in source
    assert "OutCubic" in source
    # Presentation animations must not write project/raw data.
    animation_slice = source[source.index("class ElectricalSymbolItem"):source.index("class CableSignals")]
    assert 'project.raw[' not in animation_slice
