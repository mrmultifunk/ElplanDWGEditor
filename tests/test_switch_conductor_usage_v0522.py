from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _wire(cable, placement, core_id, function):
    legs = core.cable_legs_at_symbol([cable], placement.uid)
    wiring = core.reconcile_pl_box_wiring(getattr(placement, "pl_box_wiring", []), legs)
    row = next(x for x in core.pl_box_conductors(legs) if x["core_id"] == core_id)
    placement.pl_box_wiring = core.assign_pl_conductor_function(wiring, legs, core.pl_box_conductor_key(row), function)


def _sample_chain():
    p1 = core.Placement("light_ceiling", 0, 0, group="PL01", uid="pl01")
    p2 = core.Placement("light_ceiling", 10, 0, group="PL02", uid="pl02")
    p3 = core.Placement("light_ceiling", 20, 0, group="PL03", uid="pl03")
    cable = core.CablePlacement(
        points=[(0, 0), (10, 0), (20, 0)], cable_id="K17", cable_spec="7G1,5", uid="cable17"
    )
    core.set_cable_symbol_connections(cable, [
        {"point_index": 0, "symbol_uid": p1.uid, "symbol_port": 0},
        {"point_index": 1, "symbol_uid": p2.uid, "symbol_port": 0},
        {"point_index": 2, "symbol_uid": p3.uid, "symbol_port": 0},
    ])
    return cable, [p1, p2, p3]


def test_switch_conductor_usage_tracks_colors_across_whole_cable():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    cable, placements = _sample_chain()
    _wire(cable, placements[0], "black", "switch:a")
    _wire(cable, placements[1], "grey", "switch:b")

    usage = core.cable_switch_conductor_usage(cable.uid, placements, [cable])
    by_id = {row["core_id"]: row for row in usage["cores"]}

    assert by_id["black"]["status"] == "used_switch"
    assert by_id["black"]["switch_functions"] == ["switch:a"]
    assert by_id["grey"]["switch_functions"] == ["switch:b"]
    assert by_id["red"]["status"] == "available"
    assert by_id["white"]["status"] == "available"
    assert by_id["pe"]["typical_supply"] is True
    assert by_id["blue"]["typical_supply"] is True
    assert by_id["brown"]["typical_supply"] is True
    assert usage["recommended_core_id"] == "red"


def test_switch_conductor_usage_detects_conflicting_reuse_and_current_dialog_override():
    cable, placements = _sample_chain()
    _wire(cable, placements[0], "black", "switch:a")
    _wire(cable, placements[1], "black", "switch:b")

    usage = core.cable_switch_conductor_usage(cable.uid, placements, [cable])
    black = next(row for row in usage["cores"] if row["core_id"] == "black")
    assert black["status"] == "conflict"
    assert black["switch_functions"] == ["switch:a", "switch:b"]
    assert usage["conflicts"]

    legs3 = core.cable_legs_at_symbol([cable], placements[2].uid)
    current = core.reconcile_pl_box_wiring([], legs3)
    red = next(x for x in core.pl_box_conductors(legs3) if x["core_id"] == "red")
    current = core.assign_pl_conductor_function(current, legs3, core.pl_box_conductor_key(red), "switch:c")
    live = core.cable_switch_conductor_usage(
        cable.uid, placements, [cable], current_placement_uid=placements[2].uid, current_wiring=current
    )
    red_usage = next(row for row in live["cores"] if row["core_id"] == "red")
    assert red_usage["switch_functions"] == ["switch:c"]


def test_switch_assignment_advice_prefers_non_supply_colors_and_warns_on_reuse():
    cable, placements = _sample_chain()
    _wire(cable, placements[0], "grey", "switch:b")

    conflict = core.cable_switch_conductor_assignment_advice(
        cable.uid, "grey", "switch:a", placements, [cable]
    )
    assert conflict["conflicting_switch_functions"] == ["switch:b"]

    brown = core.cable_switch_conductor_assignment_advice(
        cable.uid, "brown", "switch:a", placements, [cable]
    )
    assert brown["typical_supply"] is True

    red = core.cable_switch_conductor_assignment_advice(
        cable.uid, "red", "switch:a", placements, [cable]
    )
    assert red["typical_supply"] is False
    assert red["conflicting_switch_functions"] == []


def test_pl_gui_contains_visual_switch_conductor_overview():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    helper = Path("qt_pl_usage.py").read_text(encoding="utf-8")
    assert "SwitchConductorUsageCard" in source
    assert "Tændleder-overblik" in helper
    assert "Næste ledige:" in helper
    assert "Tændleder er allerede i brug" in helper
    assert "Typisk forsyningsleder" in helper
