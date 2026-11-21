from pathlib import Path

import core_logic as core


def test_moving_breakpoint_does_not_move_symbol_anchor():
    points=[(0.0,0.0),(5.0,0.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_vertex_flexible(points,1,(3.0,2.0),True)
    assert moved[0] == (0.0,0.0)
    assert moved[-1] == (5.0,5.0)
    assert moved[q_index] == (3.0,2.0)


def test_breakpoint_between_two_locked_anchors_is_freely_editable():
    points=[(0.0,0.0),(5.0,0.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_vertex_flexible(points,1,(2.0,3.0),True)
    assert moved[0] == points[0]
    assert moved[-1] == points[-1]
    assert moved[q_index] == (2.0,3.0)
    assert delta >= 1


def test_free_endpoint_next_to_anchor_can_create_dogleg():
    points=[(0.0,0.0),(0.0,5.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_endpoint_flexible(points,0,(2.0,2.0),True)
    assert moved[q_index] == (2.0,2.0)
    assert moved[1+delta] == points[1]


def test_connected_handle_is_explicitly_non_movable_in_qt_item():
    source=((Path(__file__).resolve().parents[1] / 'elplan_qt/qt_graphics.py')).read_text(encoding='utf-8')
    block=source[source.index('class CablePointHandle'):source.index('class CableItem')]
    assert 'self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)' in block
    assert 'Fysisk kabeltilslutning – låst til symbol' in block
    assert 'if self.connection:' in block


def test_cable_item_uses_locked_indices_during_geometry_edit():
    source=((Path(__file__).resolve().parents[1] / 'elplan_qt/qt_graphics.py')).read_text(encoding='utf-8')
    block=source[source.index('def handle_moved'):source.index('def insert_breakpoint')]
    assert 'locked_indices' in block
    assert 'move_polyline_endpoint_flexible' in block
    assert 'move_polyline_vertex_flexible' in block


def test_mainwindow_repairs_saved_anchor_drift_and_reanchors_after_edit():
    source=((Path(__file__).resolve().parents[1] / 'elplan_qt/qt_app.py')).read_text(encoding='utf-8')
    assert 'if self._repair_cable_symbol_anchors():' in source
    edit=source[source.index('def _cable_handle_edit_finished'):source.index('def _cable_insert_breakpoint')]
    assert 'self._anchor_cable_connections(item.cable)' in edit
    helper=source[source.index('def _anchor_cable_connections'):source.index('def rotate_selected_90')]
    assert 'connected_indices' in helper
    assert '(idx-1) not in connected_indices' in helper
    assert '(idx+1) not in connected_indices' in helper
