from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_is_0527():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_pl_wiring_diagram_geometry_uses_actual_available_height():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    start = source.index("class PLWiringDiagramWidget")
    end = source.index("class PLBoxDialog", start)
    block = source[start:end]
    assert "h=max(470.0,float(self.height()))" in block
    assert "h=max(620.0,float(self.height()))" not in block
    assert "bottom_y=min(h-port_h-8.0" in block
    assert "terminal_bottom=min(h-6.0,max(" in block
    assert "self.setMinimumSize(780, 470)" in block


def test_pl_dialog_keeps_footer_outside_wiring_scroll_area():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    start = source.index("class PLBoxDialog")
    block = source[start:source.index("    @staticmethod\n    def _identity", start)]
    assert "wiring_tab=QScrollArea()" in block
    assert 'self.tabs.addTab(wiring_tab,"Lederfordeling")' in block
    assert "root.addLayout(footer)" in block
