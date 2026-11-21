from __future__ import annotations

"""Read-only cable-route overview derived from the physical 0.55 cable model.

The route overview is intentionally *not* persisted.  It is rebuilt from the
physical CablePlacement objects and their symbol endpoints so there is one
source of truth for drawing, PL-box wiring, BOM and route documentation.
"""

from dataclasses import dataclass, field
from typing import Iterable

import core_logic as core


BOARD_SYMBOLS = {"distribution_board", "group_board"}
UNGROUPED_CIRCUIT = "Uden gruppe/kreds"


@dataclass(frozen=True)
class CableRouteNode:
    uid: str
    caption: str
    detail_caption: str
    symbol: str = ""
    free_end: bool = False


@dataclass(frozen=True)
class CableRouteEdge:
    cable_uid: str
    cable_id: str
    circuit_id: str
    cable_spec: str
    node_a: str
    node_b: str
    length_m: float | None = None


@dataclass
class CableRouteTreeRow:
    node_uid: str
    node_caption: str
    node_detail_caption: str
    cable_uid: str = ""
    cable_id: str = ""
    cable_spec: str = ""
    length_m: float | None = None
    path_cable_uids: list[str] = field(default_factory=list)
    depth: int = 0
    cycle: bool = False
    cycle_target_caption: str = ""
    children: list["CableRouteTreeRow"] = field(default_factory=list)


@dataclass(frozen=True)
class CableRoutePath:
    circuit_id: str
    component_index: int
    node_uids: tuple[str, ...]
    node_captions: tuple[str, ...]
    cable_uids: tuple[str, ...]
    cable_ids: tuple[str, ...]
    cable_specs: tuple[str, ...]
    length_m: float | None
    cycle: bool = False

    @property
    def route_text(self) -> str:
        text = " → ".join(self.node_captions)
        return text + (" ↻" if self.cycle else "")

    @property
    def cable_text(self) -> str:
        return ", ".join(x for x in self.cable_ids if x)

    @property
    def spec_text(self) -> str:
        seen: list[str] = []
        for spec in self.cable_specs:
            value = str(spec or "").strip()
            if value and value not in seen:
                seen.append(value)
        return " / ".join(seen)


@dataclass
class CableRouteComponent:
    index: int
    root_uid: str
    root_caption: str
    cable_uids: list[str]
    tree: CableRouteTreeRow
    paths: list[CableRoutePath]


@dataclass
class CableRouteGroup:
    circuit_id: str
    cable_uids: list[str]
    components: list[CableRouteComponent]
    paths: list[CableRoutePath]
    total_length_m: float | None

    @property
    def cable_count(self) -> int:
        return len(self.cable_uids)



def _clean(value) -> str:
    return str(value or "").strip()



def _placement_caption(placement) -> tuple[str, str]:
    """Return a compact route caption plus a fuller hover/detail caption."""
    symbol = _clean(getattr(placement, "symbol", ""))
    label = _clean(getattr(placement, "label", ""))
    group = _clean(getattr(placement, "group", ""))
    display = core.symbol_display_name(symbol) if symbol else "Symbol"

    # The free marking is normally the most useful installation-point name
    # (PL01/ST04 etc.). Fall back to group and finally the symbol type.
    compact = label or group or display
    ident = core.placement_identification_caption(placement)
    detail = display
    if ident and ident != "Lampested" and ident != display:
        detail = f"{display} · {ident}"
    return compact, detail



def _free_node(cable_uid: str, cable_id: str, side: str) -> CableRouteNode:
    suffix = "A" if side == "a" else "B"
    cable_name = _clean(cable_id) or "kabel"
    return CableRouteNode(
        uid=f"__free__:{cable_uid}:{side}",
        caption="Fri ende",
        detail_caption=f"Fri ende · {cable_name} · ende {suffix}",
        free_end=True,
    )



def _edge_length(cable, metres_per_unit: float | None) -> float | None:
    if metres_per_unit is None:
        return None
    try:
        factor = float(metres_per_unit)
    except (TypeError, ValueError):
        return None
    if factor <= 0:
        return None
    return core.cable_length_metres(cable, factor)



def _physical_endpoints(cable) -> tuple[dict | None, dict | None]:
    """Return the symbol records connected to polyline start/end."""
    points = list(getattr(cable, "points", []) or [])
    if not points:
        return None, None
    by_index = {int(r.get("point_index", -1)): r for r in core.cable_symbol_connections(cable)}
    return by_index.get(0), by_index.get(len(points) - 1)



def _root_sort_key(node: CableRouteNode, degree: int) -> tuple:
    board_rank = 0 if node.symbol in BOARD_SYMBOLS else 1
    free_rank = 1 if node.free_end else 0
    leaf_rank = 0 if degree <= 1 else 1
    return (board_rank, free_rank, leaf_rank, node.caption.casefold(), node.uid)



def _connected_components(node_ids: Iterable[str], adjacency: dict[str, list[tuple[int, str]]]) -> list[set[str]]:
    remaining = set(node_ids)
    result: list[set[str]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        comp: set[str] = set()
        while stack:
            uid = stack.pop()
            if uid in comp:
                continue
            comp.add(uid)
            remaining.discard(uid)
            for _edge_idx, other in adjacency.get(uid, []):
                if other not in comp:
                    stack.append(other)
        result.append(comp)
    return result



def _build_component(
    circuit_id: str,
    component_index: int,
    component_nodes: set[str],
    nodes: dict[str, CableRouteNode],
    edges: list[CableRouteEdge],
    adjacency: dict[str, list[tuple[int, str]]],
) -> CableRouteComponent:
    root_uid = min(
        component_nodes,
        key=lambda uid: _root_sort_key(nodes[uid], len(adjacency.get(uid, []))),
    )
    root_node = nodes[root_uid]
    root_row = CableRouteTreeRow(
        node_uid=root_uid,
        node_caption=root_node.caption,
        node_detail_caption=root_node.detail_caption,
        depth=0,
    )

    used_edges: set[int] = set()
    visited_nodes: set[str] = {root_uid}
    component_edge_indices = {
        idx for idx, edge in enumerate(edges)
        if edge.node_a in component_nodes and edge.node_b in component_nodes
    }

    def edge_key(pair: tuple[int, str]) -> tuple:
        idx, other = pair
        edge = edges[idx]
        return (
            1 if nodes[other].free_end else 0,
            nodes[other].caption.casefold(),
            edge.cable_id.casefold(),
            edge.cable_uid,
        )

    def walk(parent_row: CableRouteTreeRow, node_uid: str, path_uids: list[str]) -> None:
        for edge_idx, other_uid in sorted(adjacency.get(node_uid, []), key=edge_key):
            if edge_idx not in component_edge_indices or edge_idx in used_edges:
                continue
            used_edges.add(edge_idx)
            edge = edges[edge_idx]
            other = nodes[other_uid]
            next_path = path_uids + [edge.cable_uid]
            if other_uid in visited_nodes:
                parent_row.children.append(CableRouteTreeRow(
                    node_uid=other_uid,
                    node_caption=f"{other.caption} ↻",
                    node_detail_caption=other.detail_caption,
                    cable_uid=edge.cable_uid,
                    cable_id=edge.cable_id,
                    cable_spec=edge.cable_spec,
                    length_m=edge.length_m,
                    path_cable_uids=next_path,
                    depth=parent_row.depth + 1,
                    cycle=True,
                    cycle_target_caption=other.caption,
                ))
                continue
            visited_nodes.add(other_uid)
            child = CableRouteTreeRow(
                node_uid=other_uid,
                node_caption=other.caption,
                node_detail_caption=other.detail_caption,
                cable_uid=edge.cable_uid,
                cable_id=edge.cable_id,
                cable_spec=edge.cable_spec,
                length_m=edge.length_m,
                path_cable_uids=next_path,
                depth=parent_row.depth + 1,
            )
            parent_row.children.append(child)
            walk(child, other_uid, next_path)

    walk(root_row, root_uid, [])

    # In a multigraph every edge should be visited from the chosen root, but keep
    # a defensive fallback so a malformed/self-loop cable is still visible.
    for edge_idx in sorted(component_edge_indices - used_edges):
        edge = edges[edge_idx]
        target_uid = edge.node_b if edge.node_a == root_uid else edge.node_a
        target = nodes[target_uid]
        root_row.children.append(CableRouteTreeRow(
            node_uid=target_uid,
            node_caption=f"{target.caption} ↻",
            node_detail_caption=target.detail_caption,
            cable_uid=edge.cable_uid,
            cable_id=edge.cable_id,
            cable_spec=edge.cable_spec,
            length_m=edge.length_m,
            path_cable_uids=[edge.cable_uid],
            depth=1,
            cycle=True,
            cycle_target_caption=target.caption,
        ))
        used_edges.add(edge_idx)

    paths: list[CableRoutePath] = []

    def collect(row: CableRouteTreeRow, node_uids: list[str], captions: list[str], cable_indices: list[int]) -> None:
        if row is root_row:
            current_nodes = [root_uid]
            current_captions = [root_node.caption]
            current_edges: list[int] = []
        else:
            current_nodes = node_uids + [row.node_uid]
            # A cycle row points back to an already visited node; show its normal
            # caption and mark the path with ↻ rather than duplicating the glyph.
            current_captions = captions + [nodes[row.node_uid].caption]
            edge_idx = next((i for i, e in enumerate(edges) if e.cable_uid == row.cable_uid), -1)
            current_edges = cable_indices + ([edge_idx] if edge_idx >= 0 else [])

        if row.cycle or not row.children:
            route_edges = [edges[i] for i in current_edges if i >= 0]
            length_known = all(e.length_m is not None for e in route_edges)
            length = sum(float(e.length_m or 0.0) for e in route_edges) if length_known else None
            paths.append(CableRoutePath(
                circuit_id=circuit_id,
                component_index=component_index,
                node_uids=tuple(current_nodes),
                node_captions=tuple(current_captions),
                cable_uids=tuple(e.cable_uid for e in route_edges),
                cable_ids=tuple(e.cable_id for e in route_edges),
                cable_specs=tuple(e.cable_spec for e in route_edges),
                length_m=length,
                cycle=row.cycle,
            ))
            return
        for child in row.children:
            collect(child, current_nodes, current_captions, current_edges)

    collect(root_row, [], [], [])

    cable_uids = [edges[i].cable_uid for i in sorted(component_edge_indices)]
    return CableRouteComponent(
        index=component_index,
        root_uid=root_uid,
        root_caption=root_node.caption,
        cable_uids=cable_uids,
        tree=root_row,
        paths=paths,
    )



def build_cable_route_groups(placements, cables, metres_per_unit: float | None = None) -> list[CableRouteGroup]:
    """Build circuit/group route trees from physical cable segments.

    The function accepts the application's plain dataclasses and has no Qt
    dependency, making the same derived network suitable for future reports.
    """
    placement_lookup = {_clean(getattr(p, "uid", "")): p for p in (placements or []) if _clean(getattr(p, "uid", ""))}
    grouped: dict[str, list] = {}
    for cable in cables or []:
        circuit = _clean(getattr(cable, "circuit_id", "")) or UNGROUPED_CIRCUIT
        grouped.setdefault(circuit, []).append(cable)

    groups: list[CableRouteGroup] = []
    for circuit_id in sorted(grouped, key=lambda x: (x == UNGROUPED_CIRCUIT, x.casefold())):
        circuit_cables = grouped[circuit_id]
        nodes: dict[str, CableRouteNode] = {}
        edges: list[CableRouteEdge] = []
        adjacency: dict[str, list[tuple[int, str]]] = {}

        def node_for_record(record: dict | None, cable, side: str) -> CableRouteNode:
            if record:
                uid = _clean(record.get("symbol_uid"))
                placement = placement_lookup.get(uid)
                if placement is not None:
                    compact, detail = _placement_caption(placement)
                    node = CableRouteNode(uid=uid, caption=compact, detail_caption=detail, symbol=_clean(getattr(placement, "symbol", "")))
                    nodes.setdefault(uid, node)
                    return nodes[uid]
                node = CableRouteNode(uid=uid, caption="Ukendt symbol", detail_caption=f"Ukendt symbol · {uid[:8]}")
                nodes.setdefault(uid, node)
                return nodes[uid]
            node = _free_node(_clean(getattr(cable, "uid", "")), _clean(getattr(cable, "cable_id", "")), side)
            nodes[node.uid] = node
            return node

        for cable in circuit_cables:
            cable_uid = _clean(getattr(cable, "uid", ""))
            if not cable_uid:
                continue
            rec_a, rec_b = _physical_endpoints(cable)
            a = node_for_record(rec_a, cable, "a")
            b = node_for_record(rec_b, cable, "b")
            specs = core.cable_effective_specs(cable)
            spec = " / ".join(specs) if specs else _clean(getattr(cable, "cable_spec", ""))
            edge = CableRouteEdge(
                cable_uid=cable_uid,
                cable_id=_clean(getattr(cable, "cable_id", "")) or "Kabel",
                circuit_id=circuit_id,
                cable_spec=spec,
                node_a=a.uid,
                node_b=b.uid,
                length_m=_edge_length(cable, metres_per_unit),
            )
            edge_idx = len(edges)
            edges.append(edge)
            adjacency.setdefault(a.uid, []).append((edge_idx, b.uid))
            adjacency.setdefault(b.uid, []).append((edge_idx, a.uid))

        if not edges:
            continue

        components: list[CableRouteComponent] = []
        for component_index, component_nodes in enumerate(_connected_components(nodes.keys(), adjacency), start=1):
            components.append(_build_component(circuit_id, component_index, component_nodes, nodes, edges, adjacency))

        cable_uids = [edge.cable_uid for edge in edges]
        known_lengths = [edge.length_m for edge in edges]
        total_length = sum(float(x or 0.0) for x in known_lengths) if all(x is not None for x in known_lengths) else None
        groups.append(CableRouteGroup(
            circuit_id=circuit_id,
            cable_uids=cable_uids,
            components=components,
            paths=[path for component in components for path in component.paths],
            total_length_m=total_length,
        ))
    return groups



def cable_route_plain_text(groups: Iterable[CableRouteGroup]) -> str:
    """Compact copy/print friendly representation, one root-to-leaf path per line."""
    lines: list[str] = []
    for group in groups:
        if not group.paths:
            lines.append(f"{group.circuit_id}: —")
            continue
        for path in group.paths:
            prefix = f"{group.circuit_id}: "
            suffix = ""
            if path.cable_text:
                suffix += f"  [{path.cable_text}]"
            if path.length_m is not None:
                suffix += f"  {path.length_m:.1f} m"
            lines.append(prefix + path.route_text + suffix)
    return "\n".join(lines)
