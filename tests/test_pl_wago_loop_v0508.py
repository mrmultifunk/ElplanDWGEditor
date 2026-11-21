from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION


def ref(uid, core_id="blue", function="n"):
    return {
        "cable_uid": uid,
        "point_index": 0,
        "leg": "endpoint",
        "core_id": core_id,
        "function": function,
        "note": "",
    }


def member(uid, core_id="blue"):
    return core.pl_box_conductor_ref((uid, 0, "endpoint", core_id))


def test_version_0508():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"


def test_old_wago_defaults_to_outlet_bridge_and_loop_mode_is_preserved():
    old = core.normalize_pl_box_splices([
        {"id": "old", "function": "n", "members": [member("c1")]}
    ])[0]
    loop = core.normalize_pl_box_splices([
        {"id": "loop", "function": "n", "members": [member("c1")], "connects_to_outlet": False}
    ])[0]
    assert old["connects_to_outlet"] is True
    assert loop["connects_to_outlet"] is False


def test_loop_wago_does_not_consume_outlet_terminal_and_only_selected_members_loop():
    wiring = [ref("c1"), ref("c2"), ref("c3")]
    splice = {
        "id": "loop",
        "function": "n",
        "members": [member("c1"), member("c2")],
        "connects_to_outlet": False,
        "article_no": "221-412",
    }
    occ = core.pl_terminal_occupancy("n", wiring, [splice])
    assert set(occ["loop_members"]) == {tuple(core.pl_box_conductor_key(member("c1"))), tuple(core.pl_box_conductor_key(member("c2")))}
    assert occ["direct"] == [core.pl_box_conductor_key(wiring[2])]
    assert occ["terminal_count"] == 1
    assert occ["exclusive_wago"] is False


def test_loop_wago_recommendation_does_not_reserve_bridge_port():
    assert core.pl_wago_required_ports(2, False) == 2
    assert core.pl_recommended_wago_article(2, False) == "221-412"
    assert core.pl_wago_required_ports(2, True) == 3
    assert core.pl_recommended_wago_article(2, True) == "221-413"


def test_loop_wago_montage_status_has_no_bridge_port():
    wiring = [ref("c1"), ref("c2")]
    splice = {
        "id": "loop",
        "function": "n",
        "members": [member("c1"), member("c2")],
        "connects_to_outlet": False,
        "article_no": "221-412",
    }
    status = core.pl_montage_status("wiser_dimmer", [], wiring, [splice], [], None)
    n = next(x for x in status["terminals"] if x["function_id"] == "n")
    assert n["terminal_count"] == 0
    assert n["has_wago"] is False
    assert n["has_loop_wago"] is True
    wago = status["wago"][0]
    assert wago["connects_to_outlet"] is False
    assert wago["needed_ports"] == 2
    assert wago["article_capacity"] == 2
    assert wago["state"] == "ok"


def test_reconcile_loop_wago_keeps_only_explicit_members():
    legs = [
        {"cable_uid": "c1", "point_index": 0, "leg": "endpoint", "cable_spec": "3G1,5"},
        {"cable_uid": "c2", "point_index": 0, "leg": "endpoint", "cable_spec": "3G1,5"},
        {"cable_uid": "c3", "point_index": 0, "leg": "endpoint", "cable_spec": "3G1,5"},
    ]
    wiring = core.reconcile_pl_box_wiring([], legs)
    for row in wiring:
        if row["core_id"] == "blue":
            row["function"] = "n"
    blue = [core.pl_box_conductor_key(x) for x in wiring if x["core_id"] == "blue"]
    splice = {
        "id": "loop",
        "function": "n",
        "members": [core.pl_box_conductor_ref(blue[0]), core.pl_box_conductor_ref(blue[1])],
        "connects_to_outlet": False,
    }
    got = core.reconcile_pl_box_splices([splice], wiring, legs)[0]
    assert core.pl_splice_member_keys(got) == blue[:2]


def test_qt_exposes_direct_loop_wago_mode_and_drop_target():
    source = Path("elplan_qt/qt_pl_box.py").read_text(encoding="utf-8")
    assert "Forbind samlingen videre til {short_function}-klemmen med én bro" in source
    assert "Samlemuffe / sløjfe for {short_function}" in source
    assert "Sløjf leder i Wago uden lampested" in source
    assert "add_to_splice:" in source
    assert "connects_to_outlet" in source


def test_loop_only_switch_conductor_does_not_satisfy_lamp_terminal_requirement():
    wiring = [ref("c1", core_id="brown", function="switch:a")]
    requirement = [{
        "function_id": "switch:a", "direct": True, "required": True,
        "cable_uid": "c1", "point_index": 0, "leg": "endpoint",
        "manual_topology": False,
    }]
    loop = [{
        "id": "loop", "function": "switch:a", "members": [member("c1", "brown")],
        "connects_to_outlet": False,
    }]
    assert core.pl_wiring_requirement_summary(requirement, wiring)["ok"] == 1
    summary = core.pl_wiring_requirement_summary(requirement, wiring, loop)
    assert summary["ok"] == 0
    assert summary["missing"] == 1


def test_project_roundtrip_preserves_loop_only_mode(tmp_path):
    from elplan_project.project_model import ProjectDocument
    lamp = core.Placement(
        "light_connection", 0, 0, uid="lamp-loop",
        pl_box_splices=[{
            "id": "loop", "function": "n", "members": [],
            "article_no": "221-412", "connects_to_outlet": False,
        }],
    )
    doc = ProjectDocument.from_cad(tmp_path / "plan.dxf")
    doc.placements = [lamp]
    path = tmp_path / "loop.elplan.json"
    doc.save(path)
    loaded = ProjectDocument.load(path)
    splice = loaded.placements[0].pl_box_splices[0]
    assert splice["connects_to_outlet"] is False
    assert splice["article_no"] == "221-412"
