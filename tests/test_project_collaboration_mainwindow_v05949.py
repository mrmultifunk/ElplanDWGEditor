from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

def _main_bases():
    tree=ast.parse((ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8"))
    main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="MainWindow")
    return [ast.unparse(base) for base in main.bases]

def test_mainwindow_wires_collaboration_mixin():
    bases=_main_bases()
    assert "ProjectCollaborationMixin" in bases
    assert "ProjectOpenMixin" in bases

def test_collaboration_startup_and_shutdown_hooks_are_wired():
    source=(ROOT/"elplan_qt/qt_app.py").read_text(encoding="utf-8")
    assert "from elplan_qt.qt_project_collaboration import ProjectCollaborationMixin" in source
    assert "self._init_project_collaboration_state()" in source
    assert "self._setup_project_collaboration_ui()" in source
    assert "self._release_current_project_lock()" in source
