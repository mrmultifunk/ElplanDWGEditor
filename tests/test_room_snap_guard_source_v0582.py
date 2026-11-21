from pathlib import Path


def test_room_layer_has_explicit_snap_engine_guard_in_source():
    """Architecture guard: EL-RUM must stay out of QtSnapEngine wall geometry."""
    src = Path("elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    assert "if str(layer).casefold() == str(core.ROOM_LAYER).casefold():" in src
    assert "continue" in src[src.index("if str(layer).casefold() == str(core.ROOM_LAYER).casefold():"):][:220]


def test_main_window_still_builds_snap_engine_from_cad_primitives_only():
    src = Path("elplan_qt/qt_app.py").read_text(encoding="utf-8")
    assert "QtSnapEngine(self.cad_primitives" in src
    assert "QtSnapEngine(self.project.rooms" not in src
    assert "QtSnapEngine(self.room" not in src
