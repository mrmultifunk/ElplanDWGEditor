from __future__ import annotations

import ast
from pathlib import Path

import core_logic as core
from elplan_project.project_model import APP_VERSION, ProjectDocument, placement_from_raw


ROOT=Path(__file__).resolve().parents[1]


def _two_output_light():
    return placement_from_raw({
        "uid":"light-1","symbol":"light_connection","x":100,"y":100,
        "light_outputs":[
            {"id":"pendel","name":"Pendel","association":"a"},
            {"id":"spots","name":"Spots","association":"b"},
        ],
    })


def test_one_physical_light_has_two_stable_logical_outputs():
    light=_two_output_light()
    assert light.associations==["a"]
    assert core.light_output_associations(light)==["a","b"]
    assert core.association_display(light)=="T1:a · T2:b"
    assert [row["id"] for row in core.light_output_records(light)]==["pendel","spots"]


def test_switch_and_pl_requirements_see_both_outputs():
    light=_two_output_light()
    switch=core.Placement(symbol="switch_crown",x=0,y=0,uid="switch-1")
    core.sync_association_channels(switch,["a","b"])
    requirements=core.pl_expected_switch_connections(light,[switch],[])
    assert {row["association"] for row in requirements}=={"a","b"}


def test_spot_can_follow_one_specific_output():
    light=_two_output_light()
    chosen=core.light_output_by_id(light,"spots")
    spot=core.Placement(symbol="spot",x=110,y=100,parent_light_uid=light.uid,parent_light_output_id="spots")
    spot.associations=core.normalize_light_associations([chosen["association"]])
    assert chosen["name"]=="Spots"
    assert spot.associations==["b"]


def test_project_roundtrip_preserves_outputs_but_one_physical_placement():
    doc=ProjectDocument(); doc.placements=[_two_output_light()]
    raw=doc.to_dict(); assert len(raw["placements"])==1
    restored=placement_from_raw(raw["placements"][0])
    assert [row["id"] for row in restored.light_outputs]==["pendel","spots"]
    catalog=[{"article_no":"OUTLET","description":"Lampeudtag","unit":"stk"}]
    items,_missing=core.build_bom([restored],catalog,{restored.uid:{"outlet":[{"article_no":"OUTLET","qty":1.0}]}})
    row=next(row for row in items if row["article_no"]=="OUTLET")
    assert row["qty"]==1.0


def test_project_control_validates_each_output_separately():
    light=_two_output_light(); switch=core.Placement(symbol="switch_1",x=0,y=0,uid="switch-1")
    core.sync_association_channels(switch,["a"])
    issues=core.project_control_issues([light,switch],[])
    association_titles=[row["title"] for row in issues if row["category"]=="Tilknytning"]
    assert any("Spots" in title and "manglende" in title for title in association_titles)


def test_gui_exposes_output_editor_and_graphical_count_badge():
    app=(ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    graphics=(ROOT/"elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    ast.parse(app); ast.parse(graphics)
    assert APP_VERSION==core.APP_VERSION=="0.59.85"
    assert "light_outputs_table" in app
    assert "+ Tilføj tænding" in app
    assert "_choose_light_output" in app
    assert "str(len(outputs))" in graphics
