import core_logic as core


def test_all_standard_switch_capacities_and_channel_types():
    expected = {
        "switch_1": (1, ["switch_1"]),
        "switch_crown": (2, ["switch_crown", "switch_crown"]),
        "switch_2way": (1, ["switch_2way"]),
        "switch_cross": (1, ["switch_cross"]),
        "switch_double_2way": (2, ["switch_double_2way", "switch_double_2way"]),
        "pushbutton": (1, ["pushbutton"]),
        "pushbutton_indicator": (1, ["pushbutton_indicator"]),
        "pushbutton_4": (4, ["pushbutton_4"] * 4),
    }
    for symbol, (capacity, channels) in expected.items():
        assert core.association_capacity(symbol) == capacity
        assert core.association_channel_bases(symbol) == channels


def test_correspondence_channels_prefer_existing_relation():
    for symbol in ("switch_2way", "switch_cross", "switch_double_2way"):
        for i in range(core.association_capacity(symbol)):
            assert core.association_channel_prefers_existing(symbol, i)
    for symbol in ("switch_1", "switch_crown", "pushbutton", "pushbutton_indicator", "pushbutton_4"):
        for i in range(core.association_capacity(symbol)):
            assert not core.association_channel_prefers_existing(symbol, i)


def test_combo_channel_expansion_matches_capacity():
    symbols = (
        "combo_switch_crown_socket",
        "combo_switch_double_2way_socket",
        "combo_row_crown_1_socket",
        "combo_row_2way_2way_socket",
        "combo_row_crown_2x1_socket",
    )
    for symbol in symbols:
        assert len(core.association_channel_bases(symbol)) == core.association_capacity(symbol)


def test_custom_combo_uses_same_channel_rules():
    symbol=core.make_custom_combo_code(["switch_crown","switch_2way","pushbutton"],"socket")
    assert core.association_capacity(symbol)==4
    assert core.association_channel_bases(symbol)==[
        "switch_crown","switch_crown","switch_2way","pushbutton"
    ]
    assert [core.association_channel_prefers_existing(symbol,i) for i in range(4)]==[False,False,True,False]
