from __future__ import annotations

import core_logic as core
from elplan_core import appearance
from elplan_core.cables import categories, connections, geometry, lengths, sections


def test_cable_modules_are_reexported_through_core_facade():
    expected = {
        "normalize_hex_color": appearance,
        "normalize_cable_category_records": categories,
        "cable_effective_layer": categories,
        "normalize_cable_symbol_connections": connections,
        "cable_symbol_connections": connections,
        "polyline_length": geometry,
        "convert_cable_route_mode_geometry": geometry,
        "move_polyline_endpoint_flexible": geometry,
        "cable_length_metres": lengths,
        "cable_length_by_spec_metres": lengths,
        "cable_route_chain_length_metres": lengths,
        "normalize_cable_route_section_modes": sections,
        "cable_spec_for_section": sections,
        "split_cable_into_physical_segments": sections,
        "attach_symbol_to_existing_cable": sections,
    }

    for name, module in expected.items():
        assert getattr(core, name) is getattr(module, name)


def test_cable_layers_keep_existing_geometry_and_length_behaviour():
    cable = core.CablePlacement(
        points=[(0.0, 0.0), (3.0, 4.0)],
        cable_spec="3G1,5",
        symbol_connections=[
            {"point_index": 0, "symbol_uid": "a", "symbol_port": 0},
            {"point_index": 1, "symbol_uid": "b", "symbol_port": 0},
        ],
    )

    assert geometry.polyline_length(cable.points) == 5.0
    assert lengths.cable_length_metres(cable, 0.001) == 0.005
    assert sections.cable_spec_for_section(
        cable,
        cable.symbol_connections[0],
        cable.symbol_connections[1],
    ) == "3G1,5"


def test_cable_category_normalization_stays_available_without_core_imports():
    records = categories.normalize_cable_category_records(
        [{"id": "hovedledning", "name": "Hovedledning", "color": "#AABBCC", "line_style": "stiplet"}]
    )

    hovedledning = next(row for row in records if row["id"] == "hovedledning")
    assert hovedledning["color"] == "#aabbcc"
    assert hovedledning["line_style"] == "dash"
