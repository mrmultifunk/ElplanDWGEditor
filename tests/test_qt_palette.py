import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

def test_light_palette_and_view_background():
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication
    from qt_app import MainWindow, ElplanProxyStyle, _apply_light_application_palette
    app=QApplication.instance() or QApplication([])
    _apply_light_application_palette(app)
    assert isinstance(app.style(), ElplanProxyStyle)
    assert app.palette().color(QPalette.ColorRole.WindowText).lightness() < 128
    w=MainWindow()
    assert w.scene.backgroundBrush().color().name().lower() == "#ffffff"
    assert w.view.backgroundBrush().color().name().lower() == "#ffffff"
    css=w.styleSheet()
    assert "QToolBar#mainToolbar QToolButton" in css and "color: #27313c" in css
    w.close()
