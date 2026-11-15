from pathlib import Path
import json

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def test_version_05020():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_standard_cable_categories_have_definitions():
    rows = {row["id"]: row for row in core.default_cable_category_records()}
    assert all(str(row.get("description", "")).strip() for row in rows.values())
    assert rows["switch_cable"]["description"] == "Kabel fra afbryder til lampested."
    assert rows["interconnect"]["description"] == "Kabel mellem lampesteder på forskellige grupper."


def test_old_category_records_receive_standard_definitions_without_losing_style():
    rows = core.normalize_cable_category_records([
        {"id": "switch_cable", "name": "Tændkabel", "color": "#123456", "line_style": "dot"},
        {"id": "interconnect", "name": "Mellemkabel", "color": "#654321", "line_style": "dash"},
        {"id": "other", "name": "Øvrige", "color": "#d00000", "line_style": "solid"},
    ])
    by_id = {row["id"]: row for row in rows}
    assert by_id["switch_cable"]["description"] == "Kabel fra afbryder til lampested."
    assert by_id["switch_cable"]["color"] == "#123456"
    assert by_id["interconnect"]["description"] == "Kabel mellem lampesteder på forskellige grupper."
    assert by_id["interconnect"]["color"] == "#654321"


def test_custom_definition_is_preserved_and_can_be_empty():
    rows = core.normalize_cable_category_records([
        {"id": "switch_cable", "name": "Tændkabel", "description": "Min egen definition", "color": "#ea580c", "line_style": "dashdot"},
        {"id": "other", "name": "Øvrige", "description": "", "color": "#d00000", "line_style": "solid"},
    ])
    by_id = {row["id"]: row for row in rows}
    assert by_id["switch_cable"]["description"] == "Min egen definition"
    assert by_id["other"]["description"] == ""


def test_project_saved_in_05019_does_not_readd_deleted_standard_category(tmp_path):
    path = tmp_path / "saved_05019.elplan.json"
    data = {
        "version": "0.50.19",
        "source_file": "",
        "cable_categories": [
            {"id": "interconnect", "name": "Mellemkabel", "color": "#0e7490", "line_style": "dash"},
            {"id": "other", "name": "Øvrige", "color": "#d00000", "line_style": "solid"},
        ],
        "placements": [], "cables": [], "texts": [], "layer_visibility": {},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = ProjectDocument.load(path)
    ids = {row["id"] for row in loaded.raw["cable_categories"]}
    assert "interconnect" in ids
    assert "switch_cable" not in ids


def test_qt_exposes_definition_in_category_dialog_menu_and_cable_tool():
    source = Path("qt_app.py").read_text(encoding="utf-8")
    assert '"Definition"' in source
    assert 'rec.get("description","")' in source
    assert "self.cable_category_definition" in source
    assert "Qt.ItemDataRole.ToolTipRole" in source
