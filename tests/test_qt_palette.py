import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

def test_light_palette_and_view_background():
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication, QProxyStyle
    from elplan_qt.qt_app import MainWindow
    from elplan_qt.qt_theme import ElplanProxyStyle, _application_stylesheet, _apply_application_palette
    app=QApplication.instance() or QApplication([])
    _apply_application_palette(app,"light")
    # Nyere PySide-versioner returnerer den indpakkede native stil som
    # QCommonStyle; verificér derfor proxytypen og det synlige resultat.
    assert issubclass(ElplanProxyStyle,QProxyStyle)
    assert app.style() is not None
    assert app.palette().color(QPalette.ColorRole.WindowText).lightness() < 128
    w=MainWindow()
    assert w.scene.backgroundBrush().color().name().lower() == "#ffffff"
    assert w.view.backgroundBrush().color().name().lower() == "#ffffff"
    css=_application_stylesheet(False,False)
    assert "QToolBar#mainToolbar QToolButton" in css and "color: #27313c" in css
    w.project.dirty=False
    w.close()
