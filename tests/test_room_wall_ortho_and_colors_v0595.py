from pathlib import Path

import core_logic as core
from elplan_shared.interaction_math import room_wall_axis_snap


def test_room_wall_snap_can_be_horizontal_and_on_wall_at_same_time():
    hit=room_wall_axis_snap(100.0,3.0,(0.0,0.0),(100.0,-50.0,100.0,50.0),5.0)
    assert hit is not None
    x,y,gx,gy,label=hit
    assert (x,y)==(100.0,0.0)
    assert gx is None and gy==0.0
    assert label=='VANDRET'


def test_room_wall_snap_can_be_vertical_and_on_wall_at_same_time():
    hit=room_wall_axis_snap(2.0,100.0,(0.0,0.0),(-50.0,100.0,50.0,100.0),5.0)
    assert hit is not None
    x,y,gx,gy,label=hit
    assert (x,y)==(0.0,100.0)
    assert gx==0.0 and gy is None
    assert label=='LODRET'


def test_room_wall_axis_help_is_soft_and_alt_disables_only_combined_axis():
    assert room_wall_axis_snap(100.0,25.0,(0.0,0.0),(100.0,-50.0,100.0,50.0),5.0) is None
    assert room_wall_axis_snap(100.0,3.0,(0.0,0.0),(100.0,-50.0,100.0,50.0),5.0,disabled=True) is None


def test_room_color_is_per_room_project_data():
    room=core.RoomPlacement('Køkken',[(0,0),(10,0),(10,10)],color='#8b5cf6')
    assert room.color=='#8b5cf6'


def test_room_ui_combines_wall_and_axis_snap_and_exposes_color_swatches():
    graphics=Path('elplan_qt/qt_graphics.py').read_text(encoding='utf-8')
    rooms=Path('elplan_qt/qt_rooms.py').read_text(encoding='utf-8')
    assert 'room_wall_axis_snap' in graphics
    assert 'self.snap_engine.nearest_wall' in graphics
    assert 'VÆG · {axis_kind}' in graphics
    assert 'ROOM_COLOR_PALETTE' in rooms
    assert "after['color']=dlg.selected_color()" in rooms
    assert 'self._room_vertex_wall_snap' in rooms
    # Existing EL-RUM isolation remains explicit.
    snap=Path('elplan_qt/qt_graphics.py').read_text(encoding='utf-8')
    assert 'EL-RUM' in snap
