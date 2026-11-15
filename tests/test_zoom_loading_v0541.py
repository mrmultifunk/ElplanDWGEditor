from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_version_0541():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_zoom_is_applied_after_canvas_is_visible():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    load = app[app.index("    def _load_cad_and_scene"):app.index("    def _rebuild_scene", app.index("    def _load_cad_and_scene"))]
    rebuild = app[app.index("    def _rebuild_scene"):app.index("    def _wire_symbol_item", app.index("    def _rebuild_scene"))]
    assert load.index("self._show_canvas_page()") < load.index("self.view.fit_scene()")
    assert "self.view.fit_scene()" not in rebuild
    assert "def zoom_by_factor" in graphics
    assert "def zoom_in" in graphics and "def zoom_out" in graphics
    assert "self.zoom_by_factor(factor, anchor_view)" in graphics


def test_zoom_shortcuts_provide_keyboard_fallback():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert 'QAction("Zoom ind"' in app
    assert 'QKeySequence("Ctrl++")' in app
    assert 'QKeySequence("Ctrl+=")' in app
    assert 'QAction("Zoom ud"' in app
    assert 'QKeySequence("Ctrl+-")' in app


def test_project_open_has_full_window_busy_feedback():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    opening = (ROOT / "qt_project_open.py").read_text(encoding="utf-8")
    feedback = (ROOT / "qt_feedback.py").read_text(encoding="utf-8")
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    assert "class BusyOverlay" in feedback
    assert "QProgressBar" in feedback and "setRange(0, 0)" in feedback
    assert 'self.busy_overlay = BusyOverlay(self)' in app
    assert 'self._begin_busy("Åbner projekt…"' in opening
    assert 'self._update_busy("Indlæser projektfil…")' in opening
    assert 'self._update_busy("Opbygger plantegningen…")' in app
    assert "self._end_busy(success=True" in opening
    assert "QWidget#busyOverlay" in theme and "QFrame#busyCard" in theme
    assert "from qt_project_open import ProjectOpenMixin" in app
