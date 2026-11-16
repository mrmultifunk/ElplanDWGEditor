from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_v0563_symbol_hover_uses_device_space_glow_for_all_placements():
    assert APP_VERSION == core.APP_VERSION == "0.59.85"
    source=(ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    block=source[source.index("class ElectricalSymbolItem"):source.index("class CablePointHandle")]
    assert "QGraphicsDropShadowEffect" in source
    assert "self.setAcceptHoverEvents(True)" in block
    assert "_ensure_glow_effect" in block
    assert "effect.setOffset(0.0,0.0)" in block
    assert "effect.setBlurRadius" in block
    assert "self._animate_to(self._hover_anim,self._hover_progress,1.0)" in block
    assert "self._animate_to(self._hover_anim,self._hover_progress,0.0)" in block
    assert "project.raw[" not in block


def test_symbol_glow_is_lazy_and_does_not_expand_hit_geometry():
    source=(ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    block=source[source.index("class ElectricalSymbolItem"):source.index("class CablePointHandle")]
    assert "self._glow_effect: QGraphicsDropShadowEffect | None = None" in block
    assert "self.setGraphicsEffect(effect)" in block
    assert "effect.setEnabled(False)" in block
    # Do not make the symbol boundingRect artificially huge just to host a halo.
    assert "adjusted(-8, -8, 8, 8)" in block
