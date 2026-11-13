from dataclasses import asdict
from pathlib import Path

import core_logic as core
from project_model import ProjectDocument, cable_from_raw, APP_VERSION


def test_same_cable_can_have_many_symbol_connections():
    cable = core.CablePlacement(
        points=[(0,0),(10,0),(20,0),(30,0)],
        cable_id="K01",
        cable_spec="3G1,5",
        symbol_connections=[
            {"point_index":0,"symbol_uid":"board","symbol_port":0},
            {"point_index":1,"symbol_uid":"light1","symbol_port":0},
            {"point_index":2,"symbol_uid":"light2","symbol_port":1},
            {"point_index":3,"symbol_uid":"socket1","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    rows=core.cable_symbol_connections(cable)
    assert [r["symbol_uid"] for r in rows] == ["board","light1","light2","socket1"]
    assert cable.start_symbol_uid == "board"
    assert cable.end_symbol_uid == "socket1"
    assert core.cable_route_length(cable) == 30


def test_legacy_start_end_connections_migrate_automatically():
    cable=cable_from_raw({
        "points":[[0,0],[10,0],[20,0]],
        "start_symbol_uid":"old-start",
        "start_symbol_port":1,
        "end_symbol_uid":"old-end",
        "end_symbol_port":2,
    })
    assert cable.symbol_connections == [
        {"point_index":0,"symbol_uid":"old-start","symbol_port":1},
        {"point_index":2,"symbol_uid":"old-end","symbol_port":2},
    ]


def test_legacy_multi_connection_cable_loads_as_physical_cables(tmp_path: Path):
    cable=core.CablePlacement(
        points=[(0,0),(10,0),(20,0)], cable_id="K01",
        symbol_connections=[
            {"point_index":0,"symbol_uid":"a","symbol_port":0},
            {"point_index":1,"symbol_uid":"b","symbol_port":0},
            {"point_index":2,"symbol_uid":"c","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    path=tmp_path/"loopthrough.elplan.json"
    path.write_text(__import__("json").dumps({
        "version":"0.54.3","source_file":"","placements":[],
        "cables":[asdict(cable)],"texts":[],"layer_visibility":{},
    }),encoding="utf-8")
    loaded=ProjectDocument.load(path)
    assert loaded.raw["version"] == "0.59.75"
    assert len(loaded.cables)==2
    assert [[r["symbol_uid"] for r in core.cable_symbol_connections(c)] for c in loaded.cables] == [["a","b"],["b","c"]]
    assert [c.cable_id for c in loaded.cables] == ["K01","K02"]
    assert len({c.route_chain_uid for c in loaded.cables}) == 1
    assert all(core.cable_is_physical_segment(c) for c in loaded.cables)
    assert loaded.dirty is True


def test_lk_articles_get_direct_product_photo_url():
    article=core.normalize_article_catalog([{
        "article_no":"560D8720",
        "description":"LK FUGA SLIM design ramme 2x1 modul koksgrå",
        "manufacturer":"Schneider Electric / Lauritz Knudsen",
    }])[0]
    assert article["image_url"] == "https://www1.lk.dk/katalog/foto/jpg/560D8720.jpg"
    assert article["image_source"] == "LK / Schneider Electric"


def test_non_lk_article_does_not_get_lk_photo_url():
    article=core.normalize_article_catalog([{
        "article_no":"560D8720",
        "description":"Unrelated product",
        "manufacturer":"Other",
    }])[0]
    assert "image_url" not in article

def test_connection_indices_survive_geometry_point_removal():
    cable=core.CablePlacement(
        points=[(0,0),(5,0),(10,0),(15,0),(20,0)],
        symbol_connections=[
            {"point_index":0,"symbol_uid":"a","symbol_port":0},
            {"point_index":2,"symbol_uid":"b","symbol_port":0},
            {"point_index":4,"symbol_uid":"c","symbol_port":0},
        ],
    )
    core.set_cable_symbol_connections(cable,cable.symbol_connections)
    cable.points.pop(1)
    core.shift_cable_connection_indices(cable,2,-1)
    assert [(r["point_index"],r["symbol_uid"]) for r in cable.symbol_connections] == [(0,"a"),(1,"b"),(3,"c")]


def test_gui_source_exposes_loopthrough_workflow():
    source=(Path(__file__).resolve().parents[1] / "qt_app.py").read_text(encoding="utf-8") + (Path(__file__).resolve().parents[1] / "qt_cable_panel.py").read_text(encoding="utf-8")
    graphics=(Path(__file__).resolve().parents[1] / "qt_graphics.py").read_text(encoding="utf-8")
    assert "Kabler ved symbol" in source
    assert "Forløb:" in source
    assert "Start automatisk et nyt kabel efter afslutning" in source
    assert "self.cable_continuous.setChecked(False)" in source
    assert "_cable_connections" in graphics
    assert 'data["symbol_connections"] = connections' in graphics
