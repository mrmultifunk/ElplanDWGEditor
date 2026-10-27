from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_05016():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"


def test_pl_entry_data_supports_compact_hover_summary():
    light=core.Placement(symbol="light_connection",x=100.0,y=0.0,size=200,group="G11",pl_box_orientation=90)
    cable=core.CablePlacement(
        points=[(0.0,0.0),(100.0,0.0)], cable_id="G11", cable_spec="5G1,5",
        end_symbol_uid=light.uid, auto_label=True,
    )
    legs=core.cable_legs_at_symbol([cable],light.uid)
    entries=core.auto_assign_pl_box_entries(legs,{})
    reconciled=core.reconcile_pl_box_entries(entries,legs)
    assert len(reconciled)==1
    assert legs[0]["cable_id"]=="G11"
    assert legs[0]["cable_spec"]=="5G1,5"
    assert core.normalize_pl_box_orientation(light.pl_box_orientation)==90


def test_hover_source_uses_half_second_timer_bom_and_pl_entries_only():
    app_source=Path("qt_app.py").read_text(encoding="utf-8")
    hover_source=Path("qt_hover.py").read_text(encoding="utf-8")
    hover_bom_source=Path("hover_bom.py").read_text(encoding="utf-8")
    gfx_source=Path("qt_graphics.py").read_text(encoding="utf-8")
    assert 'self._hover_info_timer.start(180 if str(kind)=="cable" else 500)' in hover_source
    assert "QCursor" in hover_source
    assert "def _hover_info_move" in hover_source
    assert "def _pl_entry_hover_payload" in app_source
    assert "class _HoverPreviewWidget" in hover_source
    assert '"preview_mode":"pl"' in app_source
    assert "core.reconcile_pl_box_entries" in app_source
    assert "core.pl_box_unplaced_legs" in app_source
    assert "def _placement_hover_bom_html" in hover_source
    assert "Stykliste:" in hover_bom_source
    assert "Wago i PL-dåse" in hover_bom_source
    assert "hoverEntered = Signal(object)" in gfx_source
    assert "hoverLeft = Signal(object)" in gfx_source
    assert "self.setAcceptHoverEvents(True)" in gfx_source


def test_hover_popup_does_not_add_project_fields():
    source=Path("project_model.py").read_text(encoding="utf-8")
    assert "hover_info" not in source
    assert '"pl_box_entries": {}' in source


def test_pl_hover_shows_port_numbers_in_preview_and_cable_id_only_in_text():
    source=Path("qt_app.py").read_text(encoding="utf-8")
    assert "Kabelnr." in source
    assert 'cable_id=str(leg.get("cable_id")' in source
    assert 'leg.get("cable_extra_label")' in source
    hover=Path("qt_hover.py").read_text(encoding="utf-8")
    assert 'badge_center=QPointF((outside.x()+edge.x())/2.0' in hover
    assert 'p.drawText(badge_rect,Qt.AlignmentFlag.AlignCenter,str(port))' in hover
    assert "kabel-ID-tag" not in source
    assert 'shown=cable_id if len(cable_id)' not in source
