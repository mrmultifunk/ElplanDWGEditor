from pathlib import Path

from project_model import APP_VERSION
import core_logic as core


def test_version_v05945():
    assert APP_VERSION == core.APP_VERSION == "0.59.81"


def test_complete_pull_length_is_always_visible_in_inspector_source():
    root=Path(__file__).resolve().parents[1]
    panel=(root/"qt_cable_panel.py").read_text(encoding="utf-8")
    app=(root/"qt_app.py").read_text(encoding="utf-8")
    assert "cable_chain_summary_label" in panel
    assert "Hele kabeltrækket ·" in app
    assert "cable_chain_summary_label.setVisible(True)" in app


def test_hover_marks_complete_route_chain_without_replacing_primary_hover():
    root=Path(__file__).resolve().parents[1]
    graphics=(root/"qt_graphics.py").read_text(encoding="utf-8")
    app=(root/"qt_app.py").read_text(encoding="utf-8")
    assert "chain_hover_halo" in graphics
    assert "set_chain_highlight" in graphics
    assert "_set_cable_chain_hover" in app
    assert "cable_route_chain_members" in app
    assert "len(members)>1" in app
    assert "_animate_to(self._hover_anim" in graphics
