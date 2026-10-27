from copy import deepcopy
import math
import core_logic as core


def _mid_y(points):
    # Longest interior segment is the separated lane in these fixtures.
    best=None; best_len=-1
    for a,b in zip(points,points[1:]):
        length=math.hypot(b[0]-a[0],b[1]-a[1])
        if length>best_len:
            best_len=length; best=(a,b)
    return (best[0][1]+best[1][1])/2


def test_three_identical_routes_get_three_lanes_and_keep_endpoints():
    cables=[core.CablePlacement(points=[(0,0),(100,0)],cable_id=f"K{i}") for i in range(3)]
    before=deepcopy([c.points for c in cables])
    visual=core.cable_visual_paths(cables,10.0,fan_length=20.0)
    ys=sorted(round(_mid_y(visual[id(c)]),6) for c in cables)
    assert ys == [-10.0,0.0,10.0]
    for c in cables:
        pts=visual[id(c)]
        assert pts[0] == (0.0,0.0)
        assert pts[-1] == (100.0,0.0)
    assert [c.points for c in cables] == before


def test_reverse_draw_direction_still_uses_distinct_physical_lanes():
    a=core.CablePlacement(points=[(0,0),(100,0)])
    b=core.CablePlacement(points=[(100,0),(0,0)])
    visual=core.cable_visual_paths([a,b],10.0,fan_length=20.0)
    ya=_mid_y(visual[id(a)]); yb=_mid_y(visual[id(b)])
    assert round(abs(ya-yb),6) == 10.0
    assert ya*yb < 0


def test_parallel_but_separate_routes_are_not_moved():
    a=core.CablePlacement(points=[(0,0),(100,0)])
    b=core.CablePlacement(points=[(0,20),(100,20)])
    visual=core.cable_visual_paths([a,b],10.0)
    assert visual[id(a)] == [(0.0,0.0),(100.0,0.0)]
    assert visual[id(b)] == [(0.0,20.0),(100.0,20.0)]


def test_shared_lamp_endpoint_fans_out_but_stays_connected():
    a=core.CablePlacement(points=[(0,0),(100,0),(100,50)])
    b=core.CablePlacement(points=[(0,0),(100,0),(100,-50)])
    visual=core.cable_visual_paths([a,b],8.0,fan_length=16.0)
    pa=visual[id(a)]; pb=visual[id(b)]
    assert pa[0] == pb[0] == (0.0,0.0)
    # Immediately after the common terminal the visible lanes are different.
    assert pa[1] != pb[1]
    assert a.points[-1] == (100,50) and b.points[-1] == (100,-50)


def test_label_position_can_follow_visual_lane():
    a=core.CablePlacement(points=[(0,0),(100,0)])
    b=core.CablePlacement(points=[(0,0),(100,0)])
    visual=core.cable_visual_paths([a,b],10.0,fan_length=20.0)
    la=core.polyline_label_point(visual[id(a)])
    lb=core.polyline_label_point(visual[id(b)])
    assert not math.isclose(la[1],lb[1],abs_tol=1e-9)
