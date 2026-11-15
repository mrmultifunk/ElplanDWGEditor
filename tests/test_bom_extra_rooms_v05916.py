from pathlib import Path
import tempfile

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def _room(name, code, x0, y0, x1, y1):
    return core.RoomPlacement(name=name, code=code, points=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)], label_x=(x0+x1)/2, label_y=(y0+y1)/2)


def _catalog():
    return [{"article_no":"A1","description":"Stikkontakt","manufacturer":"Test","unit":"stk"}]


def test_extra_bom_room_is_additive_but_all_rooms_total_is_not_duplicated():
    hall=_room("Gang","R01",0,0,10,10)
    kitchen=_room("Køkken","R02",10,0,20,10)
    p=core.Placement(symbol="socket",x=5,y=5,label="Køleskab")
    bindings={p.uid:{"symbol":[{"article_no":"A1","qty":1}]}}
    additions={p.uid:[kitchen.uid]}

    all_rows,_=core.build_bom([p],_catalog(),bindings,rooms=[hall,kitchen],placement_room_additions=additions)
    hall_rows,_=core.build_bom([p],_catalog(),bindings,rooms=[hall,kitchen],room_filter_uid=hall.uid,placement_room_additions=additions)
    kitchen_rows,_=core.build_bom([p],_catalog(),bindings,rooms=[hall,kitchen],room_filter_uid=kitchen.uid,placement_room_additions=additions)

    assert all_rows[0]["qty"] == 1
    assert hall_rows[0]["qty"] == 1
    assert kitchen_rows[0]["qty"] == 1

    usage=core.bom_article_room_usage([p],bindings,[hall,kitchen],placement_room_additions=additions)
    assert core.room_display_text(hall) in usage["A1"]
    assert core.room_display_text(kitchen) in usage["A1"]


def test_bom_article_sources_respect_extra_room_filter():
    hall=_room("Gang","R01",0,0,10,10)
    kitchen=_room("Køkken","R02",10,0,20,10)
    p=core.Placement(symbol="socket",x=5,y=5,label="Fryser")
    bindings={p.uid:{"symbol":[{"article_no":"A1","qty":1}]}}
    additions={p.uid:[kitchen.uid]}
    got=core.bom_article_source_uids("A1",[p],bindings,[hall,kitchen],room_filter_uid=kitchen.uid,placement_room_additions=additions)
    assert got["placement_uids"] == [p.uid]
    assert got["cable_uids"] == []


def test_project_roundtrip_preserves_extra_bom_rooms_and_old_readers_can_ignore_top_level_field():
    doc=ProjectDocument.from_cad("demo.dxf")
    hall=_room("Gang","R01",0,0,10,10); kitchen=_room("Køkken","R02",10,0,20,10)
    p=core.Placement(symbol="socket",x=5,y=5)
    doc.rooms=[hall,kitchen]; doc.placements=[p]; doc.raw["placement_bom_room_additions"]={p.uid:[kitchen.uid]}
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/"demo.elplan.json"; doc.save(path); loaded=ProjectDocument.load(path)
        assert loaded.raw["version"] == APP_VERSION == "0.59.81"
        assert loaded.raw["placement_bom_room_additions"] == {p.uid:[kitchen.uid]}
