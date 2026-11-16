from __future__ import annotations

import ast
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument, placement_from_raw


ROOT=Path(__file__).resolve().parents[1]


def test_light_normalization_keeps_one_relation_per_logical_output():
    assert core.normalize_light_associations([])==[]
    assert core.normalize_light_associations(["b","a","b"])==["a"]
    light=placement_from_raw({"symbol":"light_connection","x":0,"y":0,"associations":["c","a","b"]})
    assert light.associations==["a"]
    assert core.light_output_associations(light)==["a","b","c"]
    assert [row["association"] for row in light.light_outputs]==["a","b","c"]


def test_project_serialization_writes_separate_light_outputs():
    project=ProjectDocument()
    project.placements=[core.Placement(symbol="light_connection",x=0,y=0,associations=["c","a","b"])]
    row=project.to_dict()["placements"][0]
    assert row["associations"]==["a"]
    assert [output["association"] for output in row["light_outputs"]]==["a","b","c"]


def test_switch_channels_keep_stable_ids_and_may_share_a_letter():
    first=core.Placement(symbol="switch_2way",x=0,y=0,uid="switch-one")
    second=core.Placement(symbol="switch_2way",x=1,y=0,uid="switch-two")
    core.set_association_channel(first,0,"a")
    core.set_association_channel(second,0,"a")
    one=core.association_channel_records(first)[0]
    two=core.association_channel_records(second)[0]
    assert one["channel_id"]=="switch-one:0"
    assert two["channel_id"]=="switch-two:0"
    assert one["association"]==two["association"]=="a"


def test_project_control_reports_unlinked_lights_and_empty_switch_relations():
    switch=core.Placement(symbol="switch_1",x=0,y=0,group="G1")
    core.set_association_channel(switch,0,"a")
    light=core.Placement(symbol="light_connection",x=100,y=0,group="L1")
    issues=core.project_control_issues([switch,light],[])
    titles=[row["title"] for row in issues if row["category"]=="Tilknytning"]
    assert any("ikke tilknyttet" in title for title in titles)
    assert any("intet lampested" in title for title in titles)


def test_gui_source_contains_channel_table_and_transactional_finish():
    source=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    graphics=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    ast.parse(source); ast.parse(graphics)
    assert APP_VERSION==core.APP_VERSION=="0.59.84"
    assert "assoc_channels_table" in source
    assert "_association_session_before" in source
    assert "Enter gemmer hele ændringen" in source
    assert "associationFinishRequested" in graphics
    assert "target.associations=[active]" in source
