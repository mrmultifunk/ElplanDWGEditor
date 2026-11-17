"""Stabile kabeltilslutninger og sektionsopslag.

De små grundfunktioner ligger her som forudsætning for rumfordelt kabellængde.
Den resterende sektionslogik flyttes hertil i fase 2.4.
"""

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


def normalize_cable_spec_section_overrides(records, default_spec: str | None = None):
    """Normalisér lokale kabeltype-overrides mellem fysiske tilslutninger.

    Posterne bruger samme stabile, retningsløse A/B-identitet som lokal
    ruteføring. Hvis ``default_spec`` gives, fjernes overrides der er identiske
    med kabellets globale kabeltype, så projektfilen forbliver kompakt.
    """
    out=[]; by_key={}
    default=str(default_spec or "").strip() if default_spec is not None else None
    for raw in records or []:
        if not isinstance(raw,dict):
            continue
        a_uid=str(raw.get("a_symbol_uid",raw.get("from_symbol_uid","")) or "").strip()
        b_uid=str(raw.get("b_symbol_uid",raw.get("to_symbol_uid","")) or "").strip()
        if not a_uid or not b_uid or a_uid==b_uid:
            continue
        try:
            a_port=max(0,int(raw.get("a_symbol_port",raw.get("from_symbol_port",0)) or 0))
            b_port=max(0,int(raw.get("b_symbol_port",raw.get("to_symbol_port",0)) or 0))
        except (TypeError,ValueError):
            continue
        spec=str(raw.get("cable_spec",raw.get("spec","")) or "").strip()
        if not spec or (default is not None and spec==default):
            continue
        a=(a_uid,a_port); b=(b_uid,b_port)
        if b<a:
            a,b=b,a
        by_key[(a,b)]={
            "a_symbol_uid":a[0],"a_symbol_port":a[1],
            "b_symbol_uid":b[0],"b_symbol_port":b[1],
            "cable_spec":spec,
        }
    for key in sorted(by_key):
        out.append(by_key[key])
    return out


def _cable_route_section_key(a,b):
    """Canonical key for two connection dictionaries/tuples."""
    def endpoint(value):
        if isinstance(value,dict):
            return (str(value.get("symbol_uid","") or "").strip(),max(0,int(value.get("symbol_port",0) or 0)))
        return (str(value[0] or "").strip(),max(0,int(value[1] or 0)))
    x=endpoint(a); y=endpoint(b)
    return tuple(sorted((x,y)))


def _cable_spec_section_key(a,b):
    return _cable_route_section_key(a,b)


def cable_connection_sections(cable: CablePlacement) -> list[dict]:
    """Return adjacent physical connection-to-connection sections along a cable."""
    rows=cable_symbol_connections(cable)
    out=[]
    for index,(a,b) in enumerate(zip(rows,rows[1:])):
        ai=int(a.get("point_index",0) or 0); bi=int(b.get("point_index",0) or 0)
        if bi<=ai:
            continue
        out.append({
            "section_index":index,
            "start_point_index":ai,
            "end_point_index":bi,
            "a":dict(a),"b":dict(b),
            "key":_cable_route_section_key(a,b),
        })
    return out


def cable_spec_for_section(cable: CablePlacement, a, b) -> str:
    """Effektiv kabeltype for ét fysisk afsnit, ellers kabellets standardtype."""
    key=_cable_spec_section_key(a,b)
    for row in normalize_cable_spec_section_overrides(
        getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
    ):
        if _cable_spec_section_key(
            (row["a_symbol_uid"],row["a_symbol_port"]),(row["b_symbol_uid"],row["b_symbol_port"])
        )==key:
            return str(row["cable_spec"])
    return str(getattr(cable,"cable_spec","") or "").strip()


def cable_spec_section_at_segment(cable: CablePlacement, segment_index: int) -> dict | None:
    """Find fysisk afsnit og effektiv kabeltype for et polyline-segment."""
    seg=int(segment_index)
    for section in cable_connection_sections(cable):
        if int(section["start_point_index"]) <= seg < int(section["end_point_index"]):
            rec=dict(section)
            rec["cable_spec"]=cable_spec_for_section(cable,section["a"],section["b"])
            return rec
    return None
