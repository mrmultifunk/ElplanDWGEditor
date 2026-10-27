from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_graphical_cable_marking_is_explicit_and_only_writes_extra_label():
    source = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    block = source[source.index("    def _apply_graphical_cable_marking"):source.index("    def _advance_cable_marking")]
    assert 'EditCableCommand(self, cable, {"label": old}, {"label": new}' in block
    assert '"circuit_id"' not in block
    assert '"cable_id"' not in block
    assert "Anvend" in source
    assert "Spring over" in source


def test_suggestion_chips_fill_editor_without_applying():
    source = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    suggestion = source[source.index("    def _use_suggestion"):source.index("    def show_near_cursor")]
    assert "self.edit.setText" in suggestion
    assert "_apply_graphical_cable_marking" not in suggestion
    assert "EditCableCommand" not in suggestion


def test_marking_mode_has_visual_badges_and_route_overview_tab():
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    routes = (ROOT / "qt_cable_routes.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    workspace = (ROOT / "qt_workspace.py").read_text(encoding="utf-8")
    assert "set_marking_mode" in graphics
    assert 'chip=(approved[:30]+"…")' in graphics
    assert 'self.tabs.addTab(marking_page, "Mærkning")' in routes
    assert "Mærk valgt på plantegningen" in routes
    assert "self._create_cable_marking_actions()" in app
    assert "tb.addAction(self.act_cable_marking)" in workspace


def test_marking_click_has_priority_only_when_marking_mode_is_active():
    source = (ROOT / "qt_cable_marking.py").read_text(encoding="utf-8")
    block = source[source.index("    def _handle_cable_item_click"):source.index("    def _cable_marking_endpoint_text")]
    assert "_pending_cable_attach_symbol_uid" in block
    assert "_cable_marking_active" in block
    assert "return super()._handle_cable_item_click" in block
