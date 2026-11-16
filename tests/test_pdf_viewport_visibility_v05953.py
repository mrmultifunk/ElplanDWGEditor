import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

import core_logic as core
from project_model import APP_VERSION
from qt_app import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_version_v05957():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"


def test_pdf_output_visibility_respects_quick_cable_filter():
    _app()
    w=MainWindow()
    cable=core.CablePlacement(points=[(0.0,0.0),(100.0,0.0)])
    w.project.cables=[cable]
    effective=core.cable_effective_layer(cable)
    w.project.layer_visibility[effective]=True
    w.quick_visibility["cables"]=False
    visibility=w._output_layer_visibility()
    assert visibility[effective] is False
    w.project.dirty=False
    w.close()


def test_pdf_output_visibility_keeps_layer_hidden_when_quick_filter_is_on():
    _app()
    w=MainWindow()
    cable=core.CablePlacement(points=[(0.0,0.0),(100.0,0.0)])
    w.project.cables=[cable]
    effective=core.cable_effective_layer(cable)
    w.project.layer_visibility[effective]=False
    w.quick_visibility["cables"]=True
    visibility=w._output_layer_visibility()
    assert visibility[effective] is False
    w.project.dirty=False
    w.close()


def test_current_view_layout_fits_inside_instead_of_cropping_sides():
    # A deliberately wider viewport than A3 landscape. WYSIWYG output must keep
    # xmin/xmax untouched; whitespace on the page is preferable to clipping.
    ext=(0.0,0.0,1600.0,900.0)
    _page,effective,*_rest=core.page_layout(ext,"A3","Landskab",fill_page=False)
    assert effective == ext
    cropped=core.page_layout(ext,"A3","Landskab",fill_page=True)[1]
    assert cropped[0] > ext[0] and cropped[2] < ext[2]


def test_pdf_call_sites_use_effective_visibility_and_do_not_crop_current_view():
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/"qt_app.py").read_text(encoding="utf-8")
    assert "self.window._output_layer_visibility()" in src
    assert "self._output_layer_visibility(),paper,orientation" in src
    assert "fill_page=(scope==\"Aktuel visning\")" not in src
