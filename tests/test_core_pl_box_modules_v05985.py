from __future__ import annotations

import core_logic as core
from elplan_core.export import pl_report
from elplan_core.pl_box import model, wago, wiring


def test_pl_box_modules_are_reexported_through_core_facade():
    expected = {
        model: (
            "pl_box_port_layout",
            "pl_outlet_profile",
            "normalize_pl_box_entries",
            "normalize_pl_field_record",
            "reconcile_pl_box_entries",
            "auto_assign_pl_box_entries",
            "pl_box_status",
            "normalize_pl_box_splices",
        ),
        wiring: (
            "cable_legs_at_symbol",
            "pl_expected_switch_connections",
            "pl_switch_requirement_status",
            "cable_conductor_preset",
            "cable_switch_conductor_usage",
            "reconcile_pl_box_wiring",
            "pl_wiring_suggestions",
        ),
        wago: (
            "pl_recommended_wago_article",
            "reconcile_pl_box_splices",
            "pl_terminal_occupancy",
            "pl_outlet_capacity_issues",
            "pl_montage_status",
            "pl_wiring_workflow_issues",
        ),
        pl_report: (
            "pl_report_wiring_rows",
            "export_pl_box_report_pdf",
        ),
    }

    for module, names in expected.items():
        for name in names:
            assert getattr(core, name) is getattr(module, name)


def test_pl_box_layers_keep_existing_terminal_and_wago_result():
    profile = model.pl_outlet_profile("lk_classic", ["a", "b"])
    assert [row["function_id"] for row in profile["terminals"]] == [
        "n",
        "l",
        "pe",
        "switch:a",
        "switch:b",
    ]

    conductors = wiring.cable_conductor_preset("5G1,5")
    assert [row["core_id"] for row in conductors] == [
        "pe",
        "blue",
        "brown",
        "black",
        "grey",
    ]
    assert wago.pl_recommended_wago_article(4, connects_to_outlet=True) == "221-415"
