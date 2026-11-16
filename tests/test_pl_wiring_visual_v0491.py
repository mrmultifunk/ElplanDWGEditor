from pathlib import Path


def test_version_0491():
    import core_logic as core
    from project_model import APP_VERSION
    assert core.APP_VERSION == APP_VERSION == "0.59.85"


def test_qt_source_makes_pl_wiring_canvas_primary_and_draggable():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "class PLWiringDiagramWidget" in source
    assert "self.setMinimumSize(780, 470)" in source
    assert "def mouseMoveEvent(self,event):" in source
    assert "def mouseReleaseEvent(self,event):" in source
    assert "self._drag_key" in source
    assert "Vis tabel / avanceret" in source
    assert "self.wiring_details_panel.hide()" in source
    assert "PL-dåsen og klemrækken er to separate grafiske objekter" in source
    assert "Fordel terminalindgange mellem direkte ledere og alle Wago-broer" in source
    assert "self._draw_curve(p,start,anchor_by_key[key]" in source
    assert "TÆNDING" in source


def test_visual_change_adds_only_outlet_type_beside_existing_wiring_fields():
    source=Path("project_model.py").read_text(encoding="utf-8")
    assert '"pl_box_entries": {}' in source
    assert '"pl_box_wiring": []' in source
    assert '"lamp_outlet_type": "generic"' in source
    assert "pl_wiring_visual" not in source
