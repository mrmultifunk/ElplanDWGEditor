from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT=Path(__file__).resolve().parents[1]


def test_version_0575():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"


def test_cable_hover_has_dedicated_prominent_marking_card():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    theme=(ROOT/"qt_theme.py").read_text(encoding="utf-8")
    assert 'self.marking_caption=QLabel("KABELMÆRKNING")' in hover
    assert '"marking":cable_name' in hover
    assert '"marking_extra":f"Ekstra mærkning · {extra}" if extra else ""' in hover
    assert 'QFrame#hoverMarkingCard' in theme
    assert 'QLabel#hoverMarkingValue' in theme
    assert 'font-size: 15px' in theme


def test_cable_hover_keeps_cursor_following_behavior():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "def _hover_info_move" in hover
    assert "popup.move_near_cursor(pos)" in hover
