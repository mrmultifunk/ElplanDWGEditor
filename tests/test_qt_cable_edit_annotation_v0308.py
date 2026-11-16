
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsScene

import core_logic as core
from qt_app import MainWindow
from qt_graphics import AnnotationItem, CableItem


def _app():
    return QApplication.instance() or QApplication([])


def test_existing_cable_can_be_selected_and_edited_with_undo():
    _app()
    w=MainWindow()
    cable=core.CablePlacement(points=[(0,0),(300,0),(300,300)],cable_id="K01",cable_spec="3G1,5",
                              auto_label=True,orthogonal=True)
    w._add_cable(cable)
    item=w.cable_items[id(cable)]
    item.setSelected(True)
    # 0.59.85 udskyder Egenskaber til efter muse-slip; tøm den samlede
    # valghændelse eksplicit i denne programmatisk drevne test.
    w._flush_queued_selection_changed()
    item._selection_refresh()
    assert item.handles
    before=CableItem.state(cable)
    item.begin_handle_edit()
    cable.points=core.move_polyline_vertex(cable.points,1,(200,100),True)
    item.refresh(update_handles=False)
    item.finish_handle_edit()
    assert CableItem.state(cable)!=before
    w.undo_stack.undo()
    assert CableItem.state(cable)==before
    w.project.dirty=False
    w.close()


def test_doubleclick_style_breakpoint_insert_and_remove():
    _app()
    cable=core.CablePlacement(points=[(0,0),(500,0)],orthogonal=True)
    item=CableItem(cable,scale_provider=lambda:0.1)
    scene=QGraphicsScene(); scene.addItem(item); item.setSelected(True)
    before=len(cable.points)
    assert item.insert_breakpoint(QPointF(250,0))
    assert len(cable.points)==before+1
    assert item.remove_breakpoint(1)
    assert len(cable.points)>=2


def test_annotation_modes_keep_association_visible():
    _app()
    p=core.Placement(symbol="light_connection",x=0,y=0,size=200,label="S01",group="G12",associations=["a"])
    ann=AnnotationItem(p,scale_provider=lambda:0.06,mode_provider=lambda:"Auto")
    html=ann.toHtml()
    assert "G12" in html
    assert "a" in html
    assert "S01" not in html
    ann.mode_provider=lambda:"Tydelig"
    ann.refresh()
    assert "S01" in ann.toHtml()
