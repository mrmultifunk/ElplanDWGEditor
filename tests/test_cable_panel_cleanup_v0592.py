from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cable_panel_is_responsive_and_never_requires_horizontal_panning():
    panel = (ROOT / "elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    marking = (ROOT / "elplan_qt/qt_cable_marking.py").read_text(encoding="utf-8")
    assert "ScrollBarAlwaysOff" in panel
    assert panel.count("WrapLongRows") >= 2
    assert "QGridLayout" in marking
    assert "_compact_suggestion_caption" in marking


def test_selected_cable_hides_new_drawing_controls_and_prioritizes_marking():
    panel = (ROOT / "elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    # Marking is created before the generic cable-data group.
    assert panel.index("_create_selected_cable_marking_panel") < panel.index('QGroupBox("Kabeldata")')
    context = panel[panel.index("    def _set_cable_panel_context"):]
    assert "self.cable_drawing_disclosure.setVisible(not selected)" in context
    assert "self.cable_draw_status_host.setVisible(not selected)" in context
    assert "self.cable_draw_controls.setVisible(not selected)" in context
    assert "self.cable_apply_selected.setVisible(selected)" in context


def test_start_id_is_advanced_and_explained_instead_of_first_cable_id():
    panel = (ROOT / "elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    assert "Første kabel-ID" not in panel
    assert 'self.cable_id_field_label = QLabel("Start-ID")' in panel
    assert "ID vælges automatisk" in panel
    assert 'DisclosureSection("Avancerede kabeldata"' in panel


def test_extra_marking_is_never_an_implicit_default_for_new_cables():
    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    panel = (ROOT / "elplan_qt/qt_cable_panel.py").read_text(encoding="utf-8")
    start = app[app.index("    def _start_cable_from_panel"):app.index("    def _cancel_current_cable")]
    apply_block = app[app.index("    def apply_selected_cable_properties"):app.index("    def _remove_cable")]
    assert 'label=""' in start
    assert '"label":self.cable_label_edit.text().strip()' not in apply_block
    assert 'self.cable_label_edit.setText("")' in panel
