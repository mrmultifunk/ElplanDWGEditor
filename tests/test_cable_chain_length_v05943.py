import math

import core_logic as core
from project_model import APP_VERSION


def _cable(uid, chain, length):
    return core.CablePlacement(points=[(0.0, 0.0), (float(length), 0.0)], uid=uid, route_chain_uid=chain)


def test_version_v05945():
    assert APP_VERSION == core.APP_VERSION == "0.59.83"


def test_route_chain_length_sums_only_same_drawn_pull():
    a = _cable("a", "chain-1", 3)
    b = _cable("b", "chain-1", 4)
    c = _cable("c", "chain-2", 20)
    members = core.cable_route_chain_members(a, [a, b, c])
    assert [row.uid for row in members] == ["a", "b"]
    assert math.isclose(core.cable_route_chain_length_metres(a, [a, b, c], 1.0), 7.0)
    assert math.isclose(core.cable_route_chain_estimated_length_metres(a, [a, b, c], 1.0, 10.0), 7.7)


def test_legacy_blank_chain_does_not_join_unrelated_cables():
    a = _cable("a", "", 3)
    b = _cable("b", "", 4)
    assert [row.uid for row in core.cable_route_chain_members(a, [a, b])] == ["a"]
    assert math.isclose(core.cable_route_chain_length_metres(a, [a, b], 1.0), 3.0)


def test_cable_panel_contains_piece_and_complete_pull_labels():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/"qt_cable_panel.py").read_text(encoding="utf-8")
    app=(Path(__file__).resolve().parents[1]/"qt_app.py").read_text(encoding="utf-8")
    assert "Markeret kabelstykke" in source
    assert "Hele kabeltrækket" in source
    assert "cable_route_chain_length_metres" in app
