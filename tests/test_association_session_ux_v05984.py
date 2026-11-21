from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_version_and_visible_session_actions():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    workspace = (ROOT / "elplan_qt/qt_visual_workspace.py").read_text(encoding="utf-8")
    assert 'QPushButton("Gem tilknytning")' in app
    assert 'QPushButton("Annuller")' in app
    assert 'QKeySequence("Ctrl+Return")' in app
    assert "action.setEnabled(can_save)" in app
    assert '"finish_text": "Gem tilknytning"' in workspace
    assert 'self._finish_active_association()' in workspace


def test_target_clicks_do_not_reselect_or_drag_symbols():
    graphics = (ROOT / "elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    click = graphics[graphics.index("    def mousePressEvent(self, event) -> None:", graphics.index("class ElectricalSymbolItem")):]
    click = click[:click.index("    def mouseMoveEvent")]
    assert "self.signals.clicked.emit(self)" in click
    assert "if self.workflow_click_only:" in click
    assert click.index("if self.workflow_click_only:") < click.index("self._drag_start_pose =")


def test_relation_click_refresh_is_targeted_and_panel_refresh_is_coalesced():
    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    symbol_click = app[app.index("        if not self.association_source_uid:return",app.index("    def _symbol_clicked")):app.index("    def _reselect_uid")]
    reselect = app[app.index("    def _reselect_uid"):app.index("    def clear_selected_associations")]
    assert "self._refresh_association_annotations(*affected)" in symbol_click
    assert "for ann in self.annotation_items.values()" not in symbol_click
    assert "QTimer.singleShot(0,lambda:self._reselect_uid(source.uid))" not in symbol_click
    assert "blocker=QSignalBlocker(self.scene)" in reselect
    assert "self._selection_changed()" in reselect
