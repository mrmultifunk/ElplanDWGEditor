from pathlib import Path
import json

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def test_version_and_room_layer():
    assert APP_VERSION == core.APP_VERSION == "0.59.77"
    assert core.ROOM_LAYER == "EL-RUM"
    assert core.ROOM_LAYER in core.GENERATED_LAYERS


def test_room_geometry_and_overlap_resolution():
    outer=core.RoomPlacement(name="Stue",code="R01",points=[(0,0),(10,0),(10,10),(0,10)],label_x=5,label_y=5)
    inner=core.RoomPlacement(name="Køkkenzone",code="R02",points=[(2,2),(6,2),(6,6),(2,6)],label_x=4,label_y=4)
    assert core.room_contains_point(outer,5,5)
    assert core.room_contains_point(outer,0,5)  # boundary counts as inside
    assert not core.room_contains_point(outer,12,5)
    assert core.room_for_point([outer,inner],4,4) is inner
    assert core.room_display_text(outer)=="R01 · Stue"


def test_room_project_roundtrip(tmp_path):
    doc=ProjectDocument.from_cad(tmp_path/'plan.dxf')
    room=core.RoomPlacement(name="Køkken",code="KØK",points=[(0,0),(4000,0),(4000,3000),(0,3000)],label_x=1800,label_y=1500)
    doc.rooms=[room]
    path=tmp_path/'rooms.elplan.json'; doc.save(path)
    raw=json.loads(path.read_text(encoding='utf-8'))
    assert raw['version']=='0.59.77'
    assert raw['rooms'][0]['name']=='Køkken'
    loaded=ProjectDocument.load(path)
    assert len(loaded.rooms)==1
    assert loaded.rooms[0].code=='KØK'
    assert loaded.rooms[0].points[2]==(4000.0,3000.0)
    assert loaded.rooms[0].label_x==1800.0


def test_room_ui_source_has_quiet_default_and_room_based_cable_marking():
    src=Path('qt_rooms.py').read_text(encoding='utf-8')
    app=Path('qt_app.py').read_text(encoding='utf-8')
    graphics=Path('qt_graphics.py').read_text(encoding='utf-8')
    assert "room_boundaries_visible" in src
    assert "self.room_edit_mode or self.project.raw.get('room_boundaries_visible',False)" in src
    assert 'mark_symbols_in_room' not in src
    assert 'mark_cables_by_rooms' in src
    assert 'room_labels_visible' in src
    assert 'RoomLabelItem' in src and 'ItemIsMovable' in src
    assert 'roomFinished' in graphics and 'start_room_tool' in graphics
    assert 'self.view.roomFinished.connect(self._room_sketch_finished)' in app
    assert 'room=self.room_for_placement(placement)' in app
