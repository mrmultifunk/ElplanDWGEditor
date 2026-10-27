import math
from pathlib import Path

import core_logic as core


def test_free_route_is_one_direct_diagonal_segment():
    assert core.cable_route_points_to((0, 0), (3, 4), False) == [(3.0, 4.0)]


def test_orthogonal_route_still_inserts_90_degree_corner():
    pts = core.cable_route_points_to((0, 0), (10, 4), True)
    assert pts == [(10.0, 0.0), (10.0, 4.0)]


def test_diagonal_cable_length_uses_true_geometry():
    cable = core.CablePlacement(points=[(0, 0), (3, 4)], orthogonal=False)
    assert math.isclose(core.cable_route_length(cable), 5.0)


def test_parallel_layout_separates_shared_diagonal_routes():
    a = core.CablePlacement(points=[(0, 0), (100, 100)], cable_id="K01", orthogonal=False)
    b = core.CablePlacement(points=[(0, 0), (100, 100)], cable_id="K02", orthogonal=False)
    visual = core.cable_visual_paths([a, b], 10.0, fan_length=20.0)
    pa, pb = visual[id(a)], visual[id(b)]
    assert pa[0] == pb[0] == (0.0, 0.0)
    assert pa[-1] == pb[-1] == (100.0, 100.0)
    # The cosmetic lane points after the shared anchor must not coincide.
    assert len(pa) >= 3 and len(pb) >= 3
    assert math.hypot(pa[1][0]-pb[1][0], pa[1][1]-pb[1][1]) > 5.0


def test_cable_panel_exposes_route_mode_as_primary_control():
    source = Path("qt_app.py").read_text(encoding="utf-8") + Path("qt_cable_panel.py").read_text(encoding="utf-8")
    assert 'self.cable_route_mode_combo.addItem("Fri / diagonal", "free")' in source
    assert 'self.cable_route_mode_combo.addItem("Ortogonal (90°)", "orthogonal")' in source
    assert 'self.app_settings.get("cable_route_mode", "free")' in source
