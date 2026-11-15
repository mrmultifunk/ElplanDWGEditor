from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT=Path(__file__).resolve().parents[1]


def test_version_0572():
    assert APP_VERSION == core.APP_VERSION == "0.59.80"


def test_navigator_is_minimal_and_hidden_by_default():
    visual=(ROOT/"qt_visual_workspace.py").read_text(encoding="utf-8")
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    assert "class MiniMapView(QWidget)" in visual
    assert "CAD text is intentionally omitted" in visual
    assert "isinstance(item,CadLayerItem)" in visual
    assert "isinstance(item,CableItem)" in visual
    assert "isinstance(item,ElectricalSymbolItem)" in visual
    assert 'self.app_settings.get("show_navigator",False)' in app
    assert 'navigator_hidden_default_v0572' in visual


def test_legacy_symbol_and_pl_hover_preview_is_not_suppressed_by_selection():
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    assert "item.isSelected()" not in hover
    assert "mouseGrabberItem" in hover
    assert "QApplication.activePopupWidget()" in hover
    assert 'if str(getattr(placement,"symbol","") or "")=="light_connection"' in app
    assert "return self._pl_entry_hover_payload(placement)" in app
    assert '"preview_mode":"pl"' in app
    assert '"preview_mode":"symbol"' in app


def test_extra_cable_marking_is_hover_only_not_plan_label():
    cable=core.CablePlacement(points=[(0,0),(100,0)],cable_id="K12",cable_spec="5G1,5",label="Gang → soveværelse",auto_label=True)
    assert core.cable_display_label(cable)=="K12 · 5G1,5 · Gang → soveværelse"
    assert core.cable_plan_label(cable)=="K12 · 5G1,5"
    gfx=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "core.cable_plan_label(self.cable)" in gfx
    assert '"marking_extra":f"Ekstra mærkning · {extra}" if extra else ""' in hover
    # Hover information must exist even when the cable has no article binding.
    hover_payload=hover[hover.index("def _cable_hover_payload"):hover.index("def _clear_hover_info",hover.index("def _cable_hover_payload"))]
    assert "if not article_no:return {}" not in hover_payload
