from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_window_module_is_kept_below_post_split_limit():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert len(app.splitlines()) < 6200
    assert (ROOT / "qt_articles.py").is_file()
    assert (ROOT / "qt_pl_box.py").is_file()
    assert (ROOT / "qt_widgets.py").is_file()


def test_heavy_feature_dialogs_are_lazy_imported_from_mainwindow_methods():
    tree = ast.parse((ROOT / "qt_app.py").read_text(encoding="utf-8"))
    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top_level_imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            top_level_imports.extend(alias.name for alias in node.names)
    assert "qt_articles" not in top_level_imports
    assert "qt_pl_box" not in top_level_imports

    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert "from qt_articles import BomManagerDialog" in app
    assert "from qt_articles import ArticlePickerDialog" in app
    assert "from qt_pl_box import PLBoxDialog" in app


def test_article_and_pl_modules_do_not_depend_on_qt_app():
    articles = (ROOT / "qt_articles.py").read_text(encoding="utf-8")
    pl = (ROOT / "qt_pl_box.py").read_text(encoding="utf-8")
    widgets = (ROOT / "qt_widgets.py").read_text(encoding="utf-8")
    assert "import qt_app" not in articles + pl + widgets
    assert "from qt_app" not in articles + pl + widgets
