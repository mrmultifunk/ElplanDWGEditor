import math
import core_logic as core


def _screenish_separation_after_start(paths, a, b):
    pa=paths[id(a)]; pb=paths[id(b)]
    assert pa[0] == pb[0]
    assert len(pa) >= 3 and len(pb) >= 3
    return math.hypot(pa[1][0]-pb[1][0],pa[1][1]-pb[1][1])


def test_common_panel_anchor_forces_fanout_even_when_route_overlap_match_fails():
    # Same physical panel point and same departure direction, but the second
    # cable drifts far enough away that fuzzy shared-segment matching alone is
    # not allowed to bundle the long run. The panel exit must still fan out.
    a=core.CablePlacement(points=[(0,0),(300,0)],cable_id="G01")
    b=core.CablePlacement(points=[(0,0),(300,12)],cable_id="G11")
    paths,meta,_=core.cable_visual_layout([a,b],10.0,fan_length=28.0)
    assert meta[id(a)]["max_parallel"] == 2
    assert meta[id(b)]["max_parallel"] == 2
    assert _screenish_separation_after_start(paths,a,b) >= 9.0
    assert paths[id(a)][0] == paths[id(b)][0] == (0.0,0.0)


def test_common_symbol_port_is_authoritative_for_panel_fanout():
    a=core.CablePlacement(points=[(0,0),(80,0),(200,0)],cable_id="G01")
    b=core.CablePlacement(points=[(0,0),(70,1),(200,14)],cable_id="G11")
    core.set_cable_symbol_connections(a,[{"point_index":0,"symbol_uid":"PANEL","symbol_port":0}])
    core.set_cable_symbol_connections(b,[{"point_index":0,"symbol_uid":"PANEL","symbol_port":0}])
    paths,meta,_=core.cable_visual_layout([a,b],10.0,fan_length=28.0)
    assert meta[id(a)]["max_parallel"] == meta[id(b)]["max_parallel"] == 2
    assert paths[id(a)][0] == paths[id(b)][0] == (0.0,0.0)
    assert _screenish_separation_after_start(paths,a,b) >= 9.0


def test_interior_symbol_connection_stays_on_physical_anchor_when_lane_is_offset():
    a=core.CablePlacement(points=[(0,0),(100,0),(200,0)],cable_id="K01")
    b=core.CablePlacement(points=[(0,0),(100,0),(200,0)],cable_id="K02")
    core.set_cable_symbol_connections(a,[{"point_index":1,"symbol_uid":"L01","symbol_port":0}])
    core.set_cable_symbol_connections(b,[{"point_index":1,"symbol_uid":"L01","symbol_port":0}])
    paths,_,_=core.cable_visual_layout([a,b],10.0,fan_length=20.0)
    assert (100.0,0.0) in paths[id(a)]
    assert (100.0,0.0) in paths[id(b)]
    assert a.points == [(0,0),(100,0),(200,0)]
    assert b.points == [(0,0),(100,0),(200,0)]


def test_six_cables_from_same_panel_port_get_six_distinct_departure_lanes():
    cables=[]
    for i in range(6):
        c=core.CablePlacement(points=[(0,0),(300,float(i)*3.0)],cable_id=f"K{i+1:02d}")
        core.set_cable_symbol_connections(c,[{"point_index":0,"symbol_uid":"PANEL","symbol_port":0}])
        cables.append(c)
    paths,meta,_=core.cable_visual_layout(cables,10.0,fan_length=28.0)
    ys=sorted(round(paths[id(c)][1][1],6) for c in cables)
    assert len(set(ys)) == 6
    assert all(meta[id(c)]["max_parallel"] == 6 for c in cables)
