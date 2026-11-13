from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument


def _three_stop_cable():
    cable=core.CablePlacement(
        points=[(0,0),(100,0),(100,100),(200,100),(200,200)],
        cable_id="K7",cable_spec="3G1,5",auto_label=True,orthogonal=True,
        symbol_connections=[
            {"point_index":0,"symbol_uid":"lamp_a","symbol_port":0},
            {"point_index":2,"symbol_uid":"lamp_b","symbol_port":0},
            {"point_index":4,"symbol_uid":"lamp_c","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    return cable


def test_version_and_default_section_spec_field():
    assert APP_VERSION == core.APP_VERSION == "0.59.75"
    cable=core.CablePlacement(points=[(0,0),(10,0)],cable_spec="3G1,5")
    assert cable.spec_section_overrides == []


def test_only_selected_physical_section_changes_cable_type():
    cable=_three_stop_cable()
    first,second=core.cable_connection_sections(cable)
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    assert core.cable_spec_for_section(cable,first["a"],first["b"]) == "3G1,5"
    assert core.cable_spec_for_section(cable,second["a"],second["b"]) == "5G1,5"
    assert cable.cable_spec == "3G1,5"
    assert len(cable.spec_section_overrides) == 1


def test_pl_legs_receive_effective_spec_on_each_side_of_middle_lamp():
    cable=_three_stop_cable()
    second=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    legs=core.cable_legs_at_symbol([cable],"lamp_b")
    by_side={row["leg"]:row["cable_spec"] for row in legs}
    assert by_side == {"before":"3G1,5","after":"5G1,5"}
    assert len(core.cable_conductor_preset(by_side["before"])) == 3
    assert len(core.cable_conductor_preset(by_side["after"])) == 5


def test_inserting_lamp_inside_overridden_spec_section_splits_override():
    cable=core.CablePlacement(
        points=[(0,0),(100,0)],cable_spec="3G1,5",orthogonal=False,
        symbol_connections=[
            {"point_index":0,"symbol_uid":"a","symbol_port":0},
            {"point_index":1,"symbol_uid":"b","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    section=core.cable_connection_sections(cable)[0]
    core.set_cable_spec_for_section(cable,section["a"],section["b"],"5G1,5")
    result=core.attach_symbol_to_existing_cable(cable,"mid",0,(50,0),segment_index=0)
    assert result["status"] == "attached"
    sections=core.cable_connection_sections(cable)
    assert len(sections) == 2
    assert [core.cable_spec_for_section(cable,s["a"],s["b"]) for s in sections] == ["5G1,5","5G1,5"]


def test_mixed_spec_length_is_split_by_effective_type():
    cable=_three_stop_cable()
    second=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    lengths=core.cable_length_by_spec_metres(cable,0.01)
    assert lengths == {"3G1,5":2.0,"5G1,5":2.0}
    assert sum(lengths.values()) == core.cable_length_metres(cable,0.01)


def test_mixed_spec_uses_section_labels_and_main_label_does_not_lie():
    cable=_three_stop_cable()
    second=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    assert core.cable_display_label(cable) == "K7"
    labels=core.cable_section_spec_labels(cable)
    assert [r["cable_spec"] for r in labels] == ["3G1,5","5G1,5"]


def test_legacy_section_spec_materialises_on_physical_cables(tmp_path):
    import json
    from dataclasses import asdict
    cable=_three_stop_cable(); section=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,section["a"],section["b"],"5G1,5")
    path=tmp_path/"mixed_spec.elplan.json"
    path.write_text(json.dumps({"version":"0.54.3","source_file":"","placements":[],"cables":[asdict(cable)],"texts":[],"layer_visibility":{}}),encoding="utf-8")
    loaded=ProjectDocument.load(path)
    assert len(loaded.cables)==2
    assert [c.cable_spec for c in loaded.cables] == ["3G1,5","5G1,5"]
    assert all(c.spec_section_overrides==[] for c in loaded.cables)
    assert loaded.raw["version"] == "0.59.75"


def test_qt_source_exposes_section_spec_editor_and_context_menu():
    app=Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_cable_panel.py").read_text(encoding="utf-8")
    mixin=Path("qt_cable_sections.py").read_text(encoding="utf-8")
    graphics=Path("qt_graphics.py").read_text(encoding="utf-8")
    assert 'QGroupBox("Indstillinger pr. afsnit")' in app
    assert 'self.cable_section_group.setVisible(False)' in app
    assert 'Kabeltype for dette kabel' in mixin
    assert 'apply_selected_cable_section_spec' in mixin
    assert 'section_spec_labels' in graphics


def test_bom_does_not_count_one_global_article_across_mixed_specs():
    cable=_three_stop_cable()
    second=core.cable_connection_sections(cable)[1]
    core.set_cable_spec_for_section(cable,second["a"],second["b"],"5G1,5")
    catalog=[{
        "article_no":"A3","description":"3G cable","manufacturer":"Test","unit":"m",
        "cable_spec":"3G1,5","package_length_m":0,
    }]
    rows,unassigned=core.build_bom(
        [],catalog,{},cables=[cable],cable_bindings={cable.uid:"A3"},
        metres_per_unit=0.01,reserve_percent=0,
    )
    assert not any(r["article_no"]=="A3" for r in rows)
    by_spec={r["part_label"]:r for r in unassigned if r["symbol"]=="__cable__"}
    assert by_spec["3G1,5"]["qty"] == 2.0
    assert by_spec["5G1,5"]["qty"] == 2.0
    assert "afsnitsvis artikeltilknytning" in by_spec["3G1,5"]["detail"]
