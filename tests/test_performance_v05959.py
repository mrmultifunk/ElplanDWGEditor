from pathlib import Path
import time

import core_logic as core
from annotation_layout import RectSpatialIndex, choose_label_origin
from project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_sparse_cable_layout_has_no_quadratic_pause():
    cables = [
        core.CablePlacement(
            points=[(index * 100.0, 0.0), (index * 100.0 + 50.0, 0.0)],
            cable_id=f"K{index:04d}",
        )
        for index in range(1200)
    ]
    started = time.perf_counter()
    paths, metadata, groups = core.cable_visual_layout(cables, 10.0)
    elapsed = time.perf_counter() - started

    assert len(paths) == len(metadata) == 1200
    assert groups == []
    # A generous limit keeps the test stable on ordinary Windows hardware but
    # still detects the 0.59.58 list-slice/all-pairs regression (~1.3 s here).
    assert elapsed < 0.75


def test_spatial_collision_index_preserves_exact_label_choice():
    blockers = [
        (0.0, 0.0, 20.0, 20.0),
        (32.0, -8.0, 54.0, 18.0),
        (72.0, 0.0, 95.0, 24.0),
        (-45.0, 12.0, -15.0, 38.0),
    ]
    occupied = [(22.0, 23.0, 62.0, 37.0)]
    expected = choose_label_origin(
        (10.0, 10.0), blockers[0], 38.0, 15.0,
        blockers=blockers, occupied=occupied, preferred="right",
        gap=5.0, collision_padding=1.8, y_down=True,
    )

    blocker_index = RectSpatialIndex(blockers, cell_size=48.0)
    occupied_index = RectSpatialIndex(occupied, cell_size=48.0)
    indexed = choose_label_origin(
        (10.0, 10.0), blockers[0], 38.0, 15.0,
        blocker_index=blocker_index, occupied_index=occupied_index,
        preferred="right", gap=5.0, collision_padding=1.8, y_down=True,
    )
    assert indexed == expected


def test_zoom_render_items_are_reused_within_same_semantic_profile():
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    core_source = (ROOT / "core_logic.py").read_text(encoding="utf-8")

    assert APP_VERSION == core.APP_VERSION == "0.59.77"
    assert "render_signature==self._render_signature" in graphics
    annotation_qt = (ROOT / "qt_annotation_layout.py").read_text(encoding="utf-8")
    assert "signature==window._switch_badge_render_signature" in annotation_qt
    assert "for other_row in sweep[pos+1:]" not in core_source
