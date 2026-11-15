from pathlib import Path
import json

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def _lamp(uid="lamp1", associations=None):
    return core.Placement(symbol="light_connection", x=0, y=0, uid=uid, associations=list(associations or []))


def _cable(uid, spec="3G1,5", points=None, connection_index=0, cable_id="K01"):
    points=list(points or [(0,0),(100,0)])
    cable=core.CablePlacement(points=points, uid=uid, cable_id=cable_id, cable_spec=spec)
    core.set_cable_symbol_connections(cable,[{"point_index":connection_index,"symbol_uid":"lamp1","symbol_port":0}])
    return cable


def test_standard_conductor_presets_3g_5g_7g():
    p3=core.cable_conductor_preset("3G1,5")
    assert [x["core_id"] for x in p3]==["pe","blue","brown"]
    assert [x["color_name"] for x in p3]==["Gul/grøn","Blå","Brun"]

    p5=core.cable_conductor_preset("N1XZ1 5G2,5")
    assert [x["core_id"] for x in p5]==["pe","blue","brown","black","grey"]
    assert [x["color_name"] for x in p5]==["Gul/grøn","Blå","Brun","Sort","Grå"]

    p7=core.cable_conductor_preset("7G1,5")
    assert [x["core_id"] for x in p7]==["pe","blue","brown","black","grey","red","white"]
    assert [x["color_name"] for x in p7]==["Gul/grøn","Blå","Brun","Sort","Grå","Rød","Hvid"]
    assert [x["number"] for x in p7]==[None]*7


def test_cat7_is_not_misread_as_7g_installation_cable():
    assert core.cable_conductor_preset("CAT7 S/FTP")==[]


def test_loopthrough_has_independent_conductors_on_both_cable_legs():
    cable=_cable("c1","3G1,5",[(-100,0),(0,0),(100,0)],1)
    legs=core.cable_legs_at_symbol([cable],"lamp1")
    conductors=core.pl_box_conductors(legs)
    assert len(legs)==2
    assert len(conductors)==6
    assert {(x["leg"],x["core_id"]) for x in conductors}=={
        ("before","pe"),("before","blue"),("before","brown"),
        ("after","pe"),("after","blue"),("after","brown"),
    }


def test_new_5g_wiring_starts_completely_unassigned():
    cable=_cable("c1","5G1,5")
    legs=core.cable_legs_at_symbol([cable],"lamp1")
    wiring=core.reconcile_pl_box_wiring([],legs)
    functions={x["core_id"]:x["function"] for x in wiring}
    assert functions=={"pe":"","blue":"","brown":"","black":"","grey":""}
    status=core.pl_box_wiring_status(wiring,legs)
    assert status["known"]==5
    assert status["assigned"]==0
    assert status["live_unassigned"]==3


def test_new_7g_wiring_starts_completely_unassigned():
    cable=_cable("c1","7G1,5")
    legs=core.cable_legs_at_symbol([cable],"lamp1")
    wiring=core.reconcile_pl_box_wiring([],legs)
    functions={x["core_id"]:x["function"] for x in wiring}
    assert set(functions)=={"pe","blue","brown","black","grey","red","white"}
    assert all(function=="" for function in functions.values())

def test_0480_numbered_7g_wiring_migrates_to_colour_profile():
    cable=_cable("c1","7G1,5")
    legs=core.cable_legs_at_symbol([cable],"lamp1")
    old=[
        {"cable_uid":"c1","point_index":0,"leg":"endpoint","core_id":"num1","function":"n","note":"gammel blå"},
        {"cable_uid":"c1","point_index":0,"leg":"endpoint","core_id":"num5","function":"switch:a","note":"gammel rød"},
    ]
    got=core.reconcile_pl_box_wiring(old,legs)
    by={x["core_id"]:x for x in got}
    assert by["blue"]["function"]=="n"
    assert by["blue"]["note"]=="gammel blå"
    assert by["red"]["function"]=="switch:a"
    assert by["red"]["note"]=="gammel rød"


def test_function_options_follow_lamp_associations():
    opts=dict(core.pl_wiring_function_options(["a","c"]))
    assert opts["switch:a"]=="Tænding a → lampested L(a)"
    assert opts["switch:c"]=="Tænding c → lampested L(c)"
    assert "switch:lamp" not in opts
    generic=dict(core.pl_wiring_function_options([]))
    assert generic["switch:lamp"]=="Tænding → lampested L"


def test_reconcile_wiring_survives_point_index_change_and_drops_removed_cores():
    old=[
        {"cable_uid":"c1","point_index":1,"leg":"before","core_id":"black","function":"switch:a","note":"retur"},
        {"cable_uid":"c1","point_index":1,"leg":"before","core_id":"pe","function":"pe","note":""},
    ]
    leg={"cable_uid":"c1","point_index":3,"leg":"before","leg_caption":"Side A","cable_id":"K01","cable_spec":"5G1,5"}
    got=core.reconcile_pl_box_wiring(old,[leg])
    black=next(x for x in got if x["core_id"]=="black")
    assert black["point_index"]==3
    assert black["function"]=="switch:a"
    assert black["note"]=="retur"

    leg3=dict(leg); leg3["cable_spec"]="3G1,5"
    got3=core.reconcile_pl_box_wiring(got,[leg3])
    assert {x["core_id"] for x in got3}=={"pe","blue","brown"}


def test_project_roundtrip_keeps_wiring_and_strips_dead_reference(tmp_path: Path):
    lamp=_lamp(associations=["a"])
    cable=_cable("c1","3G1,5")
    legs=core.cable_legs_at_symbol([cable],"lamp1")
    wiring=core.reconcile_pl_box_wiring([],legs)
    for row in wiring:
        if row["core_id"]=="brown":row["function"]="switch:a"
    wiring.append({"cable_uid":"deleted","point_index":0,"leg":"endpoint","core_id":"brown","function":"l","note":"dead"})
    lamp.pl_box_wiring=wiring
    lamp.pl_box_entries={"1":{"cable_uid":"c1","point_index":0,"leg":"endpoint","note":""}}
    doc=ProjectDocument.from_cad(tmp_path/"plan.dxf")
    doc.placements=[lamp]; doc.cables=[cable]
    path=tmp_path/"p.elplan.json"; doc.save(path)
    raw=json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"]==APP_VERSION=="0.59.79"
    saved=raw["placements"][0]["pl_box_wiring"]
    assert len(saved)==3
    assert next(x for x in saved if x["core_id"]=="brown")["function"]=="switch:a"
    assert not any(x["cable_uid"]=="deleted" for x in saved)
    loaded=ProjectDocument.load(path)
    assert next(x for x in loaded.placements[0].pl_box_wiring if x["core_id"]=="brown")["function"]=="switch:a"


def test_clipboard_does_not_copy_pl_wiring():
    lamp=_lamp(); lamp.pl_box_wiring=[{"cable_uid":"c1","point_index":0,"leg":"endpoint","core_id":"brown","function":"l","note":""}]
    copied=core.placement_from_clipboard_payload(core.symbol_clipboard_payload(lamp))
    assert copied is not None
    assert copied.pl_box_wiring==[]


def test_qt_source_contains_wiring_tab_and_graphic():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8") + Path("qt_app.py").read_text(encoding="utf-8")
    assert "class PLWiringDiagramWidget" in source
    assert 'self.tabs.addTab(wiring_tab,"Lederfordeling")' in source
    assert "Sæt standard PE/N" not in source
    assert "Funktion / samling" in source
    assert "functionAssigned=Signal(object,str)" in source
    assert "Vælg eller træk en farvet leder" in source
    assert "gul/grøn · blå · brun · sort · grå · rød · hvid" in source
    assert "_diagram_function_assigned" in source
    assert "_apply_pl_box_config" in source
