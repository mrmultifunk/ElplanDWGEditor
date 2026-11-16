from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_0524():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_pl_identification_keeps_group_and_marking_together():
    lamp = core.Placement("light_connection", 0, 0, uid="pl1", group="G11", label="T.V. BAD2")
    assert core.placement_identification_caption(lamp) == "G11 · T.V. BAD2"

    same = core.Placement("light_connection", 0, 0, uid="pl2", group="G12", label="G12")
    assert core.placement_identification_caption(same) == "G12"


def test_switch_conductor_usage_location_contains_group_and_marking():
    lamp = core.Placement("light_connection", 0, 0, uid="pl1", group="G11", label="T.V. BAD2")
    cable = core.CablePlacement(points=[(0, 0), (100, 0)], uid="c1", cable_id="K01", cable_spec="7G1,5")
    core.set_cable_symbol_connections(cable, [{"point_index": 0, "symbol_uid": lamp.uid, "symbol_port": 0}])
    legs = core.cable_legs_at_symbol([cable], lamp.uid)
    wiring = core.reconcile_pl_box_wiring([], legs)
    black = next(x for x in core.pl_box_conductors(legs) if x["core_id"] == "black")
    lamp.pl_box_wiring = core.assign_pl_conductor_function(
        wiring, legs, core.pl_box_conductor_key(black), "switch:a"
    )

    usage = core.cable_switch_conductor_usage(cable.uid, [lamp], [cable])
    black_usage = next(x for x in usage["cores"] if x["core_id"] == "black")["usages"]
    assert black_usage[0]["placement"] == "G11 · T.V. BAD2"


def test_pl_dialog_keeps_footer_visible_and_shows_marking_in_usage_card():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    helper = Path("qt_pl_usage.py").read_text(encoding="utf-8")
    assert "_resize_dialog(self,1240,820)" in source
    assert "wiring_tab=QScrollArea()" in source
    assert "wiring_tab.setWidgetResizable(True)" in source
    assert "self.setMinimumSize(780, 470)" in source
    assert "OK/Annuller/Anvend altid bliver stående synligt nederst" in source
    assert "self.switch_conductor_card.set_location" in source
    assert 'self.location.setText(f"Lampested: {caption}")' in helper


def test_pl_report_prints_group_and_marking_as_explicit_fields():
    source = Path("core_logic.py").read_text(encoding="utf-8")
    assert 'f"Gruppe/kreds: {group or \'—\'}   |   Mærkning: {label or \'—\'}"' in source
    assert "placement_identification_caption(placement)" in source
