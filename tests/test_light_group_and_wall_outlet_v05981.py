from __future__ import annotations

import ast
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, placement_from_raw


ROOT=Path(__file__).resolve().parents[1]


def test_wall_light_outlet_is_a_wall_mounted_single_output_light():
    symbol="wall_light_outlet"
    assert core.SYMBOL_GROUPS["Belysning"]["Lampeudtag på væg (alm. dåse)"]==symbol
    assert core.association_role(symbol)=="light"
    assert core.symbol_layer(symbol)==core.LIGHT_OUTLET_LAYER
    assert core.symbol_primitives(symbol,100.0)
    assert core.symbol_mount_points(symbol,100.0)==[(0.0,92.0)]
    assert len(core.symbol_connection_points(symbol,100.0))==2
    assert core._is_wall_device(symbol)


def test_wall_outlet_has_no_pl_box_but_can_have_an_optional_bom_article():
    wall=placement_from_raw({
        "uid":"wall-1","symbol":"wall_light_outlet","x":0,"y":0,
        "pl_box_entries":{"1":{"cable_uid":"c1","point_index":0,"leg":"endpoint"}},
        "lamp_outlet_type":"lk_classic",
    })
    assert wall.pl_box_entries=={}
    assert wall.lamp_outlet_type=="generic"
    parts=core.bom_symbol_parts(wall.symbol)
    assert parts==[{"id":"outlet","label":"Lampeudtag i vægdåse","kind":"outlet","base":"wall_light_outlet","required":False}]


def test_two_physical_lights_can_share_one_switch_function():
    ceiling=core.Placement("light_connection",0,0,uid="ceiling")
    wall=core.Placement("wall_light_outlet",100,0,uid="wall")
    assert core.set_lights_shared_association([ceiling,wall],"c")==2
    assert core.light_output_associations(ceiling)==["c"]
    assert core.light_output_associations(wall)==["c"]


def test_multi_output_light_is_not_silently_grouped_without_output_choice():
    light=core.Placement(
        "light_connection",0,0,
        light_outputs=[
            {"id":"one","name":"Pendel","association":""},
            {"id":"two","name":"Spots","association":""},
        ],
    )
    assert not core.light_can_share_switch_group(light)
    assert core.set_lights_shared_association([light],"a")==0


def test_context_toolbar_exposes_same_switch_action_for_multi_selection():
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    workspace=(ROOT/"qt_workspace.py").read_text(encoding="utf-8")
    cable_attach=(ROOT/"qt_cable_attach.py").read_text(encoding="utf-8")
    ast.parse(app); ast.parse(workspace); ast.parse(cable_attach)
    assert APP_VERSION==core.APP_VERSION=="0.59.85"
    assert "group_selected_lights_same_switch" in app
    assert "Samme tænding…" in workspace
    assert "same_switch_ready" in workspace
    assert "wall_light_outlet" in cable_attach
