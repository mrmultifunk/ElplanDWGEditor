from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT=Path(__file__).resolve().parents[1]

def test_version_and_visual_bling_modules():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    visual=(ROOT/"qt_visual_workspace.py").read_text(encoding="utf-8")
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "act_trace_circuit" in app and "act_navigator" in app and "act_zoom_selection" in app
    assert "class MiniMapView" in visual
    assert "def trace_selected_circuit" in visual
    assert "def zoom_to_selection" in visual
    assert "class HoverInfoMixin" in hover

def test_cable_flow_symbol_pulse_and_snap_feedback_are_presentation_only():
    source=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    assert "self.flow_overlay = QGraphicsPathItem(self)" in source
    assert "self._flow_anim.setLoopCount(-1)" in source
    assert "def _start_selection_pulse" in source
    assert "self._snap_pulse_anim" in source
    assert "def animate_to_scene_rect" in source
    assert "hover_badge_text" in source

def test_smart_hover_is_collision_safe():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "QApplication.activePopupWidget()" in hover
    assert "item.isSelected()" not in hover
    assert "_workflow_state" in hover
    assert "mouseGrabberItem" in hover
    assert "WA_TransparentForMouseEvents" in hover

def test_pl_exploded_view_and_connection_animation():
    source=(ROOT/"qt_pl_box.py").read_text(encoding="utf-8")
    assert "Eksploderet visning" in source
    assert "def set_exploded" in source
    assert "def flash_connection" in source
    assert "progress=1.0" in source
    assert "pointAtPercent" in source

def test_overlay_depth_and_animated_toast():
    visual=(ROOT/"qt_visual_workspace.py").read_text(encoding="utf-8")
    feedback=(ROOT/"qt_feedback.py").read_text(encoding="utf-8")
    assert "QGraphicsDropShadowEffect" in visual
    assert "_apply_overlay_depth" in visual
    assert "QPropertyAnimation" in feedback
    assert "_animate_out" in feedback
