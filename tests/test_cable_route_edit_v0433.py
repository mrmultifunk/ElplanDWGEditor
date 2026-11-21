from pathlib import Path

import core_logic as core


def _all_orthogonal(points):
    return all(abs(a[0]-b[0]) < 1e-9 or abs(a[1]-b[1]) < 1e-9 for a,b in zip(points, points[1:]))


def test_free_breakpoint_between_two_symbol_anchors_can_move():
    points=[(0.0,0.0),(5.0,0.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_vertex_flexible(points,1,(2.0,3.0),True)
    assert moved[0] == points[0]
    assert moved[-1] == points[-1]
    assert moved[q_index] == (2.0,3.0)
    assert delta == 2
    assert _all_orthogonal(moved)


def test_connection_index_after_dragged_breakpoint_can_be_remapped_by_delta():
    points=[(0.0,0.0),(5.0,0.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_vertex_flexible(points,1,(2.0,3.0),True)
    old_connection_index=2
    new_connection_index=old_connection_index + delta
    assert moved[new_connection_index] == (5.0,5.0)
    assert q_index == 2


def test_dragging_aligned_breakpoint_does_not_add_unneeded_doglegs():
    points=[(0.0,0.0),(5.0,0.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_vertex_flexible(points,1,(3.0,0.0),True)
    assert moved == [(0.0,0.0),(3.0,0.0),(5.0,0.0),(5.0,5.0)]
    assert moved[q_index] == (3.0,0.0)
    assert delta == 1
    assert _all_orthogonal(moved)


def test_free_endpoint_can_move_off_axis_while_neighbor_stays_fixed():
    points=[(0.0,0.0),(0.0,5.0),(5.0,5.0)]
    moved,q_index,delta=core.move_polyline_endpoint_flexible(points,0,(2.0,2.0),True)
    assert moved[q_index] == (2.0,2.0)
    assert moved[1+delta] == points[1]
    assert _all_orthogonal(moved)


def test_qt_editor_uses_flexible_dogleg_helpers_and_keeps_green_anchors_locked():
    source=(Path(__file__).resolve().parents[1] / 'elplan_qt/qt_graphics.py').read_text(encoding='utf-8')
    block=source[source.index('def handle_moved'):source.index('def insert_breakpoint')]
    assert 'move_polyline_vertex_flexible' in block
    assert 'move_polyline_endpoint_flexible' in block
    assert 'if old_i>index:' in block
    handle_block=source[source.index('class CablePointHandle'):source.index('class CableItem')]
    assert 'ItemIsMovable, False' in handle_block
