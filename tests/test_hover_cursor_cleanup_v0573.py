from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT=Path(__file__).resolve().parents[1]


def test_version_0573():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_hover_popup_cursor_import_and_live_cable_anchor():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    gfx=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    assert "QCursor" in hover
    assert "def move_near_cursor" in hover
    assert "def _hover_info_move" in hover
    assert "hoverMoved = Signal(object, object)" in gfx
    assert "event.screenPos()" in gfx
    assert '_hover_info_move("cable",obj,pos)' in app
    assert '180 if str(kind)=="cable" else 500' in hover


def test_symbol_legacy_hover_remains_available_while_placing_symbols():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "def _hover_workflow_blocks" in hover
    assert 'if str(kind)=="symbol" and mode=="PLACERING"' in hover
    assert "return False" in hover
    assert "mouseGrabberItem" in hover
    assert "activePopupWidget" in hover


def test_canvas_category_strip_is_kept_out_of_drawing_area():
    visual=(ROOT/"qt_visual_workspace.py").read_text(encoding="utf-8")
    assert "self.cable_category_strip.hide()" in visual
    assert "strip.hide()" in visual
    assert "strip is not None and strip.isVisible()" in visual


def test_hover_does_not_duplicate_in_scene_cable_badge():
    gfx=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    assert "badge_mix=0.0 if self._marking_mode else selection_mix" in gfx
    assert "Hover information is shown beside the mouse" in gfx
