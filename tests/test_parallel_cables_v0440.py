import math
import core_logic as core


def _longest_mid_y(points):
    best=None; length=-1.0
    for a,b in zip(points,points[1:]):
        d=math.hypot(b[0]-a[0],b[1]-a[1])
        if d>length:
            length=d; best=(a,b)
    return (best[0][1]+best[1][1])/2.0


def test_six_cables_get_six_readable_lanes_and_one_bundle_group():
    cables=[core.CablePlacement(points=[(0,0),(200,0)],cable_id=f"K{i:02d}") for i in range(1,7)]
    paths,meta,groups=core.cable_visual_layout(cables,10.0,fan_length=22.0)
    ys=sorted(round(_longest_mid_y(paths[id(c)]),6) for c in cables)
    assert ys == [-25.0,-15.0,-5.0,5.0,15.0,25.0]
    assert all(meta[id(c)]["lane_count"]==6 for c in cables)
    assert any(g["count"]==6 and g["cable_ids"]==[f"K{i:02d}" for i in range(1,7)] for g in groups)
    assert all(paths[id(c)][0]==(0.0,0.0) and paths[id(c)][-1]==(200.0,0.0) for c in cables)


def test_lane_side_is_stable_when_input_order_changes():
    a=core.CablePlacement(points=[(0,0),(100,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,0),(100,0)],cable_id="K02")
    c=core.CablePlacement(points=[(0,0),(100,0)],cable_id="K03")
    p1,_,_=core.cable_visual_layout([a,b,c],10.0)
    first={x.cable_id:round(_longest_mid_y(p1[id(x)]),6) for x in (a,b,c)}
    p2,_,_=core.cable_visual_layout([c,a,b],10.0)
    second={x.cable_id:round(_longest_mid_y(p2[id(x)]),6) for x in (a,b,c)}
    assert first==second=={"K01":-10.0,"K02":0.0,"K03":10.0}


def test_partial_shared_route_only_separates_shared_segment():
    a=core.CablePlacement(points=[(0,0),(100,0),(200,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,0),(100,0),(100,100)],cable_id="K02")
    paths,meta,groups=core.cable_visual_layout([a,b],8.0,fan_length=16.0)
    assert meta[id(a)]["max_parallel"]==2
    assert meta[id(b)]["max_parallel"]==2
    assert any(g["count"]==2 for g in groups)
    assert paths[id(a)][0]==paths[id(b)][0]==(0.0,0.0)
    assert paths[id(a)][-1]==(200.0,0.0)
    assert paths[id(b)][-1]==(100.0,100.0)


def test_visual_layout_never_mutates_logical_geometry():
    cable=core.CablePlacement(points=[(0,0),(50,0),(50,50)],cable_id="K01")
    peer=core.CablePlacement(points=[(0,0),(50,0),(50,50)],cable_id="K02")
    before=[list(cable.points),list(peer.points)]
    core.cable_visual_layout([cable,peer],12.0)
    assert cable.points==before[0]
    assert peer.points==before[1]


def test_visually_merged_routes_with_small_coordinate_drift_still_get_lanes():
    # 0.30 * lane gap apart: visually almost the same line, but not CAD-identical.
    a=core.CablePlacement(points=[(0,0),(250,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,3.0),(250,3.0)],cable_id="K02")
    paths,meta,groups=core.cable_visual_layout([a,b],10.0,fan_length=22.0)
    assert meta[id(a)]["max_parallel"]==2
    assert meta[id(b)]["max_parallel"]==2
    assert any(g["count"]==2 for g in groups)
    assert abs(_longest_mid_y(paths[id(a)])-_longest_mid_y(paths[id(b)])) >= 9.0


def test_tiny_angle_error_over_long_shared_run_is_treated_as_same_visual_route():
    # About 0.7 degrees / max 3 world units deviation over 250 units.
    a=core.CablePlacement(points=[(0,0),(250,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,1.0),(250,3.0)],cable_id="K02")
    paths,meta,_=core.cable_visual_layout([a,b],10.0,fan_length=22.0)
    assert meta[id(a)]["max_parallel"]==2
    assert meta[id(b)]["max_parallel"]==2
    assert abs(_longest_mid_y(paths[id(a)])-_longest_mid_y(paths[id(b)])) >= 9.0


def test_visually_separate_parallel_routes_are_not_bundled_by_fuzzy_matching():
    a=core.CablePlacement(points=[(0,0),(250,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,8.0),(250,8.0)],cable_id="K02")
    paths,meta,groups=core.cable_visual_layout([a,b],10.0,fan_length=22.0)
    assert meta[id(a)]["max_parallel"]==1
    assert meta[id(b)]["max_parallel"]==1
    assert groups==[]
    assert paths[id(a)]==[(0.0,0.0),(250.0,0.0)]
    assert paths[id(b)]==[(0.0,8.0),(250.0,8.0)]


def test_same_route_with_different_collinear_breakpoints_is_detected():
    a=core.CablePlacement(points=[(0,0),(300,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,1.5),(70,1.5),(180,1.5),(300,1.5)],cable_id="K02")
    paths,meta,_=core.cable_visual_layout([a,b],10.0,fan_length=22.0)
    assert meta[id(a)]["max_parallel"]==2
    assert meta[id(b)]["max_parallel"]==2
    assert abs(_longest_mid_y(paths[id(a)])-_longest_mid_y(paths[id(b)])) >= 9.0


def test_shared_panel_endpoint_fans_out_despite_small_route_drift():
    # Typical panel case: exactly same terminal, then almost the same long run.
    a=core.CablePlacement(points=[(0,0),(300,0)],cable_id="G01")
    b=core.CablePlacement(points=[(0,0),(300,3.0)],cable_id="G11")
    paths,meta,_=core.cable_visual_layout([a,b],10.0,fan_length=22.0)
    pa,pb=paths[id(a)],paths[id(b)]
    assert meta[id(a)]["max_parallel"]==meta[id(b)]["max_parallel"]==2
    assert pa[0]==pb[0]==(0.0,0.0)
    assert len(pa)>2 and len(pb)>2
    assert pa[1] != pb[1]
    # The visible runs are separated while the physical terminal remains shared.
    assert abs(_longest_mid_y(pa)-_longest_mid_y(pb)) >= 9.0
