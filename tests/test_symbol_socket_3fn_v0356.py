import core_logic as core


def test_socket_3fn_text_is_upright_and_centered_in_arch():
    size=100.0
    texts=[p for p in core.symbol_primitives("socket_3fn",size) if p[0]=="upright_text"]
    assert len(texts)==1
    _kind,x,y,value,h=texts[0]
    assert value=="3N"
    assert 0.40*size <= h <= 0.48*size
    assert x == 0
    assert -0.55*size <= y <= -0.45*size


def test_socket_3fn_physical_bbox_stays_reasonably_compact():
    x1,y1,x2,y2=core.symbol_local_bbox("socket_3fn",100.0)
    assert x1 >= -55.0
    assert x2 <= 55.0
