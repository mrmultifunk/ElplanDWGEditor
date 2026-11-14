from pathlib import Path
import core_logic as core
from project_model import APP_VERSION
from interaction_math import room_nearest_edge_insert

def test_v05957_room_can_insert_vertex_on_nearest_edge():
    assert APP_VERSION == core.APP_VERSION == '0.59.76'
    points=[(0,0),(10,0),(10,10),(0,10)]
    index,point=room_nearest_edge_insert(points,4,-11)
    assert index==3 and point==(4.0,10.0)

def test_v05957_closing_edge_is_insertable():
    points=[(0,0),(10,0),(10,10),(0,10)]
    index,point=room_nearest_edge_insert(points,-1,-5)
    assert index==4 and point==(0.0,5.0)

def test_v05957_ui_exposes_add_breakpoint_and_undo_path():
    source=Path(__file__).resolve().parents[1].joinpath('qt_rooms.py').read_text(encoding='utf-8')
    assert 'Tilføj knækpunkt her' in source
    assert 'dobbeltklik på en side for nyt knækpunkt' in source
    assert 'self.vertex_callback(self.room,before,deepcopy(after))' in source
    assert 'EditRoomCommand(self,room.uid,{"points":before},{"points":after}' in source
