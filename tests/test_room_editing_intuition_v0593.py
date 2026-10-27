from pathlib import Path

from interaction_math import room_axis_assist


def test_room_axis_assist_is_soft_and_alt_can_disable_it():
    x,y,gx,gy,label=room_axis_assist(100.0,3.0,[(0.0,0.0)],5.0)
    assert (x,y)==(100.0,0.0)
    assert gx is None and gy==0.0
    assert label=='VANDRET'

    x,y,gx,gy,label=room_axis_assist(100.0,40.0,[(0.0,0.0)],5.0)
    assert (x,y)==(100.0,40.0)
    assert gx is None and gy is None and label==''

    x,y,gx,gy,label=room_axis_assist(100.0,3.0,[(0.0,0.0)],5.0,disabled=True)
    assert (x,y)==(100.0,3.0)
    assert gx is None and gy is None and label==''


def test_vertex_assist_can_align_to_both_neighbour_axes():
    x,y,gx,gy,label=room_axis_assist(98.0,52.0,[(100.0,0.0),(0.0,50.0)],5.0)
    assert (x,y)==(100.0,50.0)
    assert gx==100.0 and gy==50.0
    assert 'VANDRET' in label and 'LODRET' in label


def test_room_double_click_and_axis_help_are_explicit_in_ui_source():
    rooms=Path('qt_rooms.py').read_text(encoding='utf-8')
    graphics=Path('qt_graphics.py').read_text(encoding='utf-8')
    assert "Dobbeltklik på rumkonturen for at redigere afgrænsningen" in rooms
    assert "if not boundary_visible and callable(self.boundary_edit_callback):" in rooms
    assert "self.boundary_edit_callback(self.room)" in rooms
    assert "def _assisted_vertex_position" in rooms
    assert "Qt.KeyboardModifier.AltModifier" in rooms
    assert "room_axis_assist" in rooms
    assert "room_axis_assist" in graphics
    assert "VANDRET" in Path('interaction_math.py').read_text(encoding='utf-8')
    assert "Alt = fri/skrå" in rooms


def test_visible_room_outline_hit_testing_is_outline_only():
    rooms=Path('qt_rooms.py').read_text(encoding='utf-8')
    assert "def shape(self):" in rooms
    assert "QPainterPathStroker" in rooms
    assert "return stroker.createStroke(self.path())" in rooms
