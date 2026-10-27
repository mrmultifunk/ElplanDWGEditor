from interaction_math import spot_row_axis_assist
from project_model import APP_VERSION
import core_logic as core


def test_version_v05945():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"


def test_spot_row_soft_horizontal_and_vertical_snap():
    x,y,gx,gy,label=spot_row_axis_assist(100.0,3.0,(0.0,0.0),5.0)
    assert (x,y,gx,gy,label)==(100.0,0.0,None,0.0,"VANDRET")

    x,y,gx,gy,label=spot_row_axis_assist(3.0,100.0,(0.0,0.0),5.0)
    assert (x,y,gx,gy,label)==(0.0,100.0,0.0,None,"LODRET")


def test_spot_row_remains_diagonal_outside_tolerance_and_alt_disables_snap():
    assert spot_row_axis_assist(100.0,25.0,(0.0,0.0),5.0)[-1] == ""
    x,y,*_=spot_row_axis_assist(100.0,3.0,(0.0,0.0),5.0,disabled=True)
    assert (x,y)==(100.0,3.0)


def test_spot_row_near_start_snaps_only_one_axis():
    x,y,gx,gy,label=spot_row_axis_assist(2.0,3.0,(0.0,0.0),5.0)
    assert (x,y)!=(0.0,0.0)
    assert label in {"VANDRET","LODRET"}
