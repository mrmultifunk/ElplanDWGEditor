from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, placement_from_raw


def test_version_and_spot_group_fields_are_persistent():
    assert APP_VERSION == core.APP_VERSION == "0.59.77"
    p = placement_from_raw({
        "symbol": "spot", "x": 10, "y": 20,
        "spot_group_id": "group-a", "spot_group_name": "Spotgruppe 1",
        "parent_light_uid": "light-a",
    })
    assert p.spot_group_id == "group-a"
    assert p.spot_group_name == "Spotgruppe 1"
    assert p.parent_light_uid == "light-a"


def test_single_spot_clipboard_does_not_keep_logical_group_or_parent():
    p = core.Placement(
        symbol="spot", x=0, y=0,
        spot_group_id="old-group", spot_group_name="Spotgruppe 1",
        parent_light_uid="light-a", associations=["a"],
    )
    copied = core.placement_from_clipboard_payload(core.symbol_clipboard_payload(p))
    assert copied is not None
    assert copied.spot_group_id == ""
    assert copied.spot_group_name == ""
    assert copied.parent_light_uid == ""
    assert copied.associations == []


def test_multi_spot_clipboard_preserves_internal_group_with_new_id():
    p1 = core.Placement(symbol="spot", x=0, y=0, spot_group_id="old-group", spot_group_name="Spotgruppe 1", parent_light_uid="light-a")
    p2 = core.Placement(symbol="spot", x=100, y=0, spot_group_id="old-group", spot_group_name="Spotgruppe 1", parent_light_uid="light-a")
    copied = core.placements_from_clipboard_payload(core.symbols_clipboard_payload([p1, p2]))
    assert len(copied) == 2
    assert copied[0].spot_group_id
    assert copied[0].spot_group_id == copied[1].spot_group_id
    assert copied[0].spot_group_id != "old-group"
    assert {p.spot_group_name for p in copied} == {"Spotgruppe 1"}
    assert all(p.parent_light_uid == "" for p in copied)


def test_downlight_cable_is_in_predefined_article_catalog():
    lookup = {a["article_no"]: a for a in core.load_predefined_article_catalog()}
    art = lookup["5401046168"]
    assert art["kind"] == "cable"
    assert art["cable_spec"] == "3G1,5"
    assert art["ean"] == "5705157430506"
    assert art["package_length_m"] == 100.0
    assert "Downlight" in art["category"] or "downlight" in art["description"].lower()


def test_qt_spot_group_workflow_is_wired_into_existing_parent_relation():
    source = "\n".join((Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8") for name in ("qt_app.py", "qt_spots.py"))
    assert "def group_selected_spots(self)" in source
    assert "def select_spot_group(self)" in source
    assert "def dissolve_spot_group(self)" in source
    assert "spots=self._selected_spots(unlocked_only=True)" in source
    assert "expanded=self._expand_spots_to_groups(spots)" in source
    assert "spot_group_id=spot_group_id,spot_group_name=spot_group_name" in source
