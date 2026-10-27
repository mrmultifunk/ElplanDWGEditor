from pathlib import Path

import core_logic as core
import portability
from project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_dark_mode_version_and_normalization():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"
    assert core.normalize_appearance_mode(None) == "light"
    assert core.normalize_appearance_mode("Lys") == "light"
    assert core.normalize_appearance_mode("Mørk") == "dark"
    assert core.normalize_appearance_mode("mork") == "dark"
    assert core.normalize_appearance_mode("Følg Windows") == "system"
    assert core.normalize_appearance_mode("windows") == "system"
    assert core.normalize_dark_canvas("off") is False
    assert core.normalize_dark_canvas("nej") is False
    assert core.normalize_dark_canvas("on") is True
    assert core.normalize_dark_canvas("ja") is True


def test_dark_mode_is_machine_local_not_portable_core_data():
    settings = {
        "appearance_mode": "dark",
        "dark_canvas": True,
        "recent_projects": ["C:/x.elplan.json"],
        "favorite_symbols": ["socket_ground"],
    }
    portable = portability.portable_settings(settings)
    assert "appearance_mode" not in portable
    assert "dark_canvas" not in portable
    assert "recent_projects" not in portable
    assert portable["favorite_symbols"] == ["socket_ground"]


def test_dark_mode_ui_contract_is_present():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    assert 'view_menu.addMenu("Udseende")' in app
    assert 'QAction("Lys"' in app
    assert 'QAction("Mørk"' in app
    assert 'QAction("Følg Windows"' in app
    assert 'QAction("Mørk tegneflade"' in app
    assert 'QKeySequence("Ctrl+Alt+D")' in app
    assert 'app.setProperty("elplanDarkMode",dark)' in theme
    assert 'app.setProperty("elplanCanvasDark",dark_canvas)' in app
    assert "AppsUseLightTheme" in theme
    assert "_application_stylesheet" in theme
    assert "_refresh_action_icons" in app
    # PL cable entry and conductor-distribution diagrams have explicit dark-aware painters.
    pl = (ROOT / "qt_pl_box.py").read_text(encoding="utf-8")
    assert 'dark=_application_dark()' in pl[pl.index("class PLBoxDiagramWidget"):pl.index("class PLBoxDialog")]


def test_dark_canvas_is_screen_only_and_exports_stay_paper_based():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    export_block = app[app.index("    def export_pdf("):app.index("    def _rebuild_layer_list(")]
    assert "elplanDarkMode" not in export_block
    assert "elplanCanvasDark" not in export_block
    assert "core.export_vector_pdf" in export_block
    assert "core.print_vector_windows" in export_block
    # The on-screen print preview surrounds a real white PDF page even in dark UI.
    preview_block = app[app.index("class PrintPreviewCanvas"):app.index("class PrintPreviewDialog")]
    assert 'QColor("#ffffff")' in preview_block
    # Project colors are adapted only while painting the dark CAD canvas.
    assert "def _dark_canvas_contrast" in graphics
    assert "Project/export colors are never modified" in graphics
    assert 'QColor("#aeb8c4") if _canvas_is_dark()' in graphics
    assert "def refresh_theme" in graphics
