from pathlib import Path

import core_logic as core
from project_model import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_version_0521():
    assert APP_VERSION == core.APP_VERSION == "0.59.82"


def test_attach_light_to_existing_cable_endpoint_is_one_physical_leg():
    cable = core.CablePlacement(
        points=[(0.0, 0.0), (100.0, 0.0)],
        cable_id="K01",
        cable_spec="5G1,5",
        orthogonal=True,
    )
    result = core.attach_symbol_to_existing_cable(cable, "pl01", 0, (0.0, 20.0), segment_index=0)
    assert result["status"] == "attached"
    assert result["endpoint"] is True
    assert result["point_index"] == 0
    assert cable.points == [(0.0, 20.0), (0.0, 0.0), (100.0, 0.0)]
    assert core.cable_symbol_connections(cable) == [
        {"point_index": 0, "symbol_uid": "pl01", "symbol_port": 0}
    ]


def test_attach_light_to_middle_of_existing_orthogonal_route_creates_loopthrough_anchor():
    cable = core.CablePlacement(
        points=[(0.0, 0.0), (100.0, 0.0)],
        cable_id="K02",
        orthogonal=True,
    )
    result = core.attach_symbol_to_existing_cable(cable, "pl02", 0, (50.0, 20.0), segment_index=0)
    assert result["status"] == "attached"
    assert result.get("endpoint") is not True
    assert cable.points == [
        (0.0, 0.0), (50.0, 0.0), (50.0, 20.0), (100.0, 20.0), (100.0, 0.0)
    ]
    assert all(
        abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
        for a, b in zip(cable.points, cable.points[1:])
    )
    assert core.cable_symbol_connections(cable)[0]["point_index"] == 2


def test_existing_connections_are_remapped_when_new_light_is_inserted():
    cable = core.CablePlacement(
        points=[(0.0, 0.0), (100.0, 0.0)],
        orthogonal=True,
        symbol_connections=[{"point_index": 1, "symbol_uid": "existing", "symbol_port": 0}],
    )
    core.set_cable_symbol_connections(cable, cable.symbol_connections)
    result = core.attach_symbol_to_existing_cable(cable, "pl03", 0, (50.0, 0.0), segment_index=0)
    assert result["status"] == "attached"
    assert cable.points == [(0.0, 0.0), (50.0, 0.0), (100.0, 0.0)]
    assert core.cable_symbol_connections(cable) == [
        {"point_index": 1, "symbol_uid": "pl03", "symbol_port": 0},
        {"point_index": 2, "symbol_uid": "existing", "symbol_port": 0},
    ]


def test_free_diagonal_route_can_be_pulled_through_existing_light():
    cable = core.CablePlacement(points=[(0.0, 0.0), (100.0, 0.0)], orthogonal=False)
    result = core.attach_symbol_to_existing_cable(cable, "pl04", 0, (50.0, 25.0), segment_index=0)
    assert result["status"] == "attached"
    assert cable.points == [(0.0, 0.0), (50.0, 25.0), (100.0, 0.0)]


def test_gui_exposes_intuitive_attach_button_context_menu_and_click_mode():
    app = (ROOT / "qt_app.py").read_text(encoding="utf-8")
    attach = (ROOT / "qt_cable_attach.py").read_text(encoding="utf-8")
    graphics = (ROOT / "qt_graphics.py").read_text(encoding="utf-8")
    assert 'QPushButton("Tilknyt eksisterende kabel…")' in app
    assert 'from qt_cable_attach import CableAttachMixin' in app
    assert 'CableAttachMixin' in app and 'class MainWindow(' in app
    assert 'def start_cable_attach_for_selection' in attach
    assert 'def _start_cable_attach_mode' in attach
    assert 'def _handle_cable_item_click' in attach
    assert 'if len(replacements)==1 and bool(result.get("endpoint"))' in attach
    assert 'Kablet forbliver ét fysisk kabel' in attach
    assert 'core.split_cable_into_physical_segments(temp)' in attach
    assert 'Tilknyt til eksisterende kabel…' in attach
    assert 'item.click_handler = self._handle_cable_item_click' in app
    assert 'self.click_handler = None' in graphics
    assert 'def contextMenuEvent(self, event) -> None:' in graphics
