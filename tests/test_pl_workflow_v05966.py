from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def _leg(spec="5G1,5"):
    return {
        "cable_uid":"c1","point_index":0,"leg":"endpoint","leg_caption":"Ende",
        "cable_id":"K1","cable_display":"K1 · AFBRYDER → PL","cable_spec":spec,
    }


def _key(core_id):
    return ("c1",0,"endpoint",core_id)


def test_version_05966():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"


def test_suggestions_are_preview_only_and_keep_brown_unchecked():
    legs=[_leg()]
    wiring=core.reconcile_pl_box_wiring([],legs)
    original=[dict(row) for row in wiring]
    suggestions=core.pl_wiring_suggestions(legs,wiring)
    by_key={tuple(row["conductor_key"]):row for row in suggestions}

    assert by_key[_key("pe")]["function_id"] == "pe"
    assert by_key[_key("pe")]["checked"] is True
    assert by_key[_key("blue")]["function_id"] == "n"
    assert by_key[_key("blue")]["checked"] is True
    assert by_key[_key("brown")]["function_id"] == "l"
    assert by_key[_key("brown")]["confidence"] == "review"
    assert by_key[_key("brown")]["checked"] is False
    assert wiring == original


def test_external_allocation_is_the_first_safe_suggestion():
    legs=[_leg()]
    wiring=core.reconcile_pl_box_wiring([],legs)
    external={
        _key("black"):{
            "functions":["switch:b"],"conflict":False,
            "usages":[{"placement":"G12 · PL KØKKEN","function":"switch:b"}],
        }
    }
    suggestions=core.pl_wiring_suggestions(legs,wiring,external_allocations=external)
    black=next(row for row in suggestions if tuple(row["conductor_key"])==_key("black"))
    assert black["function_id"] == "switch:b"
    assert black["kind"] == "external"
    assert black["checked"] is True


def test_missing_direct_switch_issue_focuses_a_free_control_core():
    legs=[_leg()]
    wiring=core.reconcile_pl_box_wiring([],legs)
    requirement={
        "function_id":"switch:a","association":"a","direct":True,"required":True,
        "cable_uid":"c1","point_index":0,"leg":"endpoint","cable_display":"K1",
    }
    issues=core.pl_wiring_workflow_issues(legs,wiring,[requirement],[],"generic",["a"],{})
    missing=next(row for row in issues if row["kind"]=="requirement_missing")
    assert missing["severity"] == "error"
    assert tuple(missing["conductor_key"]) == _key("black")
    assert missing["function_id"] == "switch:a"

    suggestions=core.pl_wiring_suggestions(legs,wiring,[requirement],{})
    switch=next(row for row in suggestions if row["function_id"]=="switch:a")
    assert tuple(switch["conductor_key"]) == _key("black")
    assert switch["checked"] is True


def test_external_conflict_becomes_clickable_error_not_automatic_suggestion():
    legs=[_leg()]
    wiring=core.reconcile_pl_box_wiring([],legs)
    external={_key("grey"):{"functions":["switch:a","switch:b"],"conflict":True,"usages":[]}}
    issues=core.pl_wiring_workflow_issues(legs,wiring,external_allocations=external)
    conflict=next(row for row in issues if row["kind"]=="external_conflict")
    assert conflict["severity"] == "error"
    assert tuple(conflict["conductor_key"]) == _key("grey")
    assert not any(tuple(row["conductor_key"])==_key("grey") for row in core.pl_wiring_suggestions(legs,wiring,external_allocations=external))


def test_qt_has_compact_problem_navigation_preview_and_cached_hover_state():
    source=Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "Næste uløste" in source and 'QKeySequence("F8")' in source
    assert "Forslag til lederfordeling · forhåndsvisning" in source
    assert "Sikre forslag er valgt på forhånd" in source
    assert "self._state_cache" in source and "_rebuild_state_cache" in source
    assert "Allokeret ved anden kabelende" in source

