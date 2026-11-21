from elplan_shared.interaction_math import axis_alignment_snap


def test_axis_alignment_snaps_x_and_y_independently():
    x,y,gx,gy=axis_alignment_snap(99.0,202.0,[(100.0,50.0),(10.0,200.0)],5.0)
    assert (x,y)==(100.0,200.0)
    assert gx==100.0 and gy==200.0


def test_axis_alignment_uses_nearest_candidate_per_axis():
    x,y,gx,gy=axis_alignment_snap(100.0,100.0,[(96.0,60.0),(102.0,107.0),(30.0,99.0)],5.0)
    assert x==102.0
    assert y==99.0
    assert gx==102.0 and gy==99.0


def test_axis_alignment_does_not_snap_outside_tolerance():
    x,y,gx,gy=axis_alignment_snap(10.0,20.0,[(30.0,50.0)],5.0)
    assert (x,y)==(10.0,20.0)
    assert gx is None and gy is None
