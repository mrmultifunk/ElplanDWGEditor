from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_selected_cable_gets_direct_marking_panel_in_inspector():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    panel = (ROOT / "qt_cable_panel.py").read_text(encoding="utf-8")
    marking = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    assert "_create_selected_cable_marking_panel" in panel
    assert 'QGroupBox("Mærkning")' in marking
    assert 'QPushButton("Anvend mærkning")' in marking
    assert 'QPushButton("Grafisk mærkning…")' in marking
    assert "_sync_selected_cable_marking_editor(cable)" in app


def test_selected_cable_marking_apply_only_uses_explicit_label_helper():
    source = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    block = source[
        source.index("    def _apply_selected_cable_marking_from_inspector"):
        source.index("    def _open_selected_cable_marking_workflow")
    ]
    assert "_apply_graphical_cable_marking(cable, edit.text())" in block
    assert '"circuit_id"' not in block
    assert '"cable_id"' not in block
    assert "EditCableCommand" not in block


def test_selected_cable_suggestions_only_fill_field_until_apply():
    source = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    block = source[
        source.index("    def _fill_selected_cable_marking"):
        source.index("    def _apply_selected_cable_marking_from_inspector")
    ]
    assert "edit.setText" in block
    assert "_apply_graphical_cable_marking" not in block
    assert "EditCableCommand" not in block


def test_existing_graphical_mode_and_route_list_remain_available():
    marking = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    routes = (ROOT / "qt_cable_routes.py").read_text(encoding="utf-8")
    assert 'QAction("Mærk kabler"' in marking
    assert 'self.tabs.addTab(marking_page, "Mærkning")' in routes
    assert "Mærk valgt på plantegningen" in routes
