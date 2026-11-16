from pathlib import Path

import core_logic as core
from project_model import APP_VERSION, ProjectDocument

ROOT = Path(__file__).resolve().parents[1]


def _class_block(source: str, class_name: str, next_class: str) -> str:
    start = source.index(f"class {class_name}(")
    end = source.index(f"class {next_class}(", start)
    return source[start:end]


def test_version_v0525():
    assert APP_VERSION == core.APP_VERSION == "0.59.84"


def test_cable_context_signal_is_declared_on_cable_signals_only():
    source = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    item_block = _class_block(source, "ItemSignals", "ElectricalSymbolItem")
    cable_block = _class_block(source, "CableSignals", "CablePointHandle")

    assert "contextRequested = Signal(object, object)" in item_block
    assert "contextRequested = Signal(object, object, object)" not in item_block
    assert "contextRequested = Signal(object, object, object)" in cable_block


def test_cable_context_event_and_main_window_use_same_signal():
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert "self.signals.contextRequested.emit(self,event.scenePos(),event.screenPos())" in graphics
    assert "item.signals.contextRequested.connect(self._cable_context_menu)" in app


def test_user_style_v0522_project_model_still_loads(tmp_path):
    # Minimal shape matching projects saved before route_section_modes existed.
    p = tmp_path / "older.elplan.json"
    p.write_text(
        '{"version":"0.52.2","source_file":"","placements":[],"cables":['
        '{"points":[[0,0],[100,0]],"layer":"EL-KABLER","line_width":0.35,'
        '"color":"#2563eb","line_style":"solid","cable_category":"light_points",'
        '"label":"","cable_spec":"3G1,5","cable_id":"G01","auto_label":true,'
        '"start_symbol_uid":"","end_symbol_uid":"","start_symbol_port":0,'
        '"end_symbol_port":0,"orthogonal":true,"symbol_connections":[],"uid":"c1"}'
        '],"texts":[],"layer_visibility":{}}',
        encoding="utf-8",
    )
    doc = ProjectDocument.load(p)
    assert len(doc.cables) == 1
    assert doc.cables[0].uid == "c1"
