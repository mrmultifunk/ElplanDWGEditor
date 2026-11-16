from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_PACKAGE = ROOT / "elplan_core"


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield node, [name.name for name in node.names]
        elif isinstance(node, ast.ImportFrom):
            yield node, [node.module or ""]


def test_elplan_core_imports_without_qt_or_win32_installed():
    module = importlib.import_module("elplan_core")
    assert module.__name__ == "elplan_core"


def test_elplan_core_never_imports_pyside6():
    for path in CORE_PACKAGE.rglob("*.py"):
        for _node, modules in _imports(path):
            assert not any(name == "PySide6" or name.startswith("PySide6.") for name in modules), path


def test_win32_imports_are_lazy_and_confined_to_platform_printing():
    for path in CORE_PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parent_by_node = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        import_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_nodes.append((node, [name.name for name in node.names]))
            elif isinstance(node, ast.ImportFrom):
                import_nodes.append((node, [node.module or ""]))
        for node, modules in import_nodes:
            win32 = [name for name in modules if name.startswith("win32")]
            if not win32:
                continue
            assert path == CORE_PACKAGE / "platform" / "printing.py"
            functions = []
            parent = parent_by_node.get(node)
            while parent is not None:
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(parent.name)
                parent = parent_by_node.get(parent)
            assert functions == ["print_vector_windows"]
