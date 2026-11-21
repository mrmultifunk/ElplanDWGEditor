import json

import core_logic as core
from elplan_project.project_model import ProjectDocument


def test_combo_keeps_physical_channel_order_when_correspondence_reuses_older_letter():
    p = core.Placement(symbol="combo_row_2x1_2way_socket", x=0, y=0)
    assert core.association_channel_bases(p.symbol) == ["switch_1", "switch_1", "switch_2way"]

    # Typisk virkelig situation: a findes allerede på en anden korrespondance.
    # De to 1-polede får derfor b og c, mens korrespondancedelen skal genbruge a.
    core.set_association_channel(p, 0, "b")
    core.set_association_channel(p, 1, "c")
    core.set_association_channel(p, 2, "a")

    assert p.association_channels == ["b", "c", "a"]
    assert p.associations == ["a", "b", "c"]  # samlet liste må gerne være sorteret
    assert core.association_display(p) == "A1:b · A2:c · A3:a"
    assert core.association_channel_prefers_existing(p.symbol, 0) is False
    assert core.association_channel_prefers_existing(p.symbol, 1) is False
    assert core.association_channel_prefers_existing(p.symbol, 2) is True


def test_combo_channel_can_be_cleared_without_legacy_list_filling_it_back():
    p = core.Placement(symbol="combo_row_2x1_2way_socket", x=0, y=0)
    for i, letter in enumerate(("b", "c", "a")):
        core.set_association_channel(p, i, letter)
    core.set_association_channel(p, 1, "")
    assert p.association_channels == ["b", "", "a"]
    assert p.associations == ["a", "b"]
    assert core.first_unassigned_association_channel(p) == 1
    assert core.assigned_association_channel_count(p) == 2


def test_custom_combo_has_distinct_channel_descriptions():
    symbol = core.make_custom_combo_code(["switch_1", "switch_1", "switch_2way"], "socket")
    assert core.association_capacity(symbol) == 3
    assert core.association_channel_caption(symbol, 0) == "Modul 1 · 1-polet"
    assert core.association_channel_caption(symbol, 1) == "Modul 2 · 1-polet"
    assert core.association_channel_caption(symbol, 2) == "Modul 3 · korrespondance"


def test_channel_mapping_roundtrips_project_file(tmp_path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    project = ProjectDocument.from_cad(source)
    p = core.Placement(symbol="combo_row_2x1_2way_socket", x=10, y=20)
    core.set_association_channel(p, 0, "b")
    core.set_association_channel(p, 1, "c")
    core.set_association_channel(p, 2, "a")
    project.placements.append(p)

    out = tmp_path / "combo.elplan.json"
    project.save(out)
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["version"] == "0.59.85"
    assert raw["placements"][0]["association_channels"] == ["b", "c", "a"]

    loaded = ProjectDocument.load(out)
    q = loaded.placements[0]
    assert q.association_channels == ["b", "c", "a"]
    assert q.associations == ["a", "b", "c"]
    assert core.association_display(q) == "A1:b · A2:c · A3:a"


def test_old_project_without_channel_mapping_is_migrated_sequentially(tmp_path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    path = tmp_path / "old.elplan.json"
    path.write_text(json.dumps({
        "version": "0.35.2",
        "source_file": str(source),
        "placements": [{
            "symbol": "combo_row_2x1_2way_socket", "x": 0, "y": 0,
            "associations": ["a", "b", "c"]
        }],
        "cables": [], "texts": []
    }), encoding="utf-8")
    project = ProjectDocument.load(path)
    assert project.placements[0].association_channels == ["a", "b", "c"]
