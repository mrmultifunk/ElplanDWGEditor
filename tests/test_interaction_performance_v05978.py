from __future__ import annotations

import ast
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]


def _source(name: str) -> str:
    return (ROOT/name).read_text(encoding="utf-8")


def test_performance_sources_are_valid_python():
    ast.parse(_source("qt_app.py"))
    ast.parse(_source("qt_graphics.py"))


def test_symbol_drag_is_frame_coalesced_and_annotation_has_fast_path():
    app=_source("qt_app.py")
    graphics=_source("qt_graphics.py")
    assert "_symbol_drag_visual_timer.setInterval(16)" in app
    assert "def _flush_symbol_drag_visuals" in app
    assert "if not self._symbol_drag_visual_timer.isActive()" in app
    assert "def reposition_fast" in graphics
    assert "use_cached_direction=True" in graphics


def test_snap_candidates_are_cached_for_active_gestures():
    app=_source("qt_app.py")
    graphics=_source("qt_graphics.py")
    assert "begin_lighting_alignment_snapshot" in graphics
    assert "self._lighting_alignment_snapshot" in graphics
    assert "begin_cable_interaction_snapshot" in graphics
    assert "self._cable_route_snapshot" in graphics
    assert "item.signals.editStarted.connect(self._cable_handle_edit_started)" in app
    assert "self.view.end_cable_interaction_snapshot()" in app


def test_hover_and_anchor_lookups_avoid_redundant_global_work():
    app=_source("qt_app.py")
    graphics=_source("qt_graphics.py")
    assert "symmetric_difference(wanted)" in app
    assert "_chain_highlight_target" in graphics
    assert "if abs(target-self._chain_highlight_target) <= 1e-9" in graphics
    assert 'item=self.symbol_items.get(str(uid or ""))' in app
