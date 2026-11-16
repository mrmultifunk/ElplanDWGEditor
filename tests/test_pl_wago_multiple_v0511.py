from pathlib import Path

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def ref(uid, function="n"):
    return {"cable_uid":uid,"point_index":0,"leg":"endpoint","core_id":"blue","function":function,"note":""}


def member(uid):
    return core.pl_box_conductor_ref((uid,0,"endpoint","blue"))


def test_version_0511():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def test_multiple_wagos_can_share_same_function():
    rows=core.normalize_pl_box_splices([
        {"id":"w1","function":"n","members":[member("c1")],"connects_to_outlet":True},
        {"id":"w2","function":"n","members":[member("c2")],"connects_to_outlet":True},
        {"id":"w3","function":"n","members":[member("c3")],"connects_to_outlet":False},
    ])
    assert [x["id"] for x in rows] == ["w1","w2","w3"]
    assert [x["function"] for x in rows] == ["n","n","n"]


def test_multiple_outlet_wagos_each_use_one_terminal_slot():
    wiring=[ref("c1"),ref("c2"),ref("c3"),ref("c4")]
    splices=[
        {"id":"w1","function":"n","members":[member("c1"),member("c2")],"connects_to_outlet":True},
        {"id":"w2","function":"n","members":[member("c3"),member("c4")],"connects_to_outlet":True},
    ]
    occ=core.pl_terminal_occupancy("n",wiring,splices)
    assert occ["direct"] == []
    assert occ["splice_count"] == 2
    assert occ["terminal_count"] == 2
    assert occ["exclusive_wago"] is False
    assert core.pl_outlet_capacity_issues("wiser_dimmer",[],wiring,splices) == []


def test_direct_conductors_can_coexist_with_multiple_wagos():
    wiring=[ref("c1"),ref("c2"),ref("c3")]
    splices=[
        {"id":"w1","function":"n","members":[member("c1")],"connects_to_outlet":True},
        {"id":"w2","function":"n","members":[member("c2")],"connects_to_outlet":False},
    ]
    occ=core.pl_terminal_occupancy("n",wiring,splices)
    assert occ["direct"] == [core.pl_box_conductor_key(wiring[2])]
    assert occ["splice_count"] == 1
    assert occ["loop_splice_count"] == 1
    assert occ["terminal_count"] == 2


def test_reconcile_keeps_multiple_same_function_splices_and_unique_members():
    legs=[
        {"cable_uid":"c1","point_index":0,"leg":"endpoint","cable_spec":"3G1,5"},
        {"cable_uid":"c2","point_index":0,"leg":"endpoint","cable_spec":"3G1,5"},
    ]
    wiring=core.reconcile_pl_box_wiring([],legs)
    for row in wiring:
        if row["core_id"]=="blue":row["function"]="n"
    blue=[core.pl_box_conductor_key(x) for x in wiring if x["core_id"]=="blue"]
    got=core.reconcile_pl_box_splices([
        {"id":"w1","function":"n","members":[core.pl_box_conductor_ref(blue[0])]},
        {"id":"w2","function":"n","members":[core.pl_box_conductor_ref(blue[1])]},
    ],wiring,legs)
    assert len(got)==2
    assert core.pl_splice_member_keys(got[0])==[blue[0]]
    assert core.pl_splice_member_keys(got[1])==[blue[1]]


def test_project_roundtrip_preserves_multiple_wagos_same_function(tmp_path):
    lamp=core.Placement("light_connection",0,0,uid="lamp",pl_box_splices=[
        {"id":"w1","function":"n","members":[],"article_no":"221-412","connects_to_outlet":True},
        {"id":"w2","function":"n","members":[],"article_no":"221-412","connects_to_outlet":False},
    ])
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf"); doc.placements=[lamp]
    path=tmp_path/"multi.elplan.json"; doc.save(path)
    loaded=ProjectDocument.load(path)
    assert [x["id"] for x in loaded.placements[0].pl_box_splices]==["w1","w2"]


def test_qt_new_wago_is_function_based_and_not_limited_by_existing_function():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _show_function_context_menu" in source
    assert "+ Opret Wago for" in source
    assert "Administrér Wago…" in source
    assert "Du kan oprette flere Wago'er på samme funktion" in source
    assert "str(t.get(\"function_id\",\"\") or \"\") not in existing" not in source
