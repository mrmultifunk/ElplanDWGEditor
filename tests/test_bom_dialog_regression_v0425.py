from pathlib import Path
import ast


def _bom_manager_class():
    source = (Path(__file__).resolve().parents[1] / "qt_articles.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "BomManagerDialog":
            return node
    raise AssertionError("BomManagerDialog blev ikke fundet")


def test_fmt_qty_is_staticmethod():
    cls = _bom_manager_class()
    method = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_fmt_qty"), None)
    assert method is not None
    decorators = [d.id for d in method.decorator_list if isinstance(d, ast.Name)]
    assert "staticmethod" in decorators
    assert [arg.arg for arg in method.args.args] == ["value"]


def test_refresh_bom_uses_fmt_qty_for_article_and_missing_rows():
    cls = _bom_manager_class()
    method = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_refresh_bom"), None)
    assert method is not None
    calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)]
    fmt_calls = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "_fmt_qty"]
    # One for normal BOM rows and one for the missing-assignment rows.
    assert len(fmt_calls) >= 2
