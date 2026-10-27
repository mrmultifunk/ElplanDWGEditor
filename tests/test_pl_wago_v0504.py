import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def ref(uid, core_id, function):
    return {
        "cable_uid": uid, "point_index": 0, "leg": "endpoint",
        "core_id": core_id, "function": function, "note": "",
    }


def test_wiser_capacity_is_two_and_classic_is_four():
    assert core.pl_outlet_terminal_capacity("wiser_dimmer", [], "n") == 2
    assert core.pl_outlet_terminal_capacity("lk_classic", [], "n") == 4


def test_wago_groups_only_its_explicit_members_and_uses_one_bridge():
    wiring=[ref("c1","blue","n"),ref("c2","blue","n"),ref("c3","blue","n")]
    no_wago=core.pl_terminal_occupancy("n",wiring,[])
    assert no_wago["terminal_count"] == 3
    splice={"id":"w1","function":"n","members":[core.pl_box_conductor_ref(core.pl_box_conductor_key(wiring[0])),core.pl_box_conductor_ref(core.pl_box_conductor_key(wiring[1]))]}
    with_wago=core.pl_terminal_occupancy("n",wiring,[splice])
    assert len(with_wago["direct"]) == 1
    assert with_wago["splice_count"] == 1
    assert with_wago["terminal_count"] == 2
    assert core.pl_outlet_capacity_issues("wiser_dimmer",[],wiring,[splice]) == []


def test_capacity_issue_without_wago_is_reported():
    wiring=[ref("c1","blue","n"),ref("c2","blue","n"),ref("c3","blue","n")]
    issues=core.pl_outlet_capacity_issues("wiser_dimmer",[],wiring,[])
    assert len(issues)==1
    assert issues[0]["function_id"]=="n"
    assert issues[0]["terminal_count"]==3
    assert issues[0]["capacity"]==2


def test_project_roundtrip_preserves_manual_wago(tmp_path):
    lamp=core.Placement("light_connection",0,0,uid="lamp1",lamp_outlet_type="wiser_dimmer")
    cables=[]
    for i in range(1,4):
        cable=core.CablePlacement(points=[(0,0),(100*i,0)],uid=f"c{i}",cable_id=f"K{i}",cable_spec="3G1,5")
        core.set_cable_symbol_connections(cable,[{"point_index":0,"symbol_uid":"lamp1","symbol_port":0}])
        cables.append(cable)
    legs=core.cable_legs_at_symbol(cables,"lamp1")
    wiring=core.reconcile_pl_box_wiring([],legs)
    for row in wiring:
        if row["core_id"]=="blue":
            row["function"]="n"
    blue=[core.pl_box_conductor_key(x) for x in wiring if x["core_id"]=="blue"]
    lamp.pl_box_wiring=wiring
    lamp.pl_box_splices=[{"id":"w1","function":"n","members":[core.pl_box_conductor_ref(blue[0]),core.pl_box_conductor_ref(blue[1])],"note":"N-samling"}]
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf"); doc.placements=[lamp]; doc.cables=cables
    path=tmp_path/"wago.elplan.json"; doc.save(path)
    loaded=ProjectDocument.load(path)
    got=loaded.placements[0].pl_box_splices
    assert len(got)==1
    assert got[0]["id"]=="w1"
    assert got[0]["function"]=="n"
    assert len(got[0]["members"])==2
    assert APP_VERSION=="0.59.73"


def test_clipboard_does_not_copy_physical_wago():
    lamp=core.Placement("light_connection",0,0,pl_box_splices=[{"id":"w1","function":"n","members":[{"cable_uid":"c1","point_index":0,"leg":"endpoint","core_id":"blue"},{"cable_uid":"c2","point_index":0,"leg":"endpoint","core_id":"blue"}]}])
    copied=core.placement_from_clipboard_payload(core.symbol_clipboard_payload(lamp))
    assert copied is not None
    assert copied.pl_box_splices==[]
