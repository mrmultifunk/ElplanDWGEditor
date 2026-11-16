from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_05017():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def test_recent_project_paths_are_deduplicated_filtered_and_limited(tmp_path):
    a = tmp_path / "A.elplan.json"
    b = tmp_path / "B.elplan.json"
    c = tmp_path / "C.elplan.json"
    for path in (a, b, c):
        path.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing.elplan.json"

    rows = core.normalize_recent_project_paths([str(a), str(a), str(missing), str(b), str(c)], limit=2, existing_only=True)
    assert rows == [str(a.resolve()), str(b.resolve())]


def test_recent_projects_menu_and_tracking_are_wired():
    source = Path("qt_app.py").read_text(encoding="utf-8")
    opening = Path("qt_project_open.py").read_text(encoding="utf-8")
    assert 'addMenu("Åbn seneste…")' in source
    assert '"recent_projects"' in source
    assert 'QKeySequence("Ctrl+Shift+O")' in source
    assert 'self._remember_recent_project(target)' in source
    assert 'self._remember_recent_project(project.path or project_path)' in opening
    assert 'clear_action.triggered.connect(self._clear_recent_projects)' in source
