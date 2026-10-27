from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _rooms():
    return [
        core.RoomPlacement(name='Køkken', code='R01', points=[(0,0),(10,0),(10,10),(0,10)], label_x=5, label_y=5),
        core.RoomPlacement(name='Gang', code='R02', points=[(10,0),(20,0),(20,10),(10,10)], label_x=15, label_y=5),
        core.RoomPlacement(name='Stue', code='R03', points=[(20,0),(30,0),(30,10),(20,10)], label_x=25, label_y=5),
    ]


def test_room_cable_marking_follows_physical_route_without_touching_circuit():
    rooms=_rooms()
    cable=core.CablePlacement(points=[(-5,5),(5,5),(15,5),(25,5),(35,5)], cable_id='K12', circuit_id='G05', label='')
    assert [r.name for r in core.cable_rooms(cable,rooms)] == ['Køkken','Gang','Stue']
    assert core.cable_room_marking(cable,rooms,'name') == 'Køkken → Gang → Stue'
    assert core.cable_room_marking(cable,rooms,'code') == 'R01 → R02 → R03'
    assert core.cable_room_marking(cable,rooms,'display') == 'R01 · Køkken → R02 · Gang → R03 · Stue'
    assert cable.cable_id == 'K12'
    assert cable.circuit_id == 'G05'
    assert cable.label == ''


def test_room_cable_marking_one_room_and_no_room():
    rooms=_rooms()
    inside=core.CablePlacement(points=[(1,2),(8,8)])
    outside=core.CablePlacement(points=[(-10,-10),(-5,-5)])
    assert core.cable_room_marking(inside,rooms) == 'Køkken'
    assert core.cable_room_marking(outside,rooms) == ''


def test_room_ui_separates_text_and_boundary_visibility_and_drops_symbol_automarking():
    assert APP_VERSION == core.APP_VERSION == '0.59.74'
    src=Path('qt_rooms.py').read_text(encoding='utf-8')
    app=Path('qt_app.py').read_text(encoding='utf-8')
    assert 'Vis rumnavne' in src
    assert 'Vis rumafgrænsninger' in src
    assert "self.project.raw.get('room_labels_visible',True)" in src
    assert "self.room_edit_mode or self.project.raw.get('room_boundaries_visible',False)" in src
    assert "_quick_visible('text')" not in src
    assert 'mark_symbols_in_room' not in src
    assert 'Mærk kabler efter rum' in src
    assert "{'label':current},{'label':proposed}" in src
    assert 'Kabel-ID og gruppe/kreds ændres aldrig' in src
    assert 'room_view_menu=view_menu.addMenu("Rum")' in app
