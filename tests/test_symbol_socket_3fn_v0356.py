import core_logic as core


def test_socket_3fn_text_is_upright_and_centered_in_arch():
    size=100.0
    texts=[p for p in core.symbol_primitives("socket_3fn",size) if p[0]=="upright_text"]
    assert len(texts)==1
    _kind,x,y,value,h=texts[0]
    assert value=="3N"
    assert 0.40*size <= h <= 0.48*size
    assert x == 0
    expected=(core.SOCKET_3FN_BODY_OFFSET_FACTOR-.50)*size
    assert abs(y-expected) < 1e-9


def test_socket_3fn_physical_bbox_stays_reasonably_compact():
    x1,y1,x2,y2=core.symbol_local_bbox("socket_3fn",100.0)
    assert x1 >= -55.0
    assert x2 <= 55.0


def test_socket_3fn_matches_standard_socket_size_when_wall_aligned():
    size=100.0

    def wall_relative_bbox(symbol):
        x1,y1,x2,y2=core.symbol_local_bbox(symbol,size)
        _mx,my=core.symbol_mount_points(symbol,size)[0]
        return x1,y1-my,x2,y2-my

    normal=wall_relative_bbox("socket")
    three_phase=wall_relative_bbox("socket_3fn")
    assert three_phase == normal


def test_socket_3fn_visible_connection_point_follows_shifted_body():
    size=100.0
    wall_port,body_port=core.symbol_connection_points("socket_3fn",size)
    assert wall_port == (0.0,size*core.EXTENDED_SOCKET_MOUNT_FACTOR)
    assert body_port == (0.0,size*core.SOCKET_3FN_BODY_OFFSET_FACTOR)
