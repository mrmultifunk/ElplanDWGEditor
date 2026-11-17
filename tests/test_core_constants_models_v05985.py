from __future__ import annotations

from dataclasses import asdict

import core_logic as core
from elplan_core import constants
from elplan_core.models import (
    CADPrimitive,
    CablePlacement,
    Placement,
    RoomPlacement,
    TextPlacement,
)


def test_core_logic_reexports_moved_constants_without_copies():
    names = (
        "APP_NAME",
        "APP_VERSION",
        "CABLE_TYPES",
        "CABLE_SPEC_PRESETS",
        "CABLE_LINE_STYLES",
        "GENERATED_LAYER_COLORS",
        "SNAP_TOLERANCE_PX",
        "THEMES",
        "SYMBOL_GROUPS",
        "SYMBOLS",
    )
    for name in names:
        assert getattr(core, name) is getattr(constants, name), name


def test_core_logic_reexports_moved_model_classes():
    classes = (
        Placement,
        CablePlacement,
        TextPlacement,
        RoomPlacement,
        CADPrimitive,
    )
    for model in classes:
        assert getattr(core, model.__name__) is model
        assert model.__module__ == "elplan_core.models"


def test_moved_models_keep_defaults_and_independent_mutable_fields():
    first = Placement("socket", 10.0, 20.0)
    second = Placement("socket", 10.0, 20.0)
    cable = CablePlacement([(0.0, 0.0), (1000.0, 0.0)])

    assert first.color == constants.DEFAULT_SYMBOL_COLOR
    assert cable.layer == constants.CABLE_LAYER
    assert cable.color == constants.DEFAULT_CABLE_COLOR
    assert cable.line_style == constants.DEFAULT_CABLE_LINE_STYLE
    assert cable.cable_category == constants.DEFAULT_CABLE_CATEGORY
    assert first.uid != second.uid
    assert first.associations is not second.associations
    assert asdict(first)["pl_box_entries"] == {}
