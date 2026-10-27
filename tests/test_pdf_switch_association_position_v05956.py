import core_logic as core

def test_horizontal_switch_relation_tag_is_below_symbol():
    x,y,side=core.output_switch_association_tag_origin(50,50,(30,40,70,55),12,7)
    assert side=="below" and x==44 and y < 33

def test_vertical_switch_relation_tag_is_right_of_symbol():
    x,y,side=core.output_switch_association_tag_origin(50,50,(42,20,57,80),12,7)
    assert side=="right" and x > 57 and y==46.5

def test_tag_orientation_uses_rendered_bounds():
    assert core.output_switch_association_tag_origin(10,10,(0,0,100,20),10,6,overview=True)[2]=="below"
