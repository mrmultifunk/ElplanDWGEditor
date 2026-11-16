import json
import math
from pathlib import Path

import pytest

import core_logic as core
from project_model import ProjectDocument, placement_from_raw, cable_from_raw, text_from_raw


def test_old_records_without_uid_get_stable_new_uid():
    p = placement_from_raw({"symbol": "socket", "x": 1, "y": 2})
    t = text_from_raw({"text": "x", "x": 1, "y": 2})
    assert p.uid and t.uid and p.uid != t.uid


def test_non_finite_geometry_is_rejected():
    with pytest.raises(ValueError):
        placement_from_raw({"symbol": "socket", "x": float("nan"), "y": 2})
    with pytest.raises(ValueError):
        cable_from_raw({"points": [[0, 0], [float("inf"), 2]]})
    with pytest.raises(ValueError):
        text_from_raw({"text": "x", "x": 0, "y": 0, "height": float("nan")})


def test_duplicate_symbol_uid_is_rejected(tmp_path: Path):
    uid = "same"
    path = tmp_path / "bad.elplan.json"
    path.write_text(json.dumps({
        "source_file": "floor.dxf",
        "placements": [
            {"uid": uid, "symbol": "socket", "x": 0, "y": 0},
            {"uid": uid, "symbol": "switch_1", "x": 1, "y": 1},
        ],
        "cables": [], "texts": []
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="dubleret symbol-id"):
        ProjectDocument.load(path)


def test_project_save_is_atomic_and_leaves_no_tmp(tmp_path: Path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    project = ProjectDocument.from_cad(source)
    project.placements.append(core.Placement(symbol="socket", x=1, y=2))
    target = tmp_path / "p.elplan.json"
    project.save(target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    assert raw["version"] == "0.59.82"
    assert not list(tmp_path.glob(".p.elplan.json.*.tmp"))


def test_qt_source_contains_unsaved_guard_and_layer_visibility_sync():
    source = (Path(__file__).resolve().parents[1] / "qt_app.py").read_text(encoding="utf-8")
    assert "def _confirm_discard_changes" in source
    assert 'QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel' in source
    assert "def _sync_symbol_annotation_visibility" in source
    assert "annotation.setVisible(symbol_visible and meta_visible)" in source


def test_delete_command_restores_reference_snapshot():
    source = (Path(__file__).resolve().parents[1] / "qt_commands.py").read_text(encoding="utf-8")
    assert "_symbol_reference_snapshot" in source
    assert "_cleanup_after_symbol_removed" in source
    assert "_restore_symbol_reference_snapshot" in source


def test_saved_state_snapshot_distinguishes_non_undo_changes(tmp_path: Path):
    source = tmp_path / "floor.dxf"
    source.write_text("dummy", encoding="utf-8")
    project = ProjectDocument.from_cad(source)
    target = tmp_path / "state.elplan.json"
    project.save(target)
    assert project.matches_saved_state()
    project.layer_visibility["X"] = False
    assert not project.matches_saved_state()


def test_rejected_project_does_not_register_custom_symbols(tmp_path):
    import core_logic as core
    from project_model import ProjectDocument

    code = core.make_custom_combo_code(["switch_1", "switch_2way"], "socket")
    before = {row["code"] for row in core.custom_symbol_records()}
    assert code not in before
    path = tmp_path / "bad_custom.elplan.json"
    path.write_text(json.dumps({
        "version": "0.36.0",
        "source_file": "x.dxf",
        "custom_symbols": [{"code": code, "name": "Må ikke registreres"}],
        "placements": [{
            "uid": "bad-symbol",
            "symbol": code,
            "x": 0,
            "y": 0,
            "size": -1,
        }],
    }), encoding="utf-8")

    with pytest.raises(ValueError):
        ProjectDocument.load(path)

    after = {row["code"] for row in core.custom_symbol_records()}
    assert code not in after


def test_qt_save_as_rebases_relative_cad_link_statically():
    source = Path('qt_app.py').read_text(encoding='utf-8')
    assert 'os.path.relpath(str(resolved_source), str(target.parent))' in source
    assert 'self.project.source_file = old_source' in source


def test_windows_start_skips_pip_when_dependencies_exist():
    source = Path('start_windows.bat').read_text(encoding='utf-8')
    assert 'python -c "import PySide6, ezdxf, reportlab; import win32api, win32print"' in source
    assert 'if errorlevel 1 (' in source
