import ast
from pathlib import Path

import user_library

ROOT=Path(__file__).resolve().parents[1]


def test_theme_and_hover_are_split_out_of_monolithic_qt_app():
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    theme=(ROOT/"qt_theme.py").read_text(encoding="utf-8")
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    assert "from qt_theme import" in app
    assert "from qt_hover import HoverInfoMixin, _HoverInfoPopup" in app
    assert "class ElplanProxyStyle" in theme
    assert "def _application_stylesheet" in theme
    assert "class _HoverPreviewWidget" in hover
    assert "class _HoverInfoPopup" in hover
    assert len(app.splitlines()) < 10800


def test_mainwindow_has_no_duplicate_method_definitions():
    tree=ast.parse((ROOT/"qt_app.py").read_text(encoding="utf-8"))
    main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="MainWindow")
    names=[]
    for node in main.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            names.append(node.name)
    assert len(names)==len(set(names))


def test_article_catalog_cache_returns_defensive_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("ELPLAN_USER_DATA_DIR",str(tmp_path))
    monkeypatch.setattr(user_library,"_ARTICLE_CATALOG_CACHE_SIGNATURE",None)
    monkeypatch.setattr(user_library,"_ARTICLE_CATALOG_CACHE_ROWS",None)
    first=user_library.load_core_article_catalog()
    second=user_library.load_core_article_catalog()
    assert first == second
    assert first is not second
    if first:
        original=second[0].get("description")
        first[0]["description"]="MUTATED"
        third=user_library.load_core_article_catalog()
        assert third[0].get("description") == original


def test_zoom_refresh_is_coalesced_and_gui_audit_is_documented():
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    assert "self._zoom_visual_refresh_timer.setInterval(80)" in app
    assert "def _refresh_zoom_dependent_visuals" in app
    assert "self._zoom_visual_refresh_timer.start()" in app
    assert (ROOT/"docs"/"history"/"GUI_AUDIT_0.52.0.md").is_file()
    assert (ROOT/"docs"/"history"/"MAINTENANCE_0.52.0.md").is_file()
