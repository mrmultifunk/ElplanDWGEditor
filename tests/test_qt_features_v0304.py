
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import core_logic as core
from qt_app import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_pattern_point_helpers():
    from qt_graphics import CadGraphicsView
    pts=CadGraphicsView._row_points((0,0),(300,0),4)
    assert pts==[(0.0,0.0),(100.0,0.0),(200.0,0.0),(300.0,0.0)]
    rect=CadGraphicsView._rect_points((0,0),(200,100),3,2)
    assert len(rect)==6
    assert (0.0,0.0) in rect and (200.0,100.0) in rect


def test_text_copy_and_spot_parent():
    _app()
    w=MainWindow()
    light=core.Placement(symbol="light_connection",x=500,y=500,size=200,associations=["a"])
    w._add_placement(light)
    config={"count":3,"size":150.0,"link":True}
    w._spot_pattern_finished("line",(0.0,0.0),(300.0,0.0),config)
    assert len([p for p in w.project.placements if p.symbol=="spot"])==3
    assert len(w.spot_parent_pending)==3
    w._symbol_clicked(w.symbol_items[light.uid])
    spots=[p for p in w.project.placements if p.symbol=="spot"]
    assert all(p.parent_light_uid==light.uid for p in spots)
    assert all(p.associations==["a"] for p in spots)

    txt=core.TextPlacement(text="Køkken",x=10,y=20,height=200)
    w._add_text(txt)
    w.text_items[txt.uid].setSelected(True)
    w.copy_selected()
    w.paste_clipboard()
    assert len(w.project.texts)==2
    w.close()


def test_print_extents_current_view():
    _app()
    w=MainWindow()
    ext=w._print_extents("Aktuel visning")
    assert len(ext)==4 and ext[2]>ext[0] and ext[3]>ext[1]
    w.close()
