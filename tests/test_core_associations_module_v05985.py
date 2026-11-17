from __future__ import annotations

import core_logic as core
from elplan_core import associations
from elplan_core.models import Placement
from elplan_core.symbols.registry import make_custom_combo_code


def test_association_module_is_reexported_through_core_facade():
    names = (
        "association_role",
        "association_capacity",
        "association_channel_bases",
        "association_module_layout",
        "association_channel_records",
        "light_output_records",
        "light_output_associations",
        "sync_light_outputs",
        "set_light_output_association",
        "light_can_share_switch_group",
        "set_lights_shared_association",
        "normalize_association_channels",
        "association_channel_letters",
        "sync_association_channels",
        "set_association_channel",
        "association_display",
        "next_association_letter",
        "association_world_point",
    )

    for name in names:
        assert getattr(core, name) is getattr(associations, name)


def test_custom_combo_channels_keep_physical_module_order():
    symbol = make_custom_combo_code(
        ["switch_1", "switch_crown", "switch_2way"],
        "socket",
    )
    placement = Placement(symbol, 100.0, 200.0)

    assert associations.association_channel_bases(symbol) == [
        "switch_1",
        "switch_crown",
        "switch_crown",
        "switch_2way",
    ]
    associations.sync_association_channels(placement, ["c", "a", "d", "b"])

    assert placement.association_channels == ["c", "a", "d", "b"]
    assert placement.associations == ["a", "b", "c", "d"]
    assert associations.association_display(placement) == "A1:c · A2:a, d · A3:b"


def test_shared_light_relation_updates_only_unambiguous_light_points():
    first = Placement("light_fixture", 0.0, 0.0)
    second = Placement(
        "light_connection",
        10.0,
        0.0,
        light_outputs=[{"id": "out1", "name": "Pendel", "association": ""}],
    )
    ambiguous = Placement(
        "light_connection",
        20.0,
        0.0,
        light_outputs=[
            {"id": "out1", "name": "Pendel", "association": ""},
            {"id": "out2", "name": "Spots", "association": ""},
        ],
    )

    assert associations.set_lights_shared_association(
        [first, second, ambiguous],
        "f",
    ) == 2
    assert associations.light_output_associations(first) == ["f"]
    assert associations.light_output_associations(second) == ["f"]
    assert associations.light_output_associations(ambiguous) == []
