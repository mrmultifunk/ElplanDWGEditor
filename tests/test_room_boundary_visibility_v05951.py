from pathlib import Path

from project_model import APP_VERSION
import core_logic as core

ROOT = Path(__file__).resolve().parents[1]


def test_version_v05957():
    assert APP_VERSION == core.APP_VERSION == "0.59.79"


def test_hiding_room_boundaries_exits_edit_mode_and_labels_remain_independent():
    source=(ROOT / "qt_rooms.py").read_text(encoding="utf-8")
    block=source[source.index("def _room_boundaries_toggled"):source.index("def room_for_point")]
    assert "if not checked and self.room_edit_mode" in block
    assert "self.room_edit_mode=False" in block
    assert "self.act_room_edit.setChecked(False)" in block
    assert "item.setSelected(False)" in block
    assert "item.setVisible(layer_visible and text_visible)" in block
    assert "self.act_room_boundaries.setChecked(boundaries)" in block
