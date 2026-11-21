from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_version_and_selection_is_deferred_until_pointer_release():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    app=(ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    graphics=(ROOT/"elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    assert "self.scene.selectionChanged.connect(self._queue_selection_changed)" in app
    assert "def _flush_queued_selection_changed" in app
    assert "if self._symbol_pointer_down or self._symbol_drag_active:" in app
    assert "pointerPressed = Signal(object)" in graphics
    assert "pointerReleased = Signal(object, bool)" in graphics
    assert "self.signals.pointerReleased.emit(self,was_dragging)" in graphics


def test_drag_and_symbol_cable_panel_use_connection_index():
    app=(ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    drag=app[app.index("    def _symbol_drag_started"):app.index("    def _symbol_drag_finished")]
    cables=app[app.index("    def _refresh_symbol_cables_group"):app.index("    def _refresh_pl_box_group")]
    assert "self._cables_by_symbol_uid.get(uid,[])" in drag
    assert "for cable in self.project.cables" not in drag
    assert "self._cables_by_symbol_uid.get(uid,[])" in cables
    assert "for cable in self.project.cables" not in cables


def test_hidden_procurement_and_cable_articles_are_not_loaded_on_symbol_selection():
    app=(ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    selection=app[app.index("    def _selection_changed"):app.index("    def _selected_symbol_item")]
    assert 'if target_workflow=="purchase":self._refresh_selected_symbol_bom_ui(p)' in selection
    assert "core.bom_binding_summary(" not in selection
    assert "self._refresh_cable_article_ui()" not in selection
    assert "self._cable_article_catalog_cache" in app


def test_unchanged_visual_emphasis_is_reused():
    visual=(ROOT/"elplan_qt/qt_visual_workspace.py").read_text(encoding="utf-8")
    block=visual[visual.index("    def _apply_visual_emphasis"):visual.index("    def _update_inspector_summary")]
    assert '_visual_emphasis_signature' in block
    assert 'if signature==getattr(self,"_visual_emphasis_signature",None):' in block
    assert block.index('if signature==getattr') < block.index('cable_opacity =')
