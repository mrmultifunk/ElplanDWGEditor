from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument


def _three_stop_cable():
    cable=core.CablePlacement(
        points=[(0,0),(100,0),(100,100),(200,100),(200,200)],
        cable_id="K7",
        cable_spec="7G1,5",
        orthogonal=True,
        symbol_connections=[
            {"point_index":0,"symbol_uid":"lamp_a","symbol_port":0},
            {"point_index":2,"symbol_uid":"lamp_b","symbol_port":0},
            {"point_index":4,"symbol_uid":"lamp_c","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    return cable


def test_version_and_mixed_route_field():
    assert APP_VERSION == core.APP_VERSION == "0.59.80"
    cable=core.CablePlacement(points=[(0,0),(10,0)])
    assert cable.route_section_modes == []


def test_only_one_connection_section_can_be_converted_to_free():
    cable=_three_stop_cable()
    first,second=core.cable_connection_sections(cable)
    assert core.cable_route_section_mode(cable,first["a"],first["b"]) == "orthogonal"
    points,connections=core.convert_cable_route_section_geometry(
        cable.points,core.cable_symbol_connections(cable),
        first["start_point_index"],first["end_point_index"],
        from_orthogonal=True,to_orthogonal=False,
    )
    cable.points=points
    core.set_cable_symbol_connections(cable,connections)
    refreshed=core.cable_connection_sections(cable)
    core.set_cable_route_section_mode(cable,refreshed[0]["a"],refreshed[0]["b"],"free")

    # Kun A→B mister det automatiske 90°-knæk. B→C står uændret.
    assert cable.points == [(0.0,0.0),(100.0,100.0),(200.0,100.0),(200.0,200.0)]
    rows=core.cable_symbol_connections(cable)
    assert [r["point_index"] for r in rows] == [0,1,3]
    sections=core.cable_connection_sections(cable)
    assert core.cable_route_section_mode(cable,sections[0]["a"],sections[0]["b"]) == "free"
    assert core.cable_route_section_mode(cable,sections[1]["a"],sections[1]["b"]) == "orthogonal"
    assert cable.orthogonal is True  # global/default mode is untouched



def test_middle_section_only_can_be_diagonal_in_long_orthogonal_cable():
    cable=core.CablePlacement(
        points=[(0,0),(100,0),(100,100),(200,100),(200,200),(300,200),(300,300)],
        orthogonal=True,
        symbol_connections=[
            {"point_index":0,"symbol_uid":"a","symbol_port":0},
            {"point_index":2,"symbol_uid":"b","symbol_port":0},
            {"point_index":4,"symbol_uid":"c","symbol_port":0},
            {"point_index":6,"symbol_uid":"d","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    middle=core.cable_connection_sections(cable)[1]
    pts,rows=core.convert_cable_route_section_geometry(
        cable.points,core.cable_symbol_connections(cable),
        middle["start_point_index"],middle["end_point_index"],
        from_orthogonal=True,to_orthogonal=False,
    )
    cable.points=pts; core.set_cable_symbol_connections(cable,rows)
    middle=core.cable_connection_sections(cable)[1]
    core.set_cable_route_section_mode(cable,middle["a"],middle["b"],"free")
    assert cable.points == [(0.0,0.0),(100.0,0.0),(100.0,100.0),(200.0,200.0),(300.0,200.0),(300.0,300.0)]
    sections=core.cable_connection_sections(cable)
    assert [core.cable_route_section_mode(cable,x["a"],x["b"]) for x in sections] == ["orthogonal","free","orthogonal"]


def test_section_can_be_converted_back_to_orthogonal_without_touching_next_section():
    cable=_three_stop_cable()
    first=core.cable_connection_sections(cable)[0]
    pts,rows=core.convert_cable_route_section_geometry(
        cable.points,core.cable_symbol_connections(cable),
        first["start_point_index"],first["end_point_index"],
        from_orthogonal=True,to_orthogonal=False,
    )
    cable.points=pts; core.set_cable_symbol_connections(cable,rows)
    first=core.cable_connection_sections(cable)[0]
    core.set_cable_route_section_mode(cable,first["a"],first["b"],"free")
    pts,rows=core.convert_cable_route_section_geometry(
        cable.points,core.cable_symbol_connections(cable),
        first["start_point_index"],first["end_point_index"],
        from_orthogonal=False,to_orthogonal=True,
    )
    cable.points=pts; core.set_cable_symbol_connections(cable,rows)
    first=core.cable_connection_sections(cable)[0]
    core.set_cable_route_section_mode(cable,first["a"],first["b"],"orthogonal")
    assert cable.points == [(0.0,0.0),(100.0,0.0),(100.0,100.0),(200.0,100.0),(200.0,200.0)]
    assert cable.route_section_modes == []  # same as global default => no override needed


def test_local_route_mode_applies_to_breakpoints_inside_overridden_section():
    cable=_three_stop_cable()
    first=core.cable_connection_sections(cable)[0]
    core.set_cable_route_section_mode(cable,first["a"],first["b"],"free")
    assert core.cable_route_mode_for_point_index(cable,1) == "free"
    assert core.cable_route_mode_for_point_index(cable,3) == "orthogonal"


def test_attach_new_lamp_inside_mixed_section_splits_override():
    cable=core.CablePlacement(
        points=[(0,0),(100,100)],orthogonal=True,
        symbol_connections=[
            {"point_index":0,"symbol_uid":"a","symbol_port":0},
            {"point_index":1,"symbol_uid":"b","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    section=core.cable_connection_sections(cable)[0]
    core.set_cable_route_section_mode(cable,section["a"],section["b"],"free")
    result=core.attach_symbol_to_existing_cable(cable,"mid",0,(50,50),segment_index=0)
    assert result["status"] == "attached"
    sections=core.cable_connection_sections(cable)
    assert len(sections) == 2
    assert [core.cable_route_section_mode(cable,s["a"],s["b"]) for s in sections] == ["free","free"]


def test_legacy_route_section_override_materialises_on_physical_cables(tmp_path):
    import json
    from dataclasses import asdict
    cable=_three_stop_cable()
    section=core.cable_connection_sections(cable)[0]
    core.set_cable_route_section_mode(cable,section["a"],section["b"],"free")
    path=tmp_path/"mixed.elplan.json"
    path.write_text(json.dumps({"version":"0.54.3","source_file":"","placements":[],"cables":[asdict(cable)],"texts":[],"layer_visibility":{}}),encoding="utf-8")
    loaded=ProjectDocument.load(path)
    assert len(loaded.cables)==2
    assert [c.orthogonal for c in loaded.cables] == [False,True]
    assert all(c.route_section_modes==[] for c in loaded.cables)
    assert all(core.cable_is_physical_segment(c) for c in loaded.cables)
    assert loaded.raw["version"] == "0.59.80"


def test_qt_source_exposes_panel_and_context_shortcut():
    app=Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_cable_panel.py").read_text(encoding="utf-8")
    mixin=Path("qt_cable_sections.py").read_text(encoding="utf-8")
    graphics=Path("qt_graphics.py").read_text(encoding="utf-8")
    assert 'QGroupBox("Indstillinger pr. afsnit")' in app
    assert 'self.cable_section_group.setVisible(False)' in app
    assert 'item.signals.contextRequested.connect(self._cable_context_menu)' in app
    assert 'Fri / diagonal for dette kabel' in mixin
    assert 'Ortogonal (90°) for dette kabel' in mixin
    assert 'contextRequested = Signal(object, object, object)' in graphics
