import core_logic as core

def test_custom_combo_module_channel_layout():
    code=core.make_custom_combo_code(["switch_1","switch_1","switch_2way"],"socket")
    layout=core.association_module_layout(code,500)
    assert len(layout)==3
    assert [rec[5] for rec in layout]==[(0,),(1,),(2,)]
    assert layout[0][3] > layout[1][3] > layout[2][3]

def test_crown_channels_share_physical_module():
    layout=core.association_module_layout("switch_crown",500)
    assert len(layout)==1
    assert layout[0][5]==(0,1)

def test_combo_crown_plus_one_mapping():
    layout=core.association_module_layout("combo_row_crown_1_socket",500)
    assert layout[0][5]==(0,1)
    assert layout[1][5]==(2,)
