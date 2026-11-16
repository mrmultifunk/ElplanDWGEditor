from pathlib import Path

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def test_lk_classic_profile_uses_n_l_pe_m1_m2_and_flags_third_switch():
    profile = core.pl_outlet_profile("lk_classic", ["a", "b", "c"])
    assert [x["label"] for x in profile["terminals"]] == ["N", "L", "PE", "M1", "M2"]
    assert [x["function_id"] for x in profile["terminals"]] == ["n", "l", "pe", "switch:a", "switch:b"]
    assert profile["unsupported_switches"] == ["switch:c"]
    assert [x.get("capacity") for x in profile["terminals"]] == [4, 4, 4, 4, 4]


def test_wiser_profile_uses_physical_pe_n_output_l_order():
    profile = core.pl_outlet_profile("wiser_dimmer", ["a", "b"])
    assert [x["label"] for x in profile["terminals"]] == ["PE", "N", "~", "L"]
    assert [x["function_id"] for x in profile["terminals"]] == ["pe", "n", "switch:a", "l"]
    assert profile["unsupported_switches"] == ["switch:b"]
    assert [x.get("capacity") for x in profile["terminals"]] == [2, 2, 2, 2]


def test_generic_profile_keeps_all_switch_functions_available():
    profile = core.pl_outlet_profile("generic", ["a", "b", "c"])
    assert [x["function_id"] for x in profile["terminals"]] == [
        "pe", "n", "l", "switch:a", "switch:b", "switch:c"
    ]
    assert profile["unsupported_switches"] == []


def test_outlet_type_aliases_are_normalized():
    assert core.normalize_pl_outlet_type("LK") == "lk_classic"
    assert core.normalize_pl_outlet_type("wiser") == "wiser_dimmer"
    assert core.normalize_pl_outlet_type("unknown") == "generic"


def test_project_roundtrip_preserves_lamp_outlet_type(tmp_path):
    project = ProjectDocument()
    project.source_file = "dummy.dxf"
    lamp = core.Placement("light_connection", 10, 20, lamp_outlet_type="wiser_dimmer")
    project.placements = [lamp]
    path = tmp_path / "p.elplan.json"
    project.path = path
    project.save()
    loaded = ProjectDocument.load(path)
    assert loaded.raw["version"] == APP_VERSION == "0.59.83"
    assert loaded.placements[0].lamp_outlet_type == "wiser_dimmer"


def test_copy_keeps_product_type_but_not_physical_wiring():
    lamp = core.Placement(
        "light_connection", 10, 20,
        lamp_outlet_type="lk_classic",
        pl_box_entries={"1": {"cable_uid": "c1", "point_index": 0, "leg": "endpoint", "note": ""}},
        pl_box_wiring=[{"cable_uid": "c1", "point_index": 0, "leg": "endpoint", "core_id": "blue", "function": "n", "note": ""}],
    )
    copied = core.placement_from_clipboard_payload(core.symbol_clipboard_payload(lamp))
    assert copied is not None
    assert copied.lamp_outlet_type == "lk_classic"
    assert copied.pl_box_entries == {}
    assert copied.pl_box_wiring == []
    assert copied.pl_box_splices == []


def test_qt_source_uses_terminal_based_editor_and_wago_support():
    source = (Path(__file__).resolve().parents[1] / "qt_pl_box.py").read_text(encoding="utf-8")
    assert 'QLabel("Lampeudtag:")' in source
    assert 'QPushButton("Vis tabel / avanceret")' in source
    assert 'core.pl_outlet_profile(self._outlet_type,self._associations)' in source
    assert 'def _draw_wago_blocks' in source
    assert 'wago_summary_label' in source
    assert '+ Samlemuffe / sløjfe' in source
    assert 'def _show_function_context_menu' in source
    assert '"FRIGØR / IKKE FORDELT"' not in source
    assert '"M1"' not in source  # physical labels come from core profile, not hard-coded widget state
