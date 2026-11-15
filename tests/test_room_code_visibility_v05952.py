from pathlib import Path

from project_model import APP_VERSION
import core_logic as core

ROOT = Path(__file__).resolve().parents[1]


def test_version_v05957():
    assert APP_VERSION == core.APP_VERSION == "0.59.79"


def test_room_name_and_room_code_can_be_shown_independently():
    src=(ROOT / "qt_rooms.py").read_text(encoding="utf-8")
    assert 'QAction("Vis rumnavne"' in src
    assert 'QAction("Vis rummærkning"' in src
    assert "room_codes_visible" in src
    assert "item.set_show_code(codes_visible)" in src
    assert "self.project.raw['room_codes_visible']=bool(checked)" in src
    toggle=src[src.index("def _room_codes_toggled"):src.index("def _room_boundaries_toggled")]
    assert "room.code" in toggle  # comment documents preservation
    assert "setattr" not in toggle


def test_room_label_defaults_to_clean_name_only():
    src=(ROOT / "qt_rooms.py").read_text(encoding="utf-8")
    assert "self._show_code=False" in src
    assert 'label=name or "Rum"' in src
    assert "room_codes_visible',False" in src
