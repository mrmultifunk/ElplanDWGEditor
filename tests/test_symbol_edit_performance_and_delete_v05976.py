from __future__ import annotations

import inspect
from pathlib import Path

import core_logic as core
from project_model import APP_VERSION
from qt_app import MainWindow
from qt_cable_attach import CableAttachMixin


ROOT=Path(__file__).resolve().parents[1]


def test_version_and_actions_are_removed():
    assert APP_VERSION==core.APP_VERSION=="0.59.76"
    assert not (ROOT/".github/workflows/tests.yml").exists()
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    assert "actions/workflows/tests.yml" not in readme
    assert "GitHub Actions kører" not in readme


def test_symbol_drag_defers_plan_wide_work_until_release():
    moved=inspect.getsource(MainWindow._symbol_moved)
    finished=inspect.getsource(MainWindow._symbol_drag_finished)
    connected=inspect.getsource(MainWindow._refresh_connected_cables)
    assert "_refresh_switch_association_badges" not in moved
    assert "finalize=False" in moved
    assert "_rebuild_cable_visual_cache" in finished
    assert "_symbol_drag_cables_changed" in finished
    assert "item.refresh(update_handles=False)" in connected


def test_selection_reuses_catalog_and_only_refreshes_changed_annotations():
    source=inspect.getsource(MainWindow._selection_changed)
    assert "load_core_article_catalog" not in source
    assert "_cached_article_catalog" in source
    assert "selected_annotation_uids | self._last_selected_annotation_uids" in source
    assert "_symbol_metadata_refresh_timer.start()" in source


def test_symbol_delete_is_visible_and_locked_state_is_explained():
    properties=inspect.getsource(MainWindow._create_properties_dock)
    deletion=inspect.getsource(MainWindow.delete_selected_symbols)
    context=inspect.getsource(CableAttachMixin._symbol_context_menu)
    assert "Slet symbol" in properties
    assert "dangerButton" in properties
    assert "QSignalBlocker(self.scene)" in deletion
    assert "Symbolet er låst" in deletion
    assert "Slet symbol" in context
    assert "delete_selected_symbols" in context


def test_silent_pose_updates_do_not_reenter_move_handler():
    source=(ROOT/"qt_graphics.py").read_text(encoding="utf-8")
    assert "ItemPositionHasChanged and self.scene() is not None and not self._suppress_snap" in source
