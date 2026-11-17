from __future__ import annotations

from types import SimpleNamespace

import core_logic as core
from elplan_core import settings
from elplan_core.platform import oda


def test_core_logic_reexports_settings_and_oda_functions():
    for name in (
        "_settings_file",
        "_recovery_file",
        "load_app_settings",
        "save_app_settings",
        "normalize_appearance_mode",
        "normalize_dark_canvas",
        "normalize_recent_project_paths",
        "normalize_cable_visual_settings",
    ):
        assert getattr(core, name) is getattr(settings, name), name
    assert core.set_oda_exec_path is oda.set_oda_exec_path
    assert core.detect_oda_exec_path is oda.detect_oda_exec_path


def test_settings_roundtrip_uses_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ELPLAN_USER_DATA_DIR", str(tmp_path))
    payload = {"appearance_mode": "dark", "favorite_symbols": ["socket"]}

    settings.save_app_settings(payload)

    assert settings._settings_file() == tmp_path / "settings.json"
    assert settings._recovery_file() == tmp_path / "recovery.elplan.json"
    assert settings.load_app_settings() == payload
    assert not list(tmp_path.glob(".settings.json.*.tmp"))


def test_oda_path_setup_persists_the_selected_converter(tmp_path, monkeypatch):
    converter = tmp_path / "ODAFileConverter.exe"
    converter.write_bytes(b"")
    option_calls = []
    saved = []
    monkeypatch.setattr(oda.ezdxf.options, "set", lambda *args: option_calls.append(args))
    monkeypatch.setattr(oda, "load_app_settings", lambda: {"existing": True})
    monkeypatch.setattr(oda, "save_app_settings", lambda data: saved.append(dict(data)))

    assert oda.set_oda_exec_path(converter) is True
    assert option_calls == [("odafc-addon", "win_exec_path", str(converter))]
    assert saved == [{"existing": True, "oda_exec_path": str(converter)}]
    assert oda.set_oda_exec_path(tmp_path / "forkert.exe") is False


def test_oda_detection_prefers_the_saved_existing_path(tmp_path, monkeypatch):
    converter = tmp_path / "ODAFileConverter.exe"
    converter.write_bytes(b"")
    selected = []
    monkeypatch.setattr(oda, "os", SimpleNamespace(name="nt", environ={}))
    monkeypatch.setattr(oda, "load_app_settings", lambda: {"oda_exec_path": str(converter)})
    monkeypatch.setattr(oda.odafc, "get_win_exec_path", lambda: "")
    monkeypatch.setattr(oda.shutil, "which", lambda _name: None)
    monkeypatch.setattr(oda, "set_oda_exec_path", lambda path: selected.append(path) or True)

    assert oda.detect_oda_exec_path() == str(converter)
    assert selected == [converter]
