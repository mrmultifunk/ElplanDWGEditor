from pathlib import Path


def test_spinboxes_have_visible_button_zones_and_custom_arrows():
    source = Path("elplan_qt/qt_app.py").read_text(encoding="utf-8") + Path("elplan_qt/qt_theme.py").read_text(encoding="utf-8") + Path("elplan_qt/qt_widgets.py").read_text(encoding="utf-8")
    assert "class ElplanProxyStyle(QProxyStyle)" in source
    assert "PE_IndicatorArrowUp" in source
    assert "PE_IndicatorArrowDown" in source
    assert "_install_application_style(app)" in source
    assert 'QDoubleSpinBox[elplanChevron="true"]::up-button, QSpinBox[elplanChevron="true"]::up-button' in source
    assert 'QDoubleSpinBox[elplanChevron="true"]::down-button, QSpinBox[elplanChevron="true"]::down-button' in source
    assert "padding-right: 28px" in source
    assert "class _AlwaysVisibleSpinArrowMixin" in source
    assert "def _paint_visible_spin_arrows" in source
    assert "def paintEvent(self, event)" in source
    assert "super().paintEvent(event)" in source
    assert "self._paint_visible_spin_arrows()" in source


def test_common_controls_have_consistent_visual_feedback():
    source = Path("elplan_qt/qt_app.py").read_text(encoding="utf-8") + Path("elplan_qt/qt_theme.py").read_text(encoding="utf-8") + Path("elplan_qt/qt_widgets.py").read_text(encoding="utf-8")
    assert "QComboBox::drop-down" in source
    assert "QPushButton:focus" in source
    assert "QTableView, QTableWidget" in source
    assert "QHeaderView::section" in source
    assert "QScrollBar:horizontal" in source
    assert "QScrollBar::handle:horizontal:hover" in source
