"""Kabel- og kabelkædelængder i tegneenheder og meter."""

from __future__ import annotations

import math

from elplan_core.cables.geometry import polyline_length
from elplan_core.cables.sections import cable_spec_section_at_segment
from elplan_core.models import CablePlacement


def cable_route_length(cable: CablePlacement) -> float:
    return polyline_length(getattr(cable, "points", []))


def cable_length_metres(cable: CablePlacement, metres_per_unit: float | None) -> float | None:
    if metres_per_unit is None or float(metres_per_unit) <= 0:
        return None
    return cable_route_length(cable) * float(metres_per_unit)


def cable_length_by_spec_metres(cable: CablePlacement, metres_per_unit: float | None) -> dict[str,float] | None:
    """Fordel kabelrutelængden på de effektive kabeltyper langs ruten.

    Hvert polyline-segment arver kabeltypen fra det fysiske afsnit mellem to
    nabotilslutninger. Segmenter uden en sådan afgrænsning bruger kabellets
    globale ``cable_spec``. Summen er derfor identisk med ``cable_length_metres``.
    """
    if metres_per_unit is None or float(metres_per_unit) <= 0:
        return None
    pts=[(float(x),float(y)) for x,y in (getattr(cable,"points",[]) or [])]
    factor=float(metres_per_unit)
    default=str(getattr(cable,"cable_spec","") or "").strip() or "—"
    totals: dict[str,float]={}
    for index,(a,b) in enumerate(zip(pts,pts[1:])):
        section=cable_spec_section_at_segment(cable,index)
        spec=str((section or {}).get("cable_spec") or default).strip() or "—"
        length=math.hypot(b[0]-a[0],b[1]-a[1])*factor
        totals[spec]=totals.get(spec,0.0)+length
    return totals


def cable_estimated_length_metres(cable: CablePlacement, metres_per_unit: float | None, reserve_percent: float = 0.0) -> float | None:
    base = cable_length_metres(cable, metres_per_unit)
    if base is None:
        return None
    return base * (1.0 + max(0.0, float(reserve_percent)) / 100.0)


def cable_route_chain_key(cable: CablePlacement) -> str:
    """Stable identity for one drawn cable pull/string.

    ``route_chain_uid`` links the physical cable pieces that were created in
    the same drawing gesture. Legacy/single cables fall back to their own UID
    so blank chain ids never accidentally join unrelated cables.
    """
    return str(getattr(cable, "route_chain_uid", "") or getattr(cable, "uid", "") or "").strip()


def cable_route_chain_members(cable: CablePlacement, cables) -> list[CablePlacement]:
    """Return all physical cable pieces belonging to ``cable``'s cable pull."""
    key = cable_route_chain_key(cable)
    if not key:
        return [cable]
    members = [row for row in (cables or []) if cable_route_chain_key(row) == key]
    if not members:
        return [cable]
    return members


def cable_route_chain_length_metres(cable: CablePlacement, cables, metres_per_unit: float | None) -> float | None:
    """Total route length for the complete cable pull containing ``cable``."""
    if metres_per_unit is None:
        return None
    total = 0.0
    for member in cable_route_chain_members(cable, cables):
        value = cable_length_metres(member, metres_per_unit)
        if value is None:
            return None
        total += float(value)
    return total


def cable_route_chain_estimated_length_metres(cable: CablePlacement, cables, metres_per_unit: float | None, reserve_percent: float = 0.0) -> float | None:
    """Total cable-pull length including the project's reserve percentage."""
    base = cable_route_chain_length_metres(cable, cables, metres_per_unit)
    if base is None:
        return None
    return base * (1.0 + max(0.0, float(reserve_percent)) / 100.0)
