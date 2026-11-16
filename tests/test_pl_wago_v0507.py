from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def ref(uid, core_id="blue", function="n"):
    return {"cable_uid":uid,"point_index":0,"leg":"endpoint","core_id":core_id,"function":function,"note":""}


def test_version_0507():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"


def test_planned_empty_wago_is_preserved():
    got=core.normalize_pl_box_splices([{"id":"w1","function":"n","members":[],"article_no":"221-412"}])
    assert len(got)==1
    assert got[0]["members"]==[]
    assert got[0]["function"]=="n"


def test_existing_wago_keeps_explicit_members_and_other_leads_remain_direct():
    wiring=[ref("c1"),ref("c2"),ref("c3")]
    legs=[
        {"cable_uid":"c1","point_index":0,"leg":"endpoint","cable_spec":"3G1,5"},
        {"cable_uid":"c2","point_index":0,"leg":"endpoint","cable_spec":"3G1,5"},
        {"cable_uid":"c3","point_index":0,"leg":"endpoint","cable_spec":"3G1,5"},
    ]
    splice={"id":"w1","function":"n","members":[core.pl_box_conductor_ref(core.pl_box_conductor_key(wiring[0]))],"article_no":"221-415"}
    occ=core.pl_terminal_occupancy("n",wiring,[splice])
    assert occ["direct"]==[core.pl_box_conductor_key(wiring[1]),core.pl_box_conductor_key(wiring[2])]
    assert occ["terminal_count"]==3
    assert occ["exclusive_wago"] is False


def test_montage_status_reports_terminal_and_wago_capacity():
    wiring=[ref("c1"),ref("c2"),ref("c3")]
    splice={"id":"w1","function":"n","members":[core.pl_box_conductor_ref(core.pl_box_conductor_key(x)) for x in wiring],"article_no":"221-415"}
    status=core.pl_montage_status("wiser_dimmer",[],wiring,[splice],[],None)
    n=next(x for x in status["terminals"] if x["function_id"]=="n")
    assert n["terminal_count"]==1
    assert n["has_wago"] is True
    w=status["wago"][0]
    assert w["needed_ports"]==4
    assert w["article_capacity"]==5
    assert w["state"]=="ok"


def test_qt_source_has_manual_planned_wago_routing_and_montage_status():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _show_function_context_menu" in source
    assert "def _show_drop_function_menu" in source
    assert "én fysisk bro går videre til lampeudtaget" in source
    assert "def _auto_route_guides" in source
    assert "route_guides=self._auto_route_guides" in source
    assert "Montagekontrol:" in source
    assert "def _refresh_montage_status" in source
