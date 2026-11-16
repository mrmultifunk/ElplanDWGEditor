import math

import pytest
pytest.importorskip("PySide6")

import core_logic as core
from qt_graphics import QtSnapEngine
from qt_rooms import RoomBoundaryItem
from PySide6.QtWidgets import QApplication, QGraphicsScene


def _app():
    return QApplication.instance() or QApplication([])


def test_el_room_layer_is_defensively_excluded_from_wall_snap_index():
    """Even accidental EL-RUM CAD primitives must never become magnetic walls."""
    prims = [
        core.CADPrimitive("line", "Walls", (0.0, 0.0, 1000.0, 0.0)),
        core.CADPrimitive("line", core.ROOM_LAYER, (0.0, 100.0, 1000.0, 100.0)),
    ]
    engine = QtSnapEngine(prims, lambda _layer: True)
    layers = {segment[4] for segment in engine.segments}
    assert "Walls" in layers
    assert core.ROOM_LAYER not in layers


def test_symbol_wall_snap_ignores_visible_room_boundary_but_keeps_cad_wall_snap():
    """A visible/editable room polygon must not affect normal symbol placement snap."""
    _app()
    scene = QGraphicsScene()

    room = core.RoomPlacement(
        name="Køkken",
        code="R01",
        points=[(0.0, 100.0), (1000.0, 100.0), (1000.0, 600.0), (0.0, 600.0)],
        label_x=500.0,
        label_y=350.0,
    )
    boundary = RoomBoundaryItem(room, None, None)
    boundary.set_edit_mode(True)
    scene.addItem(boundary)
    assert boundary.isVisible()

    engine = QtSnapEngine(
        [core.CADPrimitive("line", "Walls", (0.0, 0.0, 1000.0, 0.0))],
        lambda _layer: True,
    )

    # socket has its physical wall mount point 200 CAD units above its origin.
    # Place that mount point directly on the visible EL-RUM edge at y=100.
    raw = (500.0, -100.0)
    (xy, _rot, kind) = engine.snap_pose(
        scene,
        "socket",
        200.0,
        0.0,
        raw,
        1.0,
        ignore_uid="room-isolation-preview",
        cursor_cad=(500.0, 100.0),
    )
    assert kind == ""
    assert math.isclose(xy[0], raw[0], abs_tol=1e-9)
    assert math.isclose(xy[1], raw[1], abs_tol=1e-9)

    # Move the same symbol close to the actual CAD wall: normal wall snap must remain intact.
    (xy, _rot, kind) = engine.snap_pose(
        scene,
        "socket",
        200.0,
        0.0,
        (500.0, -195.0),
        1.0,
        ignore_uid="real-wall-preview",
        cursor_cad=(500.0, 5.0),
    )
    assert "VÆG" in kind
    assert math.isclose(xy[0], 500.0, abs_tol=1e-9)
    _mx,my=core.rotate_point(*core.symbol_mount_points("socket",200.0)[0],_rot)
    assert math.isclose(xy[1]+my, 0.0, abs_tol=1e-9)
