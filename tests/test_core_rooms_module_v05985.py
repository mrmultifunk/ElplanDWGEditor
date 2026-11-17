from __future__ import annotations

import core_logic as core
from elplan_core.cables import sections
from elplan_core.models import CablePlacement, RoomPlacement
from elplan_core import rooms


def test_core_logic_reexports_moved_room_functions():
    names = (
        "room_polygon_centroid",
        "room_contains_point",
        "room_for_point",
        "room_display_text",
        "room_output_label",
        "_segment_edge_intersection_t",
        "rooms_along_polyline",
        "cable_rooms",
        "polyline_room_lengths",
        "cable_room_length_metres",
        "cable_length_by_spec_room_metres",
        "cable_room_marking",
        "cable_light_endpoint_marking",
    )
    for name in names:
        assert getattr(core, name) is getattr(rooms, name), name


def test_core_logic_reexports_room_prerequisite_cable_helpers():
    names = (
        "normalize_cable_symbol_connections",
        "cable_symbol_connections",
        "normalize_cable_spec_section_overrides",
        "_cable_route_section_key",
        "_cable_spec_section_key",
        "cable_connection_sections",
        "cable_spec_for_section",
        "cable_spec_section_at_segment",
    )
    for name in names:
        assert getattr(core, name) is getattr(sections, name), name


def test_room_length_by_spec_uses_lower_level_cable_sections_directly():
    room = RoomPlacement(
        "Stue",
        [(-1.0, -1.0), (11.0, -1.0), (11.0, 1.0), (-1.0, 1.0)],
        code="R01",
    )
    cable = CablePlacement(
        [(0.0, 0.0), (10.0, 0.0)],
        cable_spec="3G1,5",
        symbol_connections=[
            {"point_index": 0, "symbol_uid": "a", "symbol_port": 0},
            {"point_index": 1, "symbol_uid": "b", "symbol_port": 0},
        ],
        spec_section_overrides=[{
            "a_symbol_uid": "a",
            "a_symbol_port": 0,
            "b_symbol_uid": "b",
            "b_symbol_port": 0,
            "cable_spec": "5G1,5",
        }],
    )

    assert rooms.cable_length_by_spec_room_metres(cable, [room], room.uid, 1.0) == {
        "5G1,5": 10.0,
    }
