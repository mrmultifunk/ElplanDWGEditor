from pathlib import Path
import core_logic as core


def test_legacy_startup_corruption_is_repaired_once():
    broken={
        "cable_snap_routes": True,
        "cable_parallel_lanes": False,
        "cable_lane_gap_px": 5,
        "cable_bundle_badges": False,
        "cable_focus_related": False,
    }
    fixed=core.normalize_cable_visual_settings(broken)
    assert fixed["cable_parallel_lanes"] is True
    assert fixed["cable_lane_gap_px"] == 10
    assert fixed["cable_bundle_badges"] is True
    assert fixed["cable_focus_related"] is True
    assert fixed["cable_visual_settings_init_fixed_0444"] is True


def test_user_choice_is_preserved_after_repair_marker():
    settings={
        "cable_visual_settings_init_fixed_0444": True,
        "cable_parallel_lanes": False,
        "cable_lane_gap_px": 14,
        "cable_bundle_badges": False,
        "cable_focus_related": True,
    }
    fixed=core.normalize_cable_visual_settings(settings)
    assert fixed["cable_parallel_lanes"] is False
    assert fixed["cable_lane_gap_px"] == 14
    assert fixed["cable_bundle_badges"] is False


def test_cable_controls_restore_with_signals_blocked():
    panel=Path("qt_cable_panel.py").read_text(encoding="utf-8")
    app=Path("qt_app.py").read_text(encoding="utf-8")
    block=panel.split("# Restore defaults/settings atomically.",1)[1].split("def _set_cable_panel_context",1)[0]
    assert "self._loading_cable_panel = True" in block
    assert "QSignalBlocker" in block
    assert "self.cable_snap_routes" in block
    assert "self.cable_parallel_lanes" in block
    assert "self._loading_cable_panel = False" in block
    visual=app.split("def _cable_visual_settings_changed",1)[1].split("def _rebuild_cable_visual_cache",1)[0]
    assert "_loading_cable_panel" in visual
