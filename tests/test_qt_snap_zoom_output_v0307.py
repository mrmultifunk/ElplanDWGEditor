
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

import core_logic as core
from elplan_qt.qt_app import MainWindow
from elplan_qt.qt_graphics import CadGraphicsView, QtSnapEngine


def _app():
    return QApplication.instance() or QApplication([])


def test_wall_snap_hysteresis_and_cursor_side_rotation():
    _app()
    prims=[
        core.CADPrimitive("line","Walls",(0.0,0.0,1000.0,0.0)),
        core.CADPrimitive("line","Walls",(500.0,-500.0,500.0,500.0)),
    ]
    engine=QtSnapEngine(prims,lambda layer: True)
    scene=__import__("PySide6.QtWidgets",fromlist=["QGraphicsScene"]).QGraphicsScene()
    uid="preview-test"
    # Cursor below horizontal wall should orient normal socket with its body below.
    (_xy,rot,_kind)=engine.snap_pose(scene,"socket",200.0,0.0,(250.0,-180.0),1.0,
                                     ignore_uid=uid,cursor_cad=(250.0,-20.0))
    assert round(rot)%180==0
    first_lock=engine.wall_locks.get(uid)
    assert first_lock is not None
    # Close to the crossing, a tiny move should keep the same locked segment.
    engine.snap_pose(scene,"socket",200.0,rot,(490.0,-180.0),1.0,
                     ignore_uid=uid,cursor_cad=(490.0,-5.0))
    assert engine.wall_locks.get(uid)==first_lock


def test_output_dimming_setting_is_independent_from_scene_symbols():
    _app()
    w=MainWindow()
    w.cad_background_opacity=.40
    w.print_cad_dimming=False
    assert w._output_cad_opacity()==1.0
    w.print_cad_dimming=True
    assert abs(w._output_cad_opacity()-.40)<1e-9
    w.project.dirty=False
    w.close()
