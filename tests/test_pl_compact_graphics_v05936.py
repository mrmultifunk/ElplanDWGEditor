from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_05936():
    assert APP_VERSION == core.APP_VERSION == "0.59.84"


def test_pl_graphics_has_compact_and_detailed_modes():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    start = source.index("class PLWiringDiagramWidget")
    end = source.index("class PLBoxDialog", start)
    block = source[start:end]
    assert "self._detail_mode=False" in block
    assert "def set_detail_mode" in block
    assert "def detail_mode" in block
    assert "box_h=38.0" in block
    assert "terminal_h=max(252.0,min(318.0,body.height()*0.72))" in block
    assert "def _compact_hover_tooltip" in block
    assert "QToolTip.showText" in block


def test_pl_dialog_defaults_to_compact_and_offers_detail_toggle():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    start = source.index("class PLBoxDialog")
    block = source[start:]
    assert 'QPushButton("Kompakt")' in block
    assert "self.graphics_detail_btn.setCheckable(True)" in block
    assert "self.wiring_diagram.set_detail_mode(False)" in block
    assert 'self.graphics_detail_btn.setText("Detaljeret" if detailed else "Kompakt")' in block


def test_compact_mode_hides_secondary_wago_and_terminal_text():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'compact_meta=f"{member_count}+bro"' in source
    assert 'if detailed and fid.startswith("switch:")' in source
    assert "if detailed and uses_wago" in source
    assert "elif detailed and has_loop_wago" in source
