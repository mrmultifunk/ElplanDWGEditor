import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from qt_app import MainWindow
from qt_graphics import QtSnapEngine
import core_logic as core


def test_palette_add_undo_redo_and_wall_snap():
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    assert w.palette_dock is not None
    assert w.palette_list.count() > 0

    # Simple horizontal wall y=0 and a socket whose mount point is size units above origin.
    wall = core.CADPrimitive("line", "Walls", (0.0, 0.0, 1000.0, 0.0))
    w.cad_primitives = [wall]
    w.snap_engine = QtSnapEngine(w.cad_primitives, lambda layer: True)
    w.view.set_snap_engine(w.snap_engine)
    (x, y), rot, kind = w.snap_engine.snap_pose(w.scene, "socket", 200.0, 0.0, (500.0, -190.0), 1.0,
                                                cursor_cad=(500.0, 10.0))
    assert "VÆG" in kind
    assert abs((y + 200.0) - 0.0) < 1e-6

    w.palette_size.setValue(200)
    w._placement_requested("socket", 100.0, 100.0, 0.0)
    assert len(w.project.placements) == 1
    w.undo_stack.undo()
    assert len(w.project.placements) == 0
    w.undo_stack.redo()
    assert len(w.project.placements) == 1
    w.project.dirty = False
    w.close()
