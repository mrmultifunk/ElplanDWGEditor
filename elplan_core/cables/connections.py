"""Stabile symboltilslutninger langs fysiske kabelruter."""

from __future__ import annotations

from elplan_core.models import CablePlacement


def normalize_cable_symbol_connections(records, point_count: int | None = None):
    """Normalisér fysiske symboltilslutninger langs én kabelrute.

    ``point_index`` refererer til kabelpolyline-punktet, mens ``symbol_uid`` og
    ``symbol_port`` fortæller hvilket fysisk installationspunkt kablet passerer.
    Der kan være mange tilslutninger på samme kabel (sløjfning).
    """
    out=[]; seen=set()
    limit = None if point_count is None else max(0, int(point_count))
    for raw in records or []:
        if not isinstance(raw, dict):
            continue
        try:
            index=max(0,int(raw.get("point_index",0) or 0))
            port=max(0,int(raw.get("symbol_port",0) or 0))
        except (TypeError,ValueError):
            continue
        uid=str(raw.get("symbol_uid","") or "").strip()
        if not uid or (limit is not None and (limit == 0 or index >= limit)):
            continue
        key=(index,uid,port)
        if key in seen:
            continue
        seen.add(key)
        out.append({"point_index":index,"symbol_uid":uid,"symbol_port":port})
    # Et polyline-punkt kan kun være tilsluttet ét symbol ad gangen. Sidste
    # registrering vinder, og rækkefølgen følger kabelruten.
    by_index={int(row["point_index"]):row for row in out}
    return [by_index[i] for i in sorted(by_index)]


def cable_symbol_connections(cable: CablePlacement):
    """Returnér tilslutninger og migrér legacy start/slut-referencer i hukommelsen."""
    points=list(getattr(cable,"points",[]) or [])
    rows=normalize_cable_symbol_connections(getattr(cable,"symbol_connections",[]),len(points))
    if not rows and points:
        start_uid=str(getattr(cable,"start_symbol_uid","") or "").strip()
        end_uid=str(getattr(cable,"end_symbol_uid","") or "").strip()
        if start_uid:
            rows.append({"point_index":0,"symbol_uid":start_uid,"symbol_port":max(0,int(getattr(cable,"start_symbol_port",0) or 0))})
        if end_uid:
            end_index=len(points)-1
            rec={"point_index":end_index,"symbol_uid":end_uid,"symbol_port":max(0,int(getattr(cable,"end_symbol_port",0) or 0))}
            if not rows or rows[-1] != rec:
                rows.append(rec)
    return normalize_cable_symbol_connections(rows,len(points))


def set_cable_symbol_connections(cable: CablePlacement, records) -> None:
    """Gem tilslutninger og hold legacy start/slut-felter synkroniserede."""
    points=list(getattr(cable,"points",[]) or [])
    rows=normalize_cable_symbol_connections(records,len(points))
    cable.symbol_connections=rows
    cable.start_symbol_uid=""; cable.start_symbol_port=0
    cable.end_symbol_uid=""; cable.end_symbol_port=0
    if points:
        for row in rows:
            idx=int(row["point_index"])
            if idx==0:
                cable.start_symbol_uid=str(row["symbol_uid"]); cable.start_symbol_port=int(row["symbol_port"])
            if idx==len(points)-1:
                cable.end_symbol_uid=str(row["symbol_uid"]); cable.end_symbol_port=int(row["symbol_port"])


def cable_connection_at(cable: CablePlacement, point_index: int):
    index=int(point_index)
    return next((dict(r) for r in cable_symbol_connections(cable) if int(r.get("point_index",-1))==index),None)


def cable_is_physical_segment(cable: CablePlacement) -> bool:
    """True when a cable has at most two physical symbol endpoints.

    Since 0.55.0 a ``CablePlacement`` represents one real cable, not a whole
    loop-through string. Waypoints may still be unlimited, but a cable can only
    connect two installation points.
    """
    rows=cable_symbol_connections(cable)
    points=list(getattr(cable,"points",[]) or [])
    endpoints={0,max(0,len(points)-1)} if points else set()
    return len(rows)<=2 and all(int(r.get("point_index",0) or 0) in endpoints for r in rows)


def replace_cable_connection(cable: CablePlacement, point_index: int, symbol_uid: str = "", symbol_port: int = 0) -> None:
    """Tilføj, opdatér eller fjern en forbindelse ved ét rutepunkt."""
    index=int(point_index)
    rows=[dict(r) for r in cable_symbol_connections(cable) if int(r.get("point_index",-1))!=index]
    uid=str(symbol_uid or "").strip()
    if uid:
        rows.append({"point_index":index,"symbol_uid":uid,"symbol_port":max(0,int(symbol_port or 0))})
    set_cable_symbol_connections(cable,rows)


def shift_cable_connection_indices(cable: CablePlacement, start_index: int, delta: int) -> None:
    """Forskyd forbindelsesindeks efter indsættelse/fjernelse af geometripunkter."""
    if not delta:return
    source=normalize_cable_symbol_connections(getattr(cable,"symbol_connections",[]),None)
    if not source:
        source=cable_symbol_connections(cable)
    rows=[]
    for row in source:
        rec=dict(row); idx=int(rec["point_index"])
        if idx>=int(start_index): idx+=int(delta)
        if idx>=0:
            rec["point_index"]=idx; rows.append(rec)
    set_cable_symbol_connections(cable,rows)
