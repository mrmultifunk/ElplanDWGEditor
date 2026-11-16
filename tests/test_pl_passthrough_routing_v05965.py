from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _cable():
    cable=core.CablePlacement(
        points=[(0,0),(100,0)],uid="c1",cable_id="K1",cable_spec="5G1,5",
    )
    core.set_cable_symbol_connections(cable,[
        {"point_index":0,"symbol_uid":"local","symbol_port":0},
        {"point_index":1,"symbol_uid":"remote","symbol_port":0},
    ])
    return cable


def test_version_05965():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_passthrough_functions_keep_switch_and_both_travellers_distinct():
    assert core.pl_passthrough_function("switch","b") == "switch:b"
    assert core.pl_passthrough_function("traveller_1","b") == "traveller:b:1"
    assert core.pl_passthrough_function("traveller_2","b") == "traveller:b:2"
    assert core.pl_wiring_function_caption("traveller:b:1") == "Mellemleder 1 · tilhørsforhold b"
    assert core.pl_passthrough_function_parts("traveller:b:2") == {
        "function":"traveller:b:2","role":"traveller_2","association":"b",
    }


def test_loop_splice_preserves_destination_identity_and_does_not_use_local_terminal():
    wiring=[{
        "cable_uid":"c1","point_index":0,"leg":"endpoint","core_id":"black",
        "function":"switch:b","note":"",
    }]
    splice={
        "id":"loop","function":"switch:b","members":[core.pl_box_conductor_ref(core.pl_box_conductor_key(wiring[0]))],
        "connects_to_outlet":False,"conductor_role":"switch",
        "destination_light_uid":"remote","destination_association":"b",
    }
    got=core.normalize_pl_box_splices([splice])[0]
    assert got["destination_light_uid"] == "remote"
    assert got["destination_association"] == "b"
    assert got["conductor_role"] == "switch"
    assert core.pl_terminal_occupancy("switch:b",wiring,[got])["terminal_count"] == 0
    assert core.pl_terminal_occupancy("switch:j",wiring,[got])["terminal_count"] == 0


def test_old_control_loop_without_destination_is_flagged_for_review():
    splice={
        "id":"old","function":"switch:j","members":[],
        "connects_to_outlet":False,"article_no":"221-412",
    }
    status=core.pl_montage_status("generic",["j"],[],[splice],[],None)
    row=status["wago"][0]
    assert row["destination_missing"] is True
    assert row["state"] == "warning"
    assert any("mangler tilhørende lampested" in text for text in status["warnings"])


def test_locally_empty_core_reports_allocation_at_other_cable_end():
    cable=_cable()
    local=core.Placement("light_connection",0,0,uid="local",associations=["j"])
    remote=core.Placement("light_connection",100,0,uid="remote",associations=["b"])
    remote_legs=core.cable_legs_at_symbol([cable],remote.uid)
    remote_wiring=core.reconcile_pl_box_wiring([],remote_legs)
    black=next(row for row in remote_wiring if row["core_id"]=="black")
    remote.pl_box_wiring=core.assign_pl_conductor_function(
        remote_wiring,remote_legs,core.pl_box_conductor_key(black),"switch:b",
    )
    local_legs=core.cable_legs_at_symbol([cable],local.uid)
    local_wiring=core.reconcile_pl_box_wiring([],local_legs)
    allocation=core.cable_conductor_external_allocations(
        cable.uid,"black",[local,remote],[cable],
        current_placement_uid=local.uid,current_wiring=local_wiring,
    )
    assert allocation["functions"] == ["switch:b"]
    assert allocation["usages"][0]["placement_uid"] == "remote"
    assert allocation["conflict"] is False


def test_qt_uses_separate_route_lanes_destination_picker_and_link_marker():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "center_y-18.0" in source and "center_y+18.0" in source
    assert "_choose_passthrough_identity" in source
    assert "Tilhører lampested" in source
    assert "Skift ledertype / tilhørende lampested" in source
    assert "_draw_external_allocation_marker" in source
    assert "Lederen er endnu ikke fysisk forbundet i denne dåse." in source

