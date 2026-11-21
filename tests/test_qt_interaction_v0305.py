
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsScene

import core_logic as core
from elplan_qt.qt_app import MainWindow
from elplan_qt.qt_graphics import AnnotationItem, ElectricalSymbolItem


def _app():
    return QApplication.instance() or QApplication([])


def test_plain_click_phase_cannot_move_symbol():
    _app()
    p=core.Placement(symbol="socket",x=100.0,y=200.0,size=200.0)
    item=ElectricalSymbolItem(p)
    scene=QGraphicsScene(); scene.addItem(item)
    item._drag_start_pose=(p.x,p.y,p.rotation)
    item._dragging=False
    old=item.pos()
    item.setPos(old+QPointF(4.0,0.0))
    assert item.pos()==old
    assert p.x==100.0 and p.y==200.0


def test_annotation_is_compact_and_outside_symbol():
    _app()
    p=core.Placement(symbol="switch_1",x=100.0,y=100.0,size=200.0,label="S01",group="G01",associations=["a"])
    symbol=ElectricalSymbolItem(p)
    scene=QGraphicsScene(); scene.addItem(symbol)
    ann=AnnotationItem(p,symbol_item=symbol,scale_provider=lambda:0.1)
    scene.addItem(ann); ann.reposition()
    assert "background-color:white" not in ann.toHtml().replace(" ","").lower()
    assert ann.pos().x() > symbol.sceneBoundingRect().right()


def test_association_mode_highlights_valid_targets_and_clears_when_done():
    _app()
    w=MainWindow()
    switch=core.Placement(symbol="switch_1",x=0,y=0,size=200)
    light=core.Placement(symbol="light_connection",x=800,y=0,size=200)
    w._add_placement(switch); w._add_placement(light)
    w.symbol_items[switch.uid].setSelected(True)
    w.start_association_mode()
    assert w.association_source_uid==switch.uid
    assert len(w.association_target_overlays)>=1
    assert w.association_guide is not None
    w._symbol_clicked(w.symbol_items[light.uid])
    assert switch.associations
    assert light.associations==switch.associations
    # En session kan nu tilknytte flere lys og afsluttes eksplicit.
    assert w.association_source_uid==switch.uid
    assert w.association_target_overlays
    w._finish_active_association()
    assert w.association_source_uid==""
    assert not w.association_target_overlays
    w.project.dirty=False
    w.close()
