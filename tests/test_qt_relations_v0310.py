
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import core_logic as core
from qt_app import MainWindow
from qt_graphics import AnnotationItem


def _app():
    return QApplication.instance() or QApplication([])


def test_one_switch_channel_can_control_multiple_lights():
    _app()
    w=MainWindow()
    sw=core.Placement(symbol="switch_1",x=0,y=0,size=200,associations=["a"])
    l1=core.Placement(symbol="light_connection",x=500,y=0,size=200)
    l2=core.Placement(symbol="light_connection",x=900,y=0,size=200)
    w._add_placement(sw); w._add_placement(l1); w._add_placement(l2)
    w.association_source_uid=sw.uid
    w.association_active_letter="a"
    w._symbol_clicked(w.symbol_items[l1.uid])
    w._symbol_clicked(w.symbol_items[l2.uid])
    assert l1.associations==["a"]
    assert l2.associations==["a"]
    assert sw.associations==["a"]
    assert w.association_source_uid==sw.uid
    w.project.dirty=False
    w.close()


def test_light_moves_to_new_association_instead_of_collecting_letters():
    _app()
    w=MainWindow()
    a=core.Placement(symbol="switch_1",x=0,y=0,size=200,associations=["a"])
    b=core.Placement(symbol="switch_1",x=0,y=400,size=200,associations=["b"])
    light=core.Placement(symbol="light_connection",x=700,y=200,size=200)
    for p in (a,b,light):w._add_placement(p)
    w.association_source_uid=a.uid; w.association_active_letter="a"
    w._symbol_clicked(w.symbol_items[light.uid])
    w.association_source_uid=b.uid; w.association_active_letter="b"
    w._symbol_clicked(w.symbol_items[light.uid])
    assert light.associations==["b"]
    w.project.dirty=False
    w.close()


def test_spot_parent_inherits_the_single_light_relation_and_has_visible_parent_chip():
    _app()
    w=MainWindow()
    light=core.Placement(symbol="light_connection",x=0,y=0,size=200,group="G07",associations=["a","b"])
    spot=core.Placement(symbol="spot",x=500,y=0,size=150,parent_light_uid=light.uid)
    w._add_placement(light); w._add_placement(spot)
    w._sync_spot_parent_associations()
    assert spot.associations==["a"]
    ann=w.annotation_items[spot.uid]
    ann.refresh()
    assert "G07" in ann.toHtml()
    assert "a" in ann.toHtml()
    w.project.dirty=False
    w.close()


def test_annotation_detail_returns_when_zoomed_in():
    _app()
    p=core.Placement(symbol="socket",x=0,y=0,size=200,group="G03",label="X01",associations=["a"])
    ann=AnnotationItem(p,scale_provider=lambda:0.25,mode_provider=lambda:"Auto")
    assert "G03" in ann.toHtml()
    assert "X01" in ann.toHtml()
    assert "a" in ann.toHtml()


def test_individual_spot_is_selected_for_parent_assignment():
    _app()
    w=MainWindow()
    w.spot_size_quick.setValue(135)
    w._placement_requested("spot",100,200,0)
    spot=w.project.placements[-1]
    assert spot.symbol=="spot"
    assert spot.size==135
    assert w.symbol_items[spot.uid].isSelected()
    w.start_spot_parent_for_selection()
    assert w.spot_parent_pending==[spot.uid]
    w.project.dirty=False
    w.close()


def test_crown_guide_advances_to_second_switching_and_finishes():
    app=_app()
    w=MainWindow()
    sw=core.Placement(symbol="switch_crown",x=0,y=0,size=200)
    l1=core.Placement(symbol="light_connection",x=500,y=0,size=200)
    l2=core.Placement(symbol="light_connection",x=900,y=0,size=200)
    for p in (sw,l1,l2):w._add_placement(p)
    item=w.symbol_items[sw.uid]; item.setSelected(True)
    w._activate_association_source(item)
    assert w.association_guided_setup
    assert w.association_channel_index==0
    w._symbol_clicked(w.symbol_items[l1.uid])
    assert sw.associations==["a"]
    assert l1.associations==["a"]
    assert w.association_source_uid==sw.uid
    assert w.association_active_letter==""
    assert w.association_channel_index==1
    w._symbol_clicked(w.symbol_items[l2.uid])
    app.processEvents()
    assert sw.associations==["a","b"]
    assert l2.associations==["b"]
    assert w.association_source_uid==""
    assert w.symbol_items[sw.uid].isSelected()
    assert w.apply_button.isEnabled()
    w.project.dirty=False
    w.close()


def test_correspondence_reuses_existing_relation_without_removing_it_from_light():
    _app()
    w=MainWindow()
    existing=core.Placement(symbol="switch_2way",x=0,y=0,size=200,associations=["a"])
    new_switch=core.Placement(symbol="switch_2way",x=0,y=400,size=200)
    light=core.Placement(symbol="light_connection",x=700,y=200,size=200,associations=["a"])
    for p in (existing,new_switch,light):w._add_placement(p)
    item=w.symbol_items[new_switch.uid]; item.setSelected(True)
    w._activate_association_source(item)
    w._symbol_clicked(w.symbol_items[light.uid])
    assert new_switch.associations==["a"]
    assert light.associations==["a"]
    w.project.dirty=False
    w.close()


def test_double_correspondence_guide_reuses_two_existing_relations_and_advances():
    app=_app()
    w=MainWindow()
    sw=core.Placement(symbol="switch_double_2way",x=0,y=0,size=200)
    l1=core.Placement(symbol="light_connection",x=500,y=0,size=200,associations=["a"])
    l2=core.Placement(symbol="light_connection",x=900,y=0,size=200,associations=["b"])
    for p in (sw,l1,l2):w._add_placement(p)
    item=w.symbol_items[sw.uid]; item.setSelected(True)
    w._activate_association_source(item)
    w._symbol_clicked(w.symbol_items[l1.uid])
    assert sw.associations==["a"]
    assert l1.associations==["a"]
    assert w.association_channel_index==1
    w._symbol_clicked(w.symbol_items[l2.uid])
    app.processEvents()
    assert sw.associations==["a","b"]
    assert l1.associations==["a"]
    assert l2.associations==["b"]
    assert w.association_source_uid==""
    w.project.dirty=False
    w.close()


def test_four_pushbuttons_guide_advances_through_all_four_channels():
    app=_app()
    w=MainWindow()
    sw=core.Placement(symbol="pushbutton_4",x=0,y=0,size=200)
    lights=[core.Placement(symbol="light_connection",x=500+i*300,y=0,size=200) for i in range(4)]
    w._add_placement(sw)
    for light in lights:w._add_placement(light)
    item=w.symbol_items[sw.uid]; item.setSelected(True)
    w._activate_association_source(item)
    for i,light in enumerate(lights):
        w._symbol_clicked(w.symbol_items[light.uid])
        if i<3:
            assert w.association_channel_index==i+1
            assert w.association_source_uid==sw.uid
    app.processEvents()
    assert sw.associations==["a","b","c","d"]
    assert [x.associations for x in lights]==[["a"],["b"],["c"],["d"]]
    assert w.association_source_uid==""
    w.project.dirty=False
    w.close()
