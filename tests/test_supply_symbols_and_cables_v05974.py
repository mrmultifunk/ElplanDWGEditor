import json
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument


def test_version_05974():
    assert APP_VERSION == core.APP_VERSION == "0.59.75"


def test_supply_symbols_are_available_on_dedicated_layers():
    group = core.SYMBOL_GROUPS["Tavler / forsyning"]
    assert group["Målertavle"] == "meter_board"
    assert group["Hovedjordforbindelse"] == "main_earthing_connection"
    assert core.symbol_layer("meter_board") == core.BOARD_LAYER
    assert core.symbol_layer("main_earthing_connection") == core.EARTHING_LAYER
    assert core.GENERATED_LAYER_COLORS[core.EARTHING_LAYER] == 3


def test_supply_symbol_geometry_and_connection_points():
    for symbol in ("meter_board", "main_earthing_connection"):
        assert core.symbol_primitives(symbol, 100.0)
        x1, y1, x2, y2 = core.symbol_local_bbox(symbol, 100.0)
        assert x2 > x1 and y2 > y1
        assert core.symbol_connection_points(symbol, 100.0)

    meter_marks = [
        primitive for primitive in core.symbol_primitives("meter_board", 100.0)
        if primitive[0] == "upright_text"
    ]
    assert len(meter_marks) == 1
    assert meter_marks[0][3] == "M"


def test_requested_supply_and_protective_conductor_presets():
    for spec in ("1G2,5", "1G6", "1G10", "4X10"):
        assert spec in core.CABLE_SPEC_PRESETS

    for spec in ("1G2,5", "1G6", "1G10"):
        conductors = core.cable_conductor_preset(spec)
        assert [row["core_id"] for row in conductors] == ["pe"]
        assert conductors[0]["protective"] is True

    four_x = core.cable_conductor_preset("4X10")
    assert [row["core_id"] for row in four_x] == ["brown", "black", "grey", "blue"]
    assert all(not row.get("protective", False) for row in four_x)


def test_main_cable_type_dropdown_uses_shared_presets():
    source = Path("qt_cable_panel.py").read_text(encoding="utf-8")
    assert "self.cable_spec_combo.addItems(" in source
    assert "list(core.CABLE_SPEC_PRESETS)" in source
    assert '"1G2,5", "1G6", "1G10"' not in source


def test_supply_and_earthing_cable_categories_are_standard():
    rows = {row["id"]: row for row in core.default_cable_category_records()}
    assert rows["earthing_bonding"]["name"] == "Udligning / beskyttelsesleder"
    assert "hovedjordforbindelse" in rows["earthing_bonding"]["description"].lower()
    assert rows["service_main"]["name"] == "Stikledning / hovedledning"
    assert "måler" in rows["service_main"]["description"].lower()


def test_existing_project_receives_new_categories_once(tmp_path):
    path = tmp_path / "project.elplan.json"
    path.write_text(json.dumps({
        "version": "0.59.73",
        "source_file": "",
        "cable_categories": [
            {"id": "sockets", "name": "Stikkontakter", "color": "#112233", "line_style": "solid"},
            {"id": "other", "name": "Øvrige", "color": "#d00000", "line_style": "solid"},
        ],
        "placements": [],
        "cables": [],
        "texts": [],
        "rooms": [],
        "layer_visibility": {},
    }), encoding="utf-8")

    loaded = ProjectDocument.load(path)
    by_id = {row["id"]: row for row in loaded.raw["cable_categories"]}
    assert {"earthing_bonding", "service_main"} <= set(by_id)
    assert by_id["sockets"]["color"] == "#112233"

    loaded.raw["cable_categories"] = [
        row for row in loaded.raw["cable_categories"] if row["id"] != "service_main"
    ]
    loaded.save()
    reloaded = ProjectDocument.load(path)
    assert "service_main" not in {row["id"] for row in reloaded.raw["cable_categories"]}
