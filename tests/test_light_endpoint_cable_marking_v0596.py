from pathlib import Path

import core_logic as core


def _light(label: str, x: float, uid: str):
    return core.Placement(symbol="light_connection", x=x, y=5, label=label, group="G99", uid=uid)


def _cable(a: str, b: str, points=None):
    cable = core.CablePlacement(points=points or [(0, 5), (10, 5)], cable_id="K12", circuit_id="G05")
    core.set_cable_symbol_connections(cable, [
        {"point_index": 0, "symbol_uid": a, "symbol_port": 0},
        {"point_index": len(cable.points) - 1, "symbol_uid": b, "symbol_port": 0},
    ])
    return cable


def test_light_to_light_marking_uses_only_outlet_labels_not_group():
    placements = [_light("UDTAG-KØKKEN", 0, "a"), _light("UDTAG-GANG", 10, "b")]
    cable = _cable("a", "b")
    assert core.cable_light_endpoint_marking(cable, placements) == "UDTAG-KØKKEN → UDTAG-GANG"
    assert "G99" not in core.cable_light_endpoint_marking(cable, placements)
    assert cable.circuit_id == "G05"
    assert cable.label == ""


def test_light_endpoint_fallback_requires_two_light_connection_endpoints():
    light = _light("PL01", 0, "a")
    socket = core.Placement(symbol="socket_ground", x=10, y=5, label="ST01", group="G03", uid="b")
    cable = _cable("a", "b")
    assert core.cable_light_endpoint_marking(cable, [light, socket]) == ""


def test_one_available_light_label_is_still_a_safe_suggestion():
    placements = [_light("PL01", 0, "a"), _light("", 10, "b")]
    cable = _cable("a", "b")
    assert core.cable_light_endpoint_marking(cable, placements) == "PL01"


def test_central_marking_workflow_uses_light_endpoint_fallback_and_keeps_apply_explicit():
    source = Path("qt_cable_marking.py").read_text(encoding="utf-8")
    block = source[source.index("    def _cable_marking_suggestions"):source.index("    def _focus_cable_for_marking")]
    assert "core.cable_light_endpoint_marking" in block
    assert 'f"Lampeudtag · {light_marking}"' in block
    assert "room_count <= 1" in block
    assert "_apply_graphical_cable_marking" not in block
