
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import core_logic as core
from qt_app import MainWindow
from qt_graphics import AnnotationItem, QtSnapEngine


def _app():
    return QApplication.instance() or QApplication([])


def test_auto_overview_profile_is_smaller_than_detail():
    _app()
    p=core.Placement(symbol="socket",x=0,y=0,size=200,group="G01",associations=["a"])
    overview=AnnotationItem(p,scale_provider=lambda:0.07,mode_provider=lambda:"Auto")
    detailed=AnnotationItem(p,scale_provider=lambda:0.25,mode_provider=lambda:"Auto")
    assert overview._visual_profile()["primary"] < detailed._visual_profile()["primary"]
    assert overview._visual_profile()["assoc"] < detailed._visual_profile()["assoc"]


def test_far_overview_hides_persistent_annotation():
    _app()
    p=core.Placement(symbol="socket",x=0,y=0,size=200,group="G01",label="S01",associations=["a"])
    ann=AnnotationItem(p,scale_provider=lambda:0.04,mode_provider=lambda:"Auto")
    assert ann.toHtml().strip() == ""


def test_overview_keeps_only_primary_group():
    _app()
    p=core.Placement(symbol="socket",x=0,y=0,size=200,group="G01",label="S01",associations=["a"])
    ann=AnnotationItem(p,scale_provider=lambda:0.08,mode_provider=lambda:"Auto")
    text=ann.toHtml()
    assert "G01" in text
    assert "S01" not in text
    # Tilhørsbogstavet er nu bevidst synligt allerede i oversigtsniveauet.
    assert "a" in text


def test_hidden_mode_hides_every_annotation_detail():
    _app()
    p=core.Placement(symbol="spot",x=0,y=0,size=150,group="G08",label="SP1",associations=["a","b"],parent_light_uid="x")
    ann=AnnotationItem(p,scale_provider=lambda:0.5,mode_provider=lambda:"Skjult",spot_parent_provider=lambda _p:"↳ L1")
    assert ann.toHtml().strip() == ""


def test_room_direction_follows_symbol_side_of_vertical_wall():
    _app()
    w=MainWindow()
    wall=core.CADPrimitive("line","Walls",(0.0,-1000.0,0.0,1000.0))
    w.snap_engine=QtSnapEngine([wall],lambda _layer:True)
    left=core.Placement(symbol="switch_1",x=-80,y=0,size=200)
    right=core.Placement(symbol="switch_1",x=80,y=0,size=200)
    ldx,_=w._annotation_room_direction(left)
    rdx,_=w._annotation_room_direction(right)
    assert ldx < 0
    assert rdx > 0
    w.project.dirty=False
    w.close()
