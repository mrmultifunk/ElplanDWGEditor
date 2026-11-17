"""Fysiske kabelafsnit, lokale overrides og ruteopdeling."""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict

from elplan_core.cables.connections import (
    cable_connection_at,
    cable_symbol_connections,
    normalize_cable_symbol_connections,
    replace_cable_connection,
    set_cable_symbol_connections,
)
from elplan_core.cables.geometry import (
    convert_cable_route_mode_geometry,
    move_polyline_endpoint_flexible,
    polyline_label_point,
)
from elplan_core.models import CablePlacement


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


def split_cable_into_physical_segments(cable: CablePlacement, cable_ids=None, *, return_legacy_map: bool = False):
    """Split a legacy multi-stop cable into independent physical cables.

    Geometry between neighbouring physical symbol connections becomes one
    ``CablePlacement``. Loose geometry before the first or after the last
    connection is preserved as its own cable, so migration never discards a
    drawn route. Section-specific cable type and routing mode are materialised
    onto each resulting cable.

    ``return_legacy_map`` additionally returns a mapping from old PL-box leg
    identity ``(uid, point_index, leg)`` to the new cable endpoint identity.
    """
    points=[(float(p[0]),float(p[1])) for p in (getattr(cable,"points",[]) or [])]
    conns=cable_symbol_connections(cable)
    endpoint_indices={0,max(0,len(points)-1)}
    connection_indices={int(r.get("point_index",0) or 0) for r in conns}
    already_physical=(len(conns)<=2 and connection_indices.issubset(endpoint_indices))
    if len(points)<2 or already_physical:
        if not getattr(cable,"route_chain_uid",""):
            cable.route_chain_uid=str(getattr(cable,"uid","") or uuid.uuid4().hex)
        # A pre-0.55 cable with exactly two endpoints could still store its only
        # physical span as an "override". Materialise that value now so the new
        # model has one authoritative cable type/routing mode and no section layer.
        if len(conns)==2:
            cable.cable_spec=cable_spec_for_section(cable,conns[0],conns[1])
            cable.orthogonal=cable_route_section_mode(cable,conns[0],conns[1])=="orthogonal"
        cable.route_section_modes=[]
        cable.spec_section_overrides=[]
        result=[cable]
        return (result,{}) if return_legacy_map else result

    boundaries=[0]
    boundaries.extend(int(r["point_index"]) for r in conns)
    boundaries.append(len(points)-1)
    boundaries=sorted(set(max(0,min(i,len(points)-1)) for i in boundaries))
    spans=[(a,b) for a,b in zip(boundaries,boundaries[1:]) if b>a]
    if not spans:
        result=[cable]
        return (result,{}) if return_legacy_map else result

    supplied=[str(x or "").strip() for x in (cable_ids or [])]
    base_id=str(getattr(cable,"cable_id","") or "").strip()
    chain_uid=str(getattr(cable,"route_chain_uid","") or getattr(cable,"uid","") or uuid.uuid4().hex)
    old_uid=str(getattr(cable,"uid","") or "")
    old_conn_by_index={int(r["point_index"]):dict(r) for r in conns}
    segments=[]; legacy_map={}

    for seg_no,(start,end) in enumerate(spans):
        data=asdict(cable)
        data["points"]=points[start:end+1]
        # Keep the first UID for backwards references; subsequent physical cables
        # receive fresh stable identities.
        data["uid"]=old_uid if seg_no==0 and old_uid else uuid.uuid4().hex
        data["route_chain_uid"]=chain_uid
        data["route_section_modes"]=[]
        data["spec_section_overrides"]=[]

        start_conn=old_conn_by_index.get(start)
        end_conn=old_conn_by_index.get(end)
        local=[]
        if start_conn is not None:
            local.append({"point_index":0,"symbol_uid":start_conn["symbol_uid"],"symbol_port":start_conn["symbol_port"]})
        if end_conn is not None:
            local.append({"point_index":end-start,"symbol_uid":end_conn["symbol_uid"],"symbol_port":end_conn["symbol_port"]})
        data["symbol_connections"]=normalize_cable_symbol_connections(local,len(data["points"]))

        # A span bounded by two symbol connections may have had legacy
        # section-specific settings. Materialise them on the real cable.
        if start_conn is not None and end_conn is not None:
            data["cable_spec"]=cable_spec_for_section(cable,start_conn,end_conn)
            data["orthogonal"]=cable_route_section_mode(cable,start_conn,end_conn)=="orthogonal"
        else:
            # Loose head/tail spans used the cable defaults.
            data["cable_spec"]=str(getattr(cable,"cable_spec","") or "")
            data["orthogonal"]=bool(getattr(cable,"orthogonal",False))

        if seg_no < len(supplied) and supplied[seg_no]:
            data["cable_id"]=supplied[seg_no]
        elif len(spans)>1 and base_id:
            data["cable_id"]=base_id if seg_no==0 else f"{base_id}-{seg_no+1}"

        segment=CablePlacement(**data)
        set_cable_symbol_connections(segment,data["symbol_connections"])
        segments.append(segment)

        # PL legacy mapping. A middle connection had Side A/Side B; with real
        # cables each side is simply the endpoint of its own cable.
        if start_conn is not None:
            old_leg="endpoint" if start==0 else "after"
            legacy_map[(old_uid,start,old_leg)]={
                "cable_uid":segment.uid,"point_index":0,"leg":"endpoint"
            }
        if end_conn is not None:
            old_leg="endpoint" if end==len(points)-1 else "before"
            legacy_map[(old_uid,end,old_leg)]={
                "cable_uid":segment.uid,"point_index":len(segment.points)-1,"leg":"endpoint"
            }

    return (segments,legacy_map) if return_legacy_map else segments


def normalize_cable_route_section_modes(records):
    """Normalisér lokale ruteføringsvalg mellem to fysiske kabeltilslutninger.

    Posterne er uafhængige af polyline-indeks og overlever derfor geometri-
    ændringer. Et afsnit er retningsløst: A→B og B→A er samme fysiske stræk.
    """
    out=[]; by_key={}
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
        mode=str(raw.get("mode","") or "").strip().lower()
        if mode not in {"free","orthogonal"}:
            continue
        a=(a_uid,a_port); b=(b_uid,b_port)
        if b<a:
            a,b=b,a
        key=(a,b)
        by_key[key]={"a_symbol_uid":a[0],"a_symbol_port":a[1],"b_symbol_uid":b[0],"b_symbol_port":b[1],"mode":mode}
    for key in sorted(by_key):
        out.append(by_key[key])
    return out


def cable_route_section_mode(cable: CablePlacement, a, b) -> str:
    """Effective route mode for a physical section, falling back to cable default."""
    key=_cable_route_section_key(a,b)
    for row in normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[])):
        if _cable_route_section_key((row["a_symbol_uid"],row["a_symbol_port"]),(row["b_symbol_uid"],row["b_symbol_port"]))==key:
            return str(row["mode"])
    return "orthogonal" if bool(getattr(cable,"orthogonal",False)) else "free"


def set_cable_spec_for_section(cable: CablePlacement, a, b, cable_spec: str) -> None:
    """Sæt eller ryd lokal kabeltype for ét tilslutning-til-tilslutning-afsnit."""
    spec=str(cable_spec or "").strip()
    if not spec:
        raise ValueError("Kabeltype må ikke være tom")
    key=_cable_spec_section_key(a,b)
    default=str(getattr(cable,"cable_spec","") or "").strip()
    rows=[]
    for row in normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]),default):
        rkey=_cable_spec_section_key(
            (row["a_symbol_uid"],row["a_symbol_port"]),(row["b_symbol_uid"],row["b_symbol_port"])
        )
        if rkey!=key:
            rows.append(row)
    if spec!=default:
        x,y=key
        rows.append({
            "a_symbol_uid":x[0],"a_symbol_port":x[1],
            "b_symbol_uid":y[0],"b_symbol_port":y[1],
            "cable_spec":spec,
        })
    cable.spec_section_overrides=normalize_cable_spec_section_overrides(rows,default)


def cable_spec_for_leg(cable: CablePlacement, point_index: int, leg: str) -> str:
    """Effektiv kabeltype på et bestemt fysisk kabelben ved en PL-dåse."""
    pts=list(getattr(cable,"points",[]) or [])
    if len(pts)<2:
        return str(getattr(cable,"cable_spec","") or "").strip()
    idx=max(0,min(int(point_index),len(pts)-1)); side=str(leg or "")
    if side=="before":
        seg=idx-1
    elif side=="after":
        seg=idx
    else:  # endpoint
        seg=0 if idx<=0 else idx-1
    section=cable_spec_section_at_segment(cable,max(0,min(seg,len(pts)-2)))
    return str((section or {}).get("cable_spec") or getattr(cable,"cable_spec","") or "").strip()


def cable_effective_specs(cable: CablePlacement) -> list[str]:
    """Unikke kabeltyper der reelt forekommer langs kabellets fysiske afsnit."""
    values=[]
    sections=cable_connection_sections(cable)
    if sections:
        for section in sections:
            spec=cable_spec_for_section(cable,section["a"],section["b"])
            if spec and spec not in values:
                values.append(spec)
    else:
        spec=str(getattr(cable,"cable_spec","") or "").strip()
        if spec: values.append(spec)
    return values


def cable_section_spec_labels(cable: CablePlacement) -> list[dict]:
    """Labels til tegning/output når kabeltypen varierer langs samme kabel."""
    overrides=normalize_cable_spec_section_overrides(
        getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
    )
    if not overrides:
        return []
    pts=list(getattr(cable,"points",[]) or [])
    out=[]
    for section in cable_connection_sections(cable):
        start=int(section["start_point_index"]); end=int(section["end_point_index"])
        if not (0<=start<end<len(pts)):
            continue
        section_points=pts[start:end+1]
        x,y=polyline_label_point(section_points)
        out.append({
            "section":dict(section),
            "cable_spec":cable_spec_for_section(cable,section["a"],section["b"]),
            "point":(float(x),float(y)),
        })
    return out


def set_cable_route_section_mode(cable: CablePlacement, a, b, mode: str) -> None:
    """Set or clear one local route override.

    Choosing the cable's default mode removes the explicit override, keeping the
    project compact and making later global mode changes predictable.
    """
    mode=str(mode or "").strip().lower()
    if mode not in {"free","orthogonal"}:
        raise ValueError("Ugyldig ruteføring")
    key=_cable_route_section_key(a,b)
    rows=[]
    for row in normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[])):
        rkey=_cable_route_section_key((row["a_symbol_uid"],row["a_symbol_port"]),(row["b_symbol_uid"],row["b_symbol_port"]))
        if rkey!=key:
            rows.append(row)
    default="orthogonal" if bool(getattr(cable,"orthogonal",False)) else "free"
    if mode!=default:
        x,y=key
        rows.append({"a_symbol_uid":x[0],"a_symbol_port":x[1],"b_symbol_uid":y[0],"b_symbol_port":y[1],"mode":mode})
    cable.route_section_modes=normalize_cable_route_section_modes(rows)


def cable_route_mode_for_point_index(cable: CablePlacement, point_index: int) -> str:
    """Effective local mode around an editable polyline point."""
    idx=int(point_index)
    for section in cable_connection_sections(cable):
        if int(section["start_point_index"]) < idx < int(section["end_point_index"]):
            return cable_route_section_mode(cable,section["a"],section["b"])
    return "orthogonal" if bool(getattr(cable,"orthogonal",False)) else "free"


def cable_route_section_at_segment(cable: CablePlacement, segment_index: int) -> dict | None:
    """Find the connection-to-connection section containing a polyline segment."""
    seg=int(segment_index)
    for section in cable_connection_sections(cable):
        if int(section["start_point_index"]) <= seg < int(section["end_point_index"]):
            rec=dict(section)
            rec["mode"]=cable_route_section_mode(cable,section["a"],section["b"])
            return rec
    return None


def convert_cable_route_section_geometry(points, connections, start_point_index: int, end_point_index: int, *, from_orthogonal: bool, to_orthogonal: bool):
    """Convert only one connection-bounded part of a cable polyline.

    Points and physical connection indices before/after the section are retained
    and remapped. This is the core of mixed 90°/diagonal routing on one cable.
    """
    pts=[(float(p[0]),float(p[1])) for p in (points or []) if isinstance(p,(list,tuple)) and len(p)>=2]
    rows=normalize_cable_symbol_connections(connections or [],len(pts))
    if len(pts)<2:
        return pts,rows
    start=max(0,min(int(start_point_index),len(pts)-1)); end=max(0,min(int(end_point_index),len(pts)-1))
    if end<start:
        start,end=end,start
    if end-start<1 or bool(from_orthogonal)==bool(to_orthogonal):
        return pts,rows
    sub=pts[start:end+1]
    sub_rows=[]
    outside=[]
    for row in rows:
        idx=int(row.get("point_index",0) or 0)
        if start<=idx<=end:
            rec=dict(row); rec["point_index"]=idx-start; sub_rows.append(rec)
        else:
            outside.append(dict(row))
    new_sub,new_sub_rows=convert_cable_route_mode_geometry(sub,sub_rows,from_orthogonal=from_orthogonal,to_orthogonal=to_orthogonal)
    new_pts=pts[:start]+new_sub+pts[end+1:]
    delta=len(new_sub)-len(sub)
    remapped=[]
    for row in outside:
        rec=dict(row); idx=int(rec.get("point_index",0) or 0)
        if idx>end:
            rec["point_index"]=idx+delta
        remapped.append(rec)
    for row in new_sub_rows:
        rec=dict(row); rec["point_index"]=start+int(rec.get("point_index",0) or 0); remapped.append(rec)
    return new_pts,normalize_cable_symbol_connections(remapped,len(new_pts))


def nearest_cable_segment(points, point) -> dict | None:
    """Find nærmeste segment/projektion på en kabelpolyline.

    Returnerer segmentindeks, projektion, afstand og parameter ``t``. Funktionen
    er bevidst GUI-uafhængig, så både klik-værktøjer og senere projektkontrol kan
    bruge samme geometri.
    """
    pts=[(float(x),float(y)) for x,y in (points or [])]
    if len(pts)<2:
        return None
    x,y=float(point[0]),float(point[1])
    best=None
    for i,(a,b) in enumerate(zip(pts,pts[1:])):
        ax,ay=a; bx,by=b
        dx=bx-ax; dy=by-ay; den=dx*dx+dy*dy
        if den<=1e-18:
            t=0.0; px,py=ax,ay
        else:
            t=max(0.0,min(1.0,((x-ax)*dx+(y-ay)*dy)/den))
            px,py=ax+t*dx,ay+t*dy
        dist=math.hypot(px-x,py-y)
        if best is None or dist<float(best["distance"]):
            best={"segment_index":i,"point":(px,py),"distance":dist,"t":t}
    return best


def attach_symbol_to_existing_cable(cable: CablePlacement, symbol_uid: str, symbol_port: int,
                                    target_point, segment_index: int | None = None) -> dict:
    """Kobl et eksisterende symbol fysisk på en allerede tegnet kabelrute.

    ``target_point`` er symbolportens faktiske CAD-position. Hvis porten ligger
    på et eksisterende knæk/endepunkt, genbruges punktet. Ellers indsættes et
    nyt fysisk anker på det valgte segment. Fri/diagonal føring går direkte via
    symbolet; ortogonal føring får lokale 90°-knæk, så hele ruten forbliver
    ortogonal. Eksisterende symboltilslutninger remappes altid.

    Resultatet indeholder ``status`` (``attached``, ``already_attached`` eller
    ``occupied``), det nye ``point_index`` og afstanden fra symbolporten til det
    oprindelige segment.
    """
    uid=str(symbol_uid or "").strip()
    if not uid:
        raise ValueError("symbol_uid mangler")
    pts=[(float(x),float(y)) for x,y in (getattr(cable,"points",[]) or [])]
    if len(pts)<2:
        raise ValueError("Kablet har ikke en gyldig rute")
    target=(float(target_point[0]),float(target_point[1]))
    rows=[dict(r) for r in cable_symbol_connections(cable)]
    for row in rows:
        if str(row.get("symbol_uid","") or "")==uid:
            return {"status":"already_attached","point_index":int(row.get("point_index",0) or 0),"distance":0.0}

    nearest=nearest_cable_segment(pts,target)
    if nearest is None:
        raise ValueError("Kablet har ikke et segment")
    if segment_index is None:
        seg=int(nearest["segment_index"])
    else:
        seg=max(0,min(int(segment_index),len(pts)-2))
        local=nearest_cable_segment(pts[seg:seg+2],target)
        nearest={
            "segment_index":seg,
            "point":local["point"] if local else pts[seg],
            "distance":local["distance"] if local else math.hypot(target[0]-pts[seg][0],target[1]-pts[seg][1]),
            "t":local["t"] if local else 0.0,
        }

    section_before=cable_route_section_at_segment(cable,seg)
    section_spec_before=cable_spec_section_at_segment(cable,seg)
    local_orthogonal=(str(section_before.get("mode",""))=="orthogonal") if section_before else bool(getattr(cable,"orthogonal",False))

    def preserve_section_overrides_for_new_connection(point_index: int):
        new_rec={"point_index":int(point_index),"symbol_uid":uid,"symbol_port":max(0,int(symbol_port or 0))}
        if section_before:
            mode=str(section_before.get("mode","") or "")
            default="orthogonal" if bool(getattr(cable,"orthogonal",False)) else "free"
            if mode!=default:
                set_cable_route_section_mode(cable,section_before["a"],section_before["b"],default)
                set_cable_route_section_mode(cable,section_before["a"],new_rec,mode)
                set_cable_route_section_mode(cable,new_rec,section_before["b"],mode)
        if section_spec_before:
            spec=str(section_spec_before.get("cable_spec","") or "")
            default_spec=str(getattr(cable,"cable_spec","") or "")
            if spec and spec!=default_spec:
                set_cable_spec_for_section(cable,section_spec_before["a"],section_spec_before["b"],default_spec)
                set_cable_spec_for_section(cable,section_spec_before["a"],new_rec,spec)
                set_cable_spec_for_section(cable,new_rec,section_spec_before["b"],spec)

    eps=1e-7
    # Genbrug et eksisterende rutepunkt, hvis symbolporten allerede ligger der.
    candidate_indices=[seg,seg+1]
    for idx in candidate_indices:
        if math.hypot(pts[idx][0]-target[0],pts[idx][1]-target[1])<=eps:
            existing=cable_connection_at(cable,idx)
            if existing and str(existing.get("symbol_uid","") or "")!=uid:
                return {"status":"occupied","point_index":idx,"distance":float(nearest["distance"]),"occupied_by":str(existing.get("symbol_uid","") or "")}
            replace_cable_connection(cable,idx,uid,symbol_port)
            preserve_section_overrides_for_new_connection(idx)
            return {"status":"attached","point_index":idx,"distance":float(nearest["distance"]),"inserted_points":0,"endpoint":idx in (0,len(pts)-1)}

    # Hvis lampestedet tydeligt ligger ved en fri kabelende, er den intuitive
    # betydning "kablet starter/slutter her" – ikke en kunstig gennemsløjfning
    # med to PL-ben. Flyt derfor den frie ende til symbolporten og indsæt kun
    # det nødvendige 90°-knæk.
    t=float(nearest.get("t",0.5) or 0.0)
    endpoint_index=None
    if seg==0 and t<=0.12 and cable_connection_at(cable,0) is None:
        endpoint_index=0
    elif seg==len(pts)-2 and t>=0.88 and cable_connection_at(cable,len(pts)-1) is None:
        endpoint_index=len(pts)-1
    if endpoint_index is not None:
        moved,new_index,delta=move_polyline_endpoint_flexible(pts,endpoint_index,target,local_orthogonal)
        remapped=[]
        for row in rows:
            rec=dict(row); old_idx=int(rec.get("point_index",0) or 0)
            if endpoint_index==0 and old_idx>0:
                rec["point_index"]=old_idx+int(delta)
            remapped.append(rec)
        cable.points=moved
        remapped.append({"point_index":int(new_index),"symbol_uid":uid,"symbol_port":max(0,int(symbol_port or 0))})
        set_cable_symbol_connections(cable,remapped)
        preserve_section_overrides_for_new_connection(int(new_index))
        return {"status":"attached","point_index":int(new_index),"distance":float(nearest["distance"]),"inserted_points":max(0,int(delta)),"endpoint":True}

    a=pts[seg]; b=pts[seg+1]
    inserted=[]
    if local_orthogonal:
        horizontal=math.isclose(a[1],b[1],abs_tol=eps)
        vertical=math.isclose(a[0],b[0],abs_tol=eps)
        if horizontal and math.isclose(target[1],a[1],abs_tol=eps):
            inserted=[target]
        elif vertical and math.isclose(target[0],a[0],abs_tol=eps):
            inserted=[target]
        elif horizontal:
            inserted=[(target[0],a[1]),target,(b[0],target[1])]
        elif vertical:
            inserted=[(a[0],target[1]),target,(target[0],b[1])]
        else:
            # Defensiv håndtering af et gammelt kabel markeret som ortogonalt,
            # men som indeholder et diagonalt segment. To 90°-knæk fra A via
            # symbolporten og videre til B retter lokalt geometrien op.
            inserted=[(target[0],a[1]),target,(b[0],target[1])]
    else:
        inserted=[target]

    # Fjern kun sekventielle dubletter. Et hjælpeknæk må godt være identisk
    # med segmentets B-punkt, hvis ruten bagefter går ud til symbolporten og
    # tilbage til B; ellers ville et ortogonalt endesegment blive diagonalt.
    clean=[]
    for pos,point in enumerate(inserted):
        p=(float(point[0]),float(point[1]))
        if pos==0 and math.hypot(p[0]-a[0],p[1]-a[1])<=eps:
            continue
        if clean and math.hypot(p[0]-clean[-1][0],p[1]-clean[-1][1])<=eps:
            continue
        clean.append(p)
    if clean and math.hypot(clean[-1][0]-b[0],clean[-1][1]-b[1])<=eps:
        clean.pop()
    if not clean:
        # Burde kun kunne ske ved numeriske randtilfælde; genbrug nærmeste ende.
        idx=seg if math.hypot(target[0]-a[0],target[1]-a[1])<=math.hypot(target[0]-b[0],target[1]-b[1]) else seg+1
        existing=cable_connection_at(cable,idx)
        if existing and str(existing.get("symbol_uid","") or "")!=uid:
            return {"status":"occupied","point_index":idx,"distance":float(nearest["distance"]),"occupied_by":str(existing.get("symbol_uid","") or "")}
        replace_cable_connection(cable,idx,uid,symbol_port)
        preserve_section_overrides_for_new_connection(idx)
        return {"status":"attached","point_index":idx,"distance":float(nearest["distance"]),"inserted_points":0}

    # Find targetens plads i den rensede indsættelse. Hvis et hjælpeknæk faldt
    # sammen med target, er det den pågældende position, der bliver ankeret.
    target_local=min(range(len(clean)),key=lambda j:math.hypot(clean[j][0]-target[0],clean[j][1]-target[1]))
    if math.hypot(clean[target_local][0]-target[0],clean[target_local][1]-target[1])>eps:
        clean.insert(target_local+1,target); target_local+=1

    shift=len(clean)
    new_rows=[]
    for row in rows:
        rec=dict(row); old_idx=int(rec.get("point_index",0) or 0)
        if old_idx>seg:
            rec["point_index"]=old_idx+shift
        new_rows.append(rec)
    new_index=seg+1+target_local
    occupied=next((r for r in new_rows if int(r.get("point_index",-1))==new_index and str(r.get("symbol_uid","") or "")!=uid),None)
    if occupied:
        return {"status":"occupied","point_index":new_index,"distance":float(nearest["distance"]),"occupied_by":str(occupied.get("symbol_uid","") or "")}
    cable.points=pts[:seg+1]+clean+pts[seg+1:]
    new_rows.append({"point_index":new_index,"symbol_uid":uid,"symbol_port":max(0,int(symbol_port or 0))})
    set_cable_symbol_connections(cable,new_rows)
    preserve_section_overrides_for_new_connection(new_index)
    return {"status":"attached","point_index":new_index,"distance":float(nearest["distance"]),"inserted_points":shift}
