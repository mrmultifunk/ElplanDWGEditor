from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_0520():
    assert APP_VERSION == core.APP_VERSION == "0.59.79"


def test_existing_orthogonal_route_converts_to_direct_free_geometry():
    points=[(0,0),(100,0),(100,50)]
    connections=[
        {"point_index":0,"symbol_uid":"A","symbol_port":0},
        {"point_index":2,"symbol_uid":"B","symbol_port":1},
    ]
    converted, mapped=core.convert_cable_route_mode_geometry(
        points, connections, from_orthogonal=True, to_orthogonal=False,
    )
    assert converted == [(0.0,0.0),(100.0,50.0)]
    assert [(r["point_index"],r["symbol_uid"]) for r in mapped] == [(0,"A"),(1,"B")]


def test_orthogonal_conversion_keeps_likely_clicked_waypoints():
    # Legacy 90-degree generator stores [elbow, clicked target] for each
    # diagonal span. Switching to free mode should discard the automatic
    # elbows but retain the user-level waypoints.
    points=[(0,0),(50,0),(50,40),(90,40),(90,80)]
    converted,_=core.convert_cable_route_mode_geometry(
        points, [], from_orthogonal=True, to_orthogonal=False,
    )
    assert converted == [(0.0,0.0),(50.0,40.0),(90.0,80.0)]


def test_physical_intermediate_connection_is_never_removed():
    points=[(0,0),(50,0),(50,40),(90,40),(90,80)]
    connections=[{"point_index":1,"symbol_uid":"MID","symbol_port":0}]
    converted,mapped=core.convert_cable_route_mode_geometry(
        points, connections, from_orthogonal=True, to_orthogonal=False,
    )
    assert (50.0,0.0) in converted
    mid=next(r for r in mapped if r["symbol_uid"]=="MID")
    assert converted[mid["point_index"]] == (50.0,0.0)


def test_free_route_can_be_converted_back_to_orthogonal():
    points=[(0,0),(100,50)]
    connections=[{"point_index":1,"symbol_uid":"END","symbol_port":0}]
    converted,mapped=core.convert_cable_route_mode_geometry(
        points, connections, from_orthogonal=False, to_orthogonal=True,
    )
    assert converted == [(0.0,0.0),(100.0,0.0),(100.0,50.0)]
    assert mapped[0]["point_index"] == 2


def test_cable_panel_applies_geometry_conversion_not_only_flag():
    source=Path("qt_app.py").read_text(encoding="utf-8")
    block=source[source.index("    def apply_selected_cable_properties"):source.index("    def _remove_cable",source.index("    def apply_selected_cable_properties"))]
    assert "convert_cable_route_mode_geometry" in block
    assert 'after["points"]=points' in block
    assert 'after["symbol_connections"]=connections' in block
    assert "Undo gendanner den tidligere rute" in source
