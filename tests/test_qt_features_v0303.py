
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import core_logic as core
from qt_app import ComboConfiguratorDialog, MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_configurator_auto_name_and_custom_code():
    _app()
    dlg = ComboConfiguratorDialog(settings={})
    assert len(dlg.module_boxes) == 2
    dlg.module_boxes[0].setCurrentText("Kroneafbryder")
    dlg.module_boxes[1].setCurrentText("1-polet afbryder")
    dlg.socket_combo.setCurrentText("Stikkontakt med jordtilslutning")
    dlg._definition_changed()
    assert "Krone" in dlg.name_edit.text()
    assert "1P" in dlg.name_edit.text()
    assert "Stik+J" in dlg.name_edit.text()
    parsed = core.parse_custom_combo_symbol(dlg.code())
    assert parsed and parsed[1] == "socket_earth"
    dlg.close()


def test_rotate_association_and_cable_undo():
    _app()
    w = MainWindow()

    sw = core.Placement(symbol="switch_1", x=0, y=0, size=200)
    light = core.Placement(symbol="light_connection", x=1000, y=0, size=200)
    w._add_placement(sw)
    w._add_placement(light)
    w.symbol_items[sw.uid].setSelected(True)

    w.rotate_selected_90()
    assert round(sw.rotation) == 90
    w.undo_stack.undo()
    assert round(sw.rotation) == 0
    w.undo_stack.redo()
    assert round(sw.rotation) == 90

    w.start_association_mode()
    w._symbol_clicked(w.symbol_items[light.uid])
    assert sw.associations
    assert light.associations == sw.associations

    data = {
        "points": [(0.0, 0.0), (1000.0, 0.0)],
        "layer": core.CABLE_LAYER,
        "line_width": 0.35,
        "label": "",
        "cable_spec": "3G1,5",
        "cable_id": "K01",
        "auto_label": True,
        "start_symbol_uid": sw.uid,
        "end_symbol_uid": light.uid,
        "start_symbol_port": 0,
        "end_symbol_port": 0,
        "orthogonal": True,
    }
    before = len(w.project.cables)
    w._cable_finished(data)
    assert len(w.project.cables) == before + 1
    w.undo_stack.undo()
    assert len(w.project.cables) == before
    w.undo_stack.redo()
    assert len(w.project.cables) == before + 1
    w.close()
