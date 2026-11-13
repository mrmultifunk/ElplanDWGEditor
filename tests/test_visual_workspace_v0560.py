from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_visual_workspace_module_and_version():
    assert APP_VERSION == core.APP_VERSION == "0.59.75"
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    visual = (ROOT / "qt_visual_workspace.py").read_text(encoding="utf-8")
    assert "from qt_visual_workspace import VisualWorkspaceMixin" in app
    assert "class VisualWorkspaceMixin" in visual
    assert "class WorkflowBar" in visual
    assert "class InspectorSummaryCard" in visual


def test_active_workflow_bar_covers_primary_tools():
    visual = (ROOT / "qt_visual_workspace.py").read_text(encoding="utf-8")
    for token in ("KABELTRÆK", "PLACERING", "TEKST", "SPOTS", "KALIBRERING", "TILHØRSFORHOLD"):
        assert token in visual
    assert "Fortryd punkt" in visual
    assert "Afslut kabel" in visual
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert "self._create_visual_workspace()" in app
    assert "self._refresh_workflow_bar()" in app


def test_selected_cable_has_halo_and_endpoint_markers():
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    assert "self.selection_halo = QGraphicsPathItem(self)" in graphics
    assert "self.selection_endpoints = []" in graphics
    assert "halo_pen.setWidthF(8.0)" in graphics
    assert "marker.setPos(_mapped_point(*point))" in graphics


def test_group_focus_is_presentation_only_and_has_context_actions():
    visual = (ROOT / "qt_visual_workspace.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    assert "def focus_selected_group" in visual
    assert "def clear_group_focus" in visual
    assert "def _apply_visual_emphasis" in visual
    assert "_focus_group_id" in visual
    assert 'project.raw["focus' not in visual
    assert 'QAction("Fokusér valgt gruppe"' in app
    assert "Ctrl+Shift+F" in app
    assert "self.act_ctx_focus_group" in workspace


def test_inspector_has_compact_object_summary():
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    visual = (ROOT / "qt_visual_workspace.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert "self.inspector_summary = InspectorSummaryCard(shell)" in workspace
    assert "Gruppe {group}" in visual
    assert "core.cable_length_metres" in visual
    assert "self._update_inspector_summary(cable=cable)" in app
    assert "self._update_inspector_summary(placement=p)" in app


def test_visual_workspace_theme_hooks_exist():
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    for token in ("QFrame#workflowBar", "QLabel#workflowMode", "QFrame#inspectorSummaryCard", "QLabel#inspectorSummaryChip"):
        assert token in theme
