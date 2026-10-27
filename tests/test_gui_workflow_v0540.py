from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_version_0540():
    assert APP_VERSION == core.APP_VERSION == "0.59.73"


def test_global_search_and_command_palette_are_wired():
    source = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    search = (ROOT / "qt_search.py").read_text(encoding="utf-8")
    assert 'QKeySequence.StandardKey.Find' in source
    assert 'Ctrl+Shift+P' in source
    assert 'class SearchUiMixin' in search
    assert '_project_search_entries' in search
    assert '_activate_search_entry' in search
    assert 'cable_id' in search and 'cable_spec' in search


def test_start_page_and_recent_projects_are_central_workspace():
    source = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    welcome = (ROOT / "qt_welcome.py").read_text(encoding="utf-8")
    assert 'self._create_central_pages()' in source
    assert 'class WelcomePage' in welcome
    assert 'Seneste projekter' in welcome
    assert 'Nyt fra DWG/DXF' in welcome
    assert '_show_canvas_page' in welcome


def test_progressive_disclosure_and_toasts_are_used():
    source = (ROOT / "qt_app.py").read_text(encoding="utf-8") + (ROOT / "qt_cable_panel.py").read_text(encoding="utf-8")
    ui = (ROOT / "qt_ui.py").read_text(encoding="utf-8")
    feedback = (ROOT / "qt_feedback.py").read_text(encoding="utf-8")
    assert 'class DisclosureSection' in ui
    assert 'Udseende og placering' in source
    assert 'Parallel visning' in source
    assert 'Længde og rapport' in source
    assert 'class ToastOverlay' in feedback
    assert 'def _notify' in source
    assert 'Projekt gemt:' in source and 'self._notify' in source


def test_dialog_and_table_foundations_are_consistent():
    source = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    tables = (ROOT / "qt_table_utils.py").read_text(encoding="utf-8")
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    dialogs = source + (ROOT / "qt_articles.py").read_text(encoding="utf-8") + (ROOT / "qt_pl_box.py").read_text(encoding="utf-8")
    assert dialogs.count('configure_modern_dialog(') >= 4
    assert 'make_dialog_header(' in dialogs
    assert 'Tilpas kolonner til indhold' in tables
    assert 'Nulstil kolonnebredder' in tables
    assert 'setSectionsMovable(True)' in tables
    assert 'welcomePage' in theme and 'toastOverlay' in theme and 'disclosureHeader' in theme


def test_hover_bom_cache_avoids_rebuilding_every_hover():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    hover = (ROOT / "qt_hover.py").read_text(encoding="utf-8")
    assert 'self._hover_bom_cache = {}' in app
    assert 'getattr(self,"_hover_bom_cache",{}).get(uid)' in hover
    assert '_hover_price_lookup_signature' in hover
    assert 'self._hover_bom_cache.clear()' in app
