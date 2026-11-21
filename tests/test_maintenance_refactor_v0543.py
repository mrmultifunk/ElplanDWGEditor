from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imports(tree):
    for node in tree:
        if isinstance(node, ast.ImportFrom):
            yield node.module or ""
            if node.module == "elplan_qt":
                yield from (f"elplan_qt.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)


def test_main_window_module_is_kept_below_post_split_limit():
    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    # Registrér den eksisterende 0.59.85-baseline uden at tillade yderligere
    # vækst under den forestående core-refaktorering.
    assert len(app.splitlines()) <= 6980
    assert (ROOT / "elplan_qt/qt_articles.py").is_file()
    assert (ROOT / "elplan_qt/qt_pl_box.py").is_file()
    assert (ROOT / "elplan_qt/qt_widgets.py").is_file()


def test_heavy_feature_dialogs_are_lazy_imported_from_mainwindow_methods():
    tree = ast.parse((ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8"))
    top_level_imports = set(_imports(tree.body))
    assert "elplan_qt.qt_articles" not in top_level_imports
    assert "elplan_qt.qt_pl_box" not in top_level_imports

    app = (ROOT / "elplan_qt/qt_app.py").read_text(encoding="utf-8")
    assert "from elplan_qt.qt_articles import BomManagerDialog" in app
    assert "from elplan_qt.qt_articles import ArticlePickerDialog" in app
    assert "from elplan_qt.qt_pl_box import PLBoxDialog" in app


def test_article_and_pl_modules_do_not_depend_on_qt_app():
    articles = (ROOT / "elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    pl = (ROOT / "elplan_qt/qt_pl_box.py").read_text(encoding="utf-8")
    widgets = (ROOT / "elplan_qt/qt_widgets.py").read_text(encoding="utf-8")
    for source in (articles, pl, widgets):
        assert "elplan_qt.qt_app" not in set(_imports(ast.walk(ast.parse(source))))
