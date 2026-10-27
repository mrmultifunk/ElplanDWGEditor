from pathlib import Path

import core_logic as core
from cable_routes import UNGROUPED_CIRCUIT, build_cable_route_groups, cable_route_plain_text


def placement(uid, symbol, label="", group=""):
    return core.Placement(symbol=symbol, x=0, y=0, uid=uid, label=label, group=group)


def cable(uid, cable_id, a, b, *, circuit="G05", spec="3G1,5", length=10.0):
    c = core.CablePlacement(
        points=[(0.0, 0.0), (length, 0.0)],
        uid=uid,
        cable_id=cable_id,
        cable_spec=spec,
        circuit_id=circuit,
    )
    rows = []
    if a:
        rows.append({"point_index": 0, "symbol_uid": a, "symbol_port": 0})
    if b:
        rows.append({"point_index": 1, "symbol_uid": b, "symbol_port": 0})
    core.set_cable_symbol_connections(c, rows)
    return c


def test_linear_physical_cables_become_one_readable_route():
    placements = [
        placement("board", "group_board", "Tavle"),
        placement("p1", "light_connection", "PL01"),
        placement("p2", "light_connection", "PL02"),
        placement("p3", "light_connection", "PL03"),
    ]
    cables = [
        cable("c1", "K01", "board", "p1"),
        cable("c2", "K02", "p1", "p2"),
        cable("c3", "K03", "p2", "p3", spec="5G1,5"),
    ]
    groups = build_cable_route_groups(placements, cables, metres_per_unit=0.1)
    assert len(groups) == 1
    group = groups[0]
    assert group.circuit_id == "G05"
    assert group.cable_count == 3
    assert len(group.paths) == 1
    path = group.paths[0]
    assert path.route_text == "Tavle → PL01 → PL02 → PL03"
    assert path.cable_ids == ("K01", "K02", "K03")
    assert path.spec_text == "3G1,5 / 5G1,5"
    assert path.length_m == 3.0
    assert "G05: Tavle → PL01 → PL02 → PL03" in cable_route_plain_text(groups)


def test_branch_creates_one_compact_route_per_leaf_without_duplicate_cable_objects():
    placements = [
        placement("board", "distribution_board", "Tavle"),
        placement("p1", "light_connection", "PL01"),
        placement("p2", "light_connection", "PL02"),
        placement("p3", "light_connection", "PL03"),
    ]
    cables = [
        cable("c1", "K01", "board", "p1"),
        cable("c2", "K02", "p1", "p2"),
        cable("c3", "K03", "p1", "p3"),
    ]
    group = build_cable_route_groups(placements, cables)[0]
    assert {p.route_text for p in group.paths} == {
        "Tavle → PL01 → PL02",
        "Tavle → PL01 → PL03",
    }
    assert group.cable_uids == ["c1", "c2", "c3"]


def test_group_board_is_preferred_as_root_even_if_other_caption_sorts_first():
    placements = [
        placement("board", "group_board", "Z-Tavle"),
        placement("p1", "light_connection", "A-PL"),
    ]
    group = build_cable_route_groups(placements, [cable("c1", "K01", "p1", "board")])[0]
    assert group.components[0].root_uid == "board"
    assert group.paths[0].route_text == "Z-Tavle → A-PL"


def test_free_endpoint_is_kept_visible_in_route_list():
    placements = [placement("p1", "light_connection", "PL01")]
    groups = build_cable_route_groups(placements, [cable("c1", "K01", "p1", None, circuit="")])
    assert groups[0].circuit_id == UNGROUPED_CIRCUIT
    assert groups[0].paths[0].route_text == "PL01 → Fri ende"


def test_disconnected_cables_in_same_circuit_are_separate_components():
    placements = [
        placement("a", "light_connection", "PL01"), placement("b", "light_connection", "PL02"),
        placement("c", "light_connection", "PL10"), placement("d", "light_connection", "PL11"),
    ]
    group = build_cable_route_groups(placements, [
        cable("c1", "K01", "a", "b"), cable("c2", "K02", "c", "d")
    ])[0]
    assert len(group.components) == 2
    assert len(group.paths) == 2


def test_cycle_is_finite_and_every_cable_is_represented():
    placements = [
        placement("board", "group_board", "Tavle"),
        placement("a", "light_connection", "PL01"),
        placement("b", "light_connection", "PL02"),
    ]
    group = build_cable_route_groups(placements, [
        cable("c1", "K01", "board", "a"),
        cable("c2", "K02", "a", "b"),
        cable("c3", "K03", "b", "board"),
    ])[0]
    assert group.cable_count == 3
    assert any(path.cycle for path in group.paths)
    represented = {uid for path in group.paths for uid in path.cable_uids}
    assert represented == {"c1", "c2", "c3"}


def test_qt_main_window_exposes_modeless_cable_route_overview():
    source = Path(__file__).resolve().parents[1].joinpath("qt_app.py").read_text(encoding="utf-8")
    assert 'QAction("Kabeltræk / ruteforløb…"' in source
    assert "tools_menu.addAction(self.act_cable_routes)" in source
    assert "def show_cable_routes_overview" in source
    assert "from qt_cable_routes import CableRoutesDialog" in source
    assert "highlight_callback=self._highlight_cable_route_uids" in source
