from pathlib import Path

import core_logic as core


def _combo(uid="sw", symbol="combo_row_2x1_2way_socket"):
    p=core.Placement(symbol=symbol,x=0,y=0,uid=uid,group="G02",label="Kombi køkken")
    return p


def _lamp(uid="lamp", associations=None):
    return core.Placement(symbol="light_connection",x=100,y=0,uid=uid,group="G02",label="PL01",associations=list(associations or []))


def _direct_cable(sw_uid="sw", lamp_uid="lamp", uid="cab", spec="7G1,5"):
    c=core.CablePlacement(points=[(0,0),(100,0)],uid=uid,cable_id="K12",label="Kombi køkken → PL01",cable_spec=spec)
    core.set_cable_symbol_connections(c,[
        {"point_index":0,"symbol_uid":sw_uid,"symbol_port":0},
        {"point_index":1,"symbol_uid":lamp_uid,"symbol_port":0},
    ])
    return c


def test_pl_cable_legs_include_id_and_extra_marking_and_neighbor_switch():
    cable=_direct_cable()
    legs=core.cable_legs_at_symbol([cable],"lamp")
    assert len(legs)==1
    leg=legs[0]
    assert leg["cable_id"]=="K12"
    assert leg["cable_extra_label"]=="Kombi køkken → PL01"
    assert leg["cable_display"]=="K12 · Kombi køkken → PL01"
    assert leg["neighbor_symbol_uid"]=="sw"


def test_combo_channels_are_identified_from_existing_associations_and_direct_cable():
    sw=_combo()
    core.set_association_channel(sw,0,"a")
    core.set_association_channel(sw,1,"b")
    core.set_association_channel(sw,2,"c")
    lamp=_lamp(associations=["a","b","c"])
    cable=_direct_cable()

    req=core.pl_expected_switch_connections(lamp,[sw,lamp],[cable])
    assert [(x["association"],x["channel_caption"]) for x in req]==[
        ("a","Modul 1 · 1-polet"),
        ("b","Modul 2 · 1-polet"),
        ("c","Modul 3 · korrespondance"),
    ]
    assert all(x["direct"] for x in req)
    assert req[0]["channel_id"]==f"{sw.uid}:0"
    assert req[1]["channel_id"]==f"{sw.uid}:1"
    assert req[0]["required"] is True
    assert req[1]["required"] is True
    # Korrespondance kan identificeres via tilhørsforholdet, men terminaltopologien
    # kan ikke udledes sikkert af bogstavet alene.
    assert req[2]["manual_topology"] is True
    assert req[2]["required"] is False
    assert req[0]["cable_display"]=="K12 · Kombi køkken → PL01"



def test_crown_combo_exposes_two_distinct_tending_outputs():
    sw=_combo(symbol="combo_row_crown_1_socket")
    core.set_association_channel(sw,0,"a")
    core.set_association_channel(sw,1,"b")
    core.set_association_channel(sw,2,"c")
    lamp=_lamp(associations=["a","b","c"])
    cable=_direct_cable(spec="7G1,5")
    req=core.pl_expected_switch_connections(lamp,[sw,lamp],[cable])
    assert [(r["association"],r["channel_caption"],r["required"]) for r in req]==[
        ("a","Modul 1 · krone · tænding 1",True),
        ("b","Modul 1 · krone · tænding 2",True),
        ("c","Modul 2 · 1-polet",True),
    ]

def test_switch_requirement_must_be_satisfied_on_expected_cable_leg():
    sw=_combo(symbol="combo_row_2x1_socket")
    core.set_association_channel(sw,0,"a")
    core.set_association_channel(sw,1,"b")
    lamp=_lamp(associations=["a","b"])
    cable=_direct_cable(spec="5G1,5")
    legs=core.cable_legs_at_symbol([cable],lamp.uid)
    req=core.pl_expected_switch_connections(lamp,[sw,lamp],[cable])
    wiring=core.reconcile_pl_box_wiring([],legs)

    summary=core.pl_wiring_requirement_summary(req,wiring)
    assert summary["required"]==2
    assert summary["missing"]==2

    conductors=core.pl_box_conductors(legs)
    black=next(x for x in conductors if x["core_id"]=="black")
    grey=next(x for x in conductors if x["core_id"]=="grey")
    wiring=core.assign_pl_conductor_function(wiring,legs,core.pl_box_conductor_key(black),"switch:a")
    wiring=core.assign_pl_conductor_function(wiring,legs,core.pl_box_conductor_key(grey),"switch:b")
    summary=core.pl_wiring_requirement_summary(req,wiring)
    assert summary["ok"]==2
    assert summary["missing"]==0


def test_one_physical_conductor_can_never_keep_two_switch_functions():
    sw=_combo(symbol="combo_row_2x1_socket")
    core.set_association_channel(sw,0,"a")
    core.set_association_channel(sw,1,"b")
    lamp=_lamp(associations=["a","b"])
    cable=_direct_cable(spec="5G1,5")
    legs=core.cable_legs_at_symbol([cable],lamp.uid)
    wiring=core.reconcile_pl_box_wiring([],legs)
    brown=next(x for x in core.pl_box_conductors(legs) if x["core_id"]=="brown")
    key=core.pl_box_conductor_key(brown)

    wiring=core.assign_pl_conductor_function(wiring,legs,key,"switch:a")
    wiring=core.assign_pl_conductor_function(wiring,legs,key,"switch:b")
    row=next(x for x in wiring if core.pl_box_conductor_key(x)==key)
    assert row["function"]=="switch:b"
    assert sum(1 for x in wiring if core.pl_box_conductor_key(x)==key)==1


def test_duplicate_conductors_for_same_direct_switch_output_are_flagged():
    sw=_combo(symbol="combo_row_2x1_socket")
    core.set_association_channel(sw,0,"a")
    lamp=_lamp(associations=["a"])
    cable=_direct_cable(spec="5G1,5")
    legs=core.cable_legs_at_symbol([cable],lamp.uid)
    req=core.pl_expected_switch_connections(lamp,[sw,lamp],[cable])
    wiring=core.reconcile_pl_box_wiring([],legs)
    conductors=core.pl_box_conductors(legs)
    for core_id in ("brown","black"):
        meta=next(x for x in conductors if x["core_id"]==core_id)
        wiring=core.assign_pl_conductor_function(wiring,legs,core.pl_box_conductor_key(meta),"switch:a")
    summary=core.pl_wiring_requirement_summary(req,wiring)
    assert summary["duplicate"]==1
    assert summary["ok"]==0


def test_related_switch_without_direct_cable_is_information_not_hard_requirement():
    sw=_combo(symbol="combo_row_2x1_socket")
    core.set_association_channel(sw,0,"a")
    lamp=_lamp(associations=["a"])
    req=core.pl_expected_switch_connections(lamp,[sw,lamp],[])
    assert len(req)==1
    assert req[0]["direct"] is False
    assert req[0]["required"] is False
    status=core.pl_switch_requirement_status(req,[])[0]
    assert status["state"]=="related"


def test_qt_source_exposes_switch_requirements_and_extra_cable_marking():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "Forventede tændinger fra tilhørsforhold" in source
    assert "Afbryderkanal" in source
    assert "Én fysisk leder kan kun have én funktion" in source
    assert "cable_display" in source
    assert "pl_expected_switch_connections" in source
