import math

import ezdxf

import core_logic as core


MARKED_SYMBOLS = {
    "socket_3fn": "3N",
    "socket_double_box": "2",
    "socket_triple_box": "3",
    "socket_double_box_earth": "2",
    "socket_triple_box_earth": "3",
    "combo_switch_double_2way_socket": "2",
    "switch_double_2way": "2",
    "pushbutton_4": "4",
    "emergency_light": "N",
    "water_heater": "VV",
    "electric_lock": "L",
    "smoke": "R",
}


def _text_primitives(symbol, size=100.0):
    return [row for row in core.symbol_primitives(symbol,size) if row[0] in {"text","upright_text"}]


def test_all_builtin_internal_markings_use_one_upright_primitive():
    for symbol in core.SYMBOL_NAMES_BY_CODE:
        assert all(row[0] != "text" for row in core.symbol_primitives(symbol,100.0)), symbol

    for symbol,expected in MARKED_SYMBOLS.items():
        rows=_text_primitives(symbol)
        assert rows, symbol
        assert {row[0] for row in rows} == {"upright_text"}, symbol
        assert expected in {str(row[3]) for row in rows}

    custom=core.make_custom_combo_code(["switch_double_2way"],"socket")
    assert {row[0] for row in _text_primitives(custom)} == {"upright_text"}


def test_boxed_socket_counts_are_centered_in_the_arch():
    for symbol in (
        "socket_double_box","socket_triple_box",
        "socket_double_box_earth","socket_triple_box_earth",
    ):
        _kind,x,y,_value,_height=_text_primitives(symbol)[0]
        assert x == 0.0
        assert y == -50.0


def test_internal_markings_stay_horizontal_in_dxf_at_all_quarter_turns():
    for symbol,expected in MARKED_SYMBOLS.items():
        for rotation in (0.0,90.0,180.0,270.0):
            doc=ezdxf.new()
            core.add_placement_to_dxf(
                doc.modelspace(),
                core.Placement(symbol=symbol,x=10.0,y=20.0,size=100.0,rotation=rotation),
            )
            labels=[entity for entity in doc.modelspace().query("TEXT") if entity.dxf.text==expected]
            assert labels, (symbol,rotation)
            assert all(math.isclose(float(entity.dxf.rotation),0.0,abs_tol=1e-9) for entity in labels)


def test_all_builtin_symbol_geometry_is_finite_and_has_a_positive_bbox():
    for symbol in core.SYMBOL_NAMES_BY_CODE:
        primitives=core.symbol_primitives(symbol,100.0)
        assert primitives, symbol
        x1,y1,x2,y2=core.symbol_local_bbox(symbol,100.0)
        assert all(math.isfinite(value) for value in (x1,y1,x2,y2)), symbol
        assert x2 > x1 and y2 > y1, symbol
