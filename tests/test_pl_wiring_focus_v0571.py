from pathlib import Path

from project_model import APP_VERSION
import core_logic as core


def test_version_and_nordtronic_has_compact_terminal_hint():
    assert APP_VERSION == core.APP_VERSION == "0.59.73"
    profile = core.pl_outlet_profile("nordtronic_zigbee", ["a"])
    assert profile["compact_hint"] == "P = tryk · COM = fælles · ~ = dæmpet udgang"
    assert "Ingen forbindelser" in profile["hint"]


def test_switch_conductor_help_is_collapsed_by_default():
    helper = Path("qt_pl_usage.py").read_text(encoding="utf-8")
    assert "Vis overblik" in helper
    assert "self.details.setVisible(self._expanded)" in helper
    assert "self.setMaximumHeight(142 if self._expanded else 42)" in helper
    assert "Tændlederhjælp" in helper


def test_pl_wiring_prioritises_graphic_and_reserves_non_overlapping_footer():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "self.wiring_diagram.setMinimumHeight(535)" in source
    assert "self.wiring_selection_label.hide()" in source
    assert "footer_h=30.0" in source
    assert "h-port_h-footer_h-8.0" in source
    assert "h-footer_h-6.0" in source


def test_terminal_header_is_single_and_uses_compact_hint():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert source.count("LAMPEUDTAG ·") == 1
    assert 'profile.get("compact_hint")' in source
    assert 'self.outlet_profile_hint.setToolTip(str(profile.get("hint") or ""))' in source
    # Neutral-start help lives above the editor rather than over bottom cable cards.
    end = source.index("class PLBoxDialog")
    diagram = source[source.index("class PLWiringDiagramWidget"):end]
    assert 'text="Ingen forbindelser laves automatisk' not in diagram
