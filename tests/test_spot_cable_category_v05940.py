import json
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument


def test_spots_is_standard_cable_category():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"
    by_id = {row["id"]: row for row in core.default_cable_category_records()}
    assert by_id["spots"]["name"] == "Spots"
    assert "downlight" in by_id["spots"]["description"].lower()


def test_old_project_gets_spots_category_once(tmp_path: Path):
    path = tmp_path / "old.elplan.json"
    path.write_text(json.dumps({
        "version": "0.59.39",
        "source_file": "",
        "cable_categories": [
            {"id": "sockets", "name": "Stikkontakter", "color": "#d00000", "line_style": "solid"},
            {"id": "other", "name": "Øvrige", "color": "#d00000", "line_style": "solid"},
        ],
        "placements": [], "cables": [], "texts": [], "rooms": [], "layer_visibility": {},
    }), encoding="utf-8")
    doc = ProjectDocument.load(path)
    assert "spots" in {row["id"] for row in doc.raw["cable_categories"]}


def test_new_project_may_remove_spots_category(tmp_path: Path):
    path = tmp_path / "new.elplan.json"
    path.write_text(json.dumps({
        "version": "0.59.82",
        "source_file": "",
        "cable_categories": [
            {"id": "sockets", "name": "Stikkontakter", "color": "#d00000", "line_style": "solid"},
            {"id": "other", "name": "Øvrige", "color": "#d00000", "line_style": "solid"},
        ],
        "placements": [], "cables": [], "texts": [], "rooms": [], "layer_visibility": {},
    }), encoding="utf-8")
    doc = ProjectDocument.load(path)
    assert "spots" not in {row["id"] for row in doc.raw["cable_categories"]}
