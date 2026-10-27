import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from qt_app import MainWindow


def test_main_window_constructs():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.view is not None
    assert window.palette_dock is not None
    assert window.palette_list.count() > 0
    assert window.layers_dock is not None
    assert window.properties_dock is not None
    window.close()
