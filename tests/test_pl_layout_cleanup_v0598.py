from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_0598():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"


def test_port_cards_reserve_a_separate_conductor_band():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _port_card_layout" in source
    assert "conductor_band=19.0" in source
    assert "if int(port)<=3" in source
    assert "content_top=rect.top()+conductor_band+2.0" in source
    assert 'card_layout=self._port_card_layout(rect,port)' in source
    assert 'self._draw_port_cable_label(p,rect,display,text_main,card_layout["label"])' in source


def test_secondary_port_info_is_allowed_to_elide_before_marking():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "meta_text=fm.elidedText" in source
    assert 'meta_text=" · ".join(x for x in [category_name,spec,side] if x)' in source
    assert "display[:38]" not in source


def test_montage_control_is_compact_and_collapsed_by_default():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert 'QPushButton("Vis kontrol")' in source
    assert "self.montage_status_label.hide()" in source
    assert "def _toggle_montage_details" in source
    assert 'summary="✓ Montagekontrol · klar til montage"' in source
