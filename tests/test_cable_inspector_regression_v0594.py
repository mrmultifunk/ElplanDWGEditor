from pathlib import Path


def test_retired_cable_dock_widgets_are_not_referenced_by_active_code():
    main = Path("qt_app.py").read_text(encoding="utf-8")
    sections = Path("qt_cable_sections.py").read_text(encoding="utf-8")
    attach = Path("qt_cable_attach.py").read_text(encoding="utf-8")
    marking = Path("qt_cable_marking.py").read_text(encoding="utf-8")

    assert "self.cable_selected_label" not in main
    assert "self.cable_dock.show()" not in sections
    assert "self.cable_dock.raise_()" not in sections
    assert 'hasattr(self,"cable_dock")' not in attach
    assert 'hasattr(self, "cable_dock")' not in marking
    assert 'self._show_inspector_page(' in sections


def test_selected_cable_loader_uses_unified_inspector_context():
    main = Path("qt_app.py").read_text(encoding="utf-8")
    start = main.index("    def _load_selected_cable_into_panel")
    end = main.index("    def apply_selected_cable_properties", start)
    body = main[start:end]
    assert "self._set_cable_panel_context(cable)" in body
    assert "self.cable_apply_selected.setEnabled(False)" in body
    assert "self.cable_apply_selected.setEnabled(True)" in body
    assert "cable_selected_label" not in body


def test_cable_context_open_action_targets_inspector_not_old_dock():
    source = Path("qt_cable_sections.py").read_text(encoding="utf-8")
    assert 'open_panel=menu.addAction("Vis kablet i Kabelværktøj")' in source
    assert 'self._show_inspector_page(' in source
    assert '"cable"' in source
    assert "self.cable_dock" not in source
