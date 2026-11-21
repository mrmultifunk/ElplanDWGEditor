
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import core_logic as core
from elplan_qt.qt_app import MainWindow
from elplan_qt.qt_graphics import CadLayerItem, ElectricalSymbolItem


def _app():
    return QApplication.instance() or QApplication([])


def test_cad_background_opacity_only_affects_cad_items():
    _app()
    w=MainWindow()
    cad=CadLayerItem("Walls",[core.CADPrimitive("line","Walls",(0.0,0.0,1000.0,0.0))])
    w.scene.addItem(cad); w.layer_items["Walls"]=cad
    p=core.Placement(symbol="socket",x=100,y=100,size=200)
    w._add_placement(p)
    w._cad_opacity_changed(40)
    assert abs(cad.opacity()-0.40)<1e-9
    assert abs(w.symbol_items[p.uid].opacity()-1.0)<1e-9
    w.project.dirty=False
    w.close()


def test_cable_workspace_live_settings():
    _app()
    w=MainWindow()
    # Minimal non-null doc marker is enough for cable workspace activation.
    w.doc=object()
    w._show_inspector_page("cable")
    w.cable_id_edit.setText("K01")
    w.cable_spec_combo.setCurrentText("5G1,5")
    w.cable_snap_symbols.setChecked(True)
    w.cable_snap_walls.setChecked(False)
    w._start_cable_from_panel()
    assert w.view._cable_active
    assert w.view._cable_meta["cable_id"]=="K01"
    assert w.view._cable_meta["cable_spec"]=="5G1,5"
    assert w.view._cable_snap_symbols is True
    assert w.view._cable_snap_walls is False
    w.view.remove_last_cable_point()
    w.project.dirty=False
    w.close()
