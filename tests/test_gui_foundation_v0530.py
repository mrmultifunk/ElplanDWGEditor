from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_workspace_modules_are_present():
    assert APP_VERSION == core.APP_VERSION == "0.59.77"
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    panel = (ROOT / "qt_cable_panel.py").read_text(encoding="utf-8")
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    ui = (ROOT / "qt_ui.py").read_text(encoding="utf-8")
    assert "from qt_workspace import WorkspaceUiMixin" in app
    assert "class MainWindow(ProjectOpenMixin, HoverInfoMixin, VisualWorkspaceMixin, WorkspaceUiMixin" in app
    assert "class WorkspaceUiMixin" in workspace
    assert "class UiMetrics" in ui and "UI = UiMetrics()" in ui


def test_unified_inspector_hosts_symbol_and_cable_pages():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    panel = (ROOT / "qt_cable_panel.py").read_text(encoding="utf-8")
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    assert 'object_name="inspectorDock"' in workspace
    assert "self.inspector_stack = QStackedWidget" in workspace
    assert "self.properties_page = scroll" in app
    assert "self.cable_page = scroll" in panel
    assert 'self.inspector_stack.addWidget(scroll)' in app
    assert 'self._show_inspector_page("cable"' in app
    assert 'self._show_inspector_page("properties"' in app
    assert 'QDockWidget("Kabelværktøj"' not in app


def test_main_toolbar_is_calm_and_context_toolbar_is_selection_aware():
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    main_block = workspace[workspace.index("    def _create_toolbar"):workspace.index("    def _context_selected_cable")]
    assert 'QToolBar("Hovedværktøjer"' in main_block
    assert 'QToolBar("Kontekst"' in main_block
    assert "self.context_cable_category" in main_block
    assert "self.context_cable_route" in main_block
    assert 'QAction("PL-dåse…"' in main_block
    assert 'QAction("Artikler…"' in main_block
    assert "self.act_quick_cad" not in main_block
    assert "self.act_quick_symbols" not in main_block
    assert "self.act_quick_cables" not in main_block


def test_context_toolbar_updates_cable_category_and_route_with_undo():
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    assert "def _context_cable_category_changed" in workspace
    assert 'EditCableCommand(self, cable, before, after, "Skift kabelkategori")' in workspace
    assert "def _context_cable_route_changed" in workspace
    assert "convert_cable_route_mode_geometry" in workspace
    assert '"route_section_modes": []' in workspace


def test_window_and_dock_layout_are_machine_local_and_resettable():
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert 'data["qt_window_geometry"]' in workspace
    assert 'data["qt_window_state"]' in workspace
    assert "restoreGeometry" in workspace and "restoreState" in workspace
    assert "def reset_main_window_layout" in workspace
    assert "self._save_main_window_layout()" in app
    assert 'QAction("Nulstil panel-layout"' in app
