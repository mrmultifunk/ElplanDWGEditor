from __future__ import annotations

import core_logic as core
from elplan_core import associations
from elplan_core.pl_box import model as pl_box_model
from elplan_core.symbols import clipboard, geometry, registry


def test_symbol_modules_are_reexported_through_core_facade():
    expected = {
        "parse_custom_combo_symbol": registry,
        "combo_modules": registry,
        "symbol_display_name": registry,
        "symbol_primitives": geometry,
        "symbol_connection_points": geometry,
        "placement_connection_ports": geometry,
        "wall_device_snap_origins": geometry,
        "symbol_layer": clipboard,
        "symbol_annotation_lines": clipboard,
        "symbol_clipboard_payload": clipboard,
        "placements_from_clipboard_payload": clipboard,
        "normalize_associations": associations,
        "normalize_light_outputs": associations,
        "normalize_pl_box_orientation": pl_box_model,
        "normalize_pl_outlet_type": pl_box_model,
    }

    for name, module in expected.items():
        assert getattr(core, name) is getattr(module, name)


def test_custom_combo_registry_and_geometry_work_without_core_facade():
    code = registry.make_custom_combo_code(
        ["switch_1", "switch_2way"],
        "socket_earth",
    )

    assert registry.parse_custom_combo_symbol(code) == (
        ["switch_1", "switch_2way"],
        "socket_earth",
    )
    assert registry.combo_modules(code) == ["switch_1", "switch_2way"]
    assert geometry.symbol_primitives(code, 100.0)
    assert geometry.symbol_connection_points(code, 100.0)


def test_symbol_clipboard_keeps_physical_data_but_clears_relations():
    source = core.Placement(
        "light_connection",
        10.0,
        20.0,
        label="Lampe",
        associations=["b"],
        light_outputs=[{"id": "out1", "name": "Pendel", "association": "b"}],
        locked=True,
        pl_box_entries={"1": {"cable_uid": "c1"}},
        lamp_outlet_type="nordtronic_zigbee",
    )

    restored = clipboard.placement_from_clipboard_payload(
        clipboard.symbol_clipboard_payload(source)
    )

    assert restored is not None
    assert (restored.symbol, restored.x, restored.y, restored.label) == (
        "light_connection",
        10.0,
        20.0,
        "Lampe",
    )
    assert restored.associations == []
    assert restored.light_outputs == [
        {"id": "out1", "name": "Pendel", "association": ""}
    ]
    assert restored.locked is False
    assert restored.pl_box_entries == {}
    assert restored.lamp_outlet_type == "nordtronic_zigbee"
