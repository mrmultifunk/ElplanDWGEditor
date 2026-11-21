"""Kabelmærkning og visuelle kabelbaner til tegning og eksport."""

from __future__ import annotations

import math
from collections import defaultdict

from elplan_core.cables.connections import cable_symbol_connections
from elplan_core.cables.sections import normalize_cable_spec_section_overrides
from elplan_core.models import CablePlacement


def cable_display_label(cable: CablePlacement) -> str:
    """Byg den tekst, der vises/eksporteres ved et kabel eller en ledning."""
    parts=[]
    if getattr(cable, "auto_label", False):
        if getattr(cable, "cable_id", ""): parts.append(str(cable.cable_id).strip())
        # Ved blandede kabeltyper vises kabel-ID'et som fælles hovedlabel,
        # mens de faktiske typer mærkes pr. fysisk afsnit. Ellers kunne en
        # global 3G-label ved et lokalt 5G-afsnit være direkte misvisende.
        if not normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        ) and getattr(cable, "cable_spec", ""):
            parts.append(str(cable.cable_spec).strip())
    if getattr(cable, "label", ""): parts.append(str(cable.label).strip())
    return " · ".join(x for x in parts if x)


def cable_plan_label(cable: CablePlacement) -> str:
    """Kompakt kabelmærkning til selve plantegningen.

    Den brugerdefinerede ekstra mærkning er bevidst udeladt fra canvas/print;
    den er stadig projektdata og vises i hover/inspector/ruteoversigter.
    """
    parts=[]
    if getattr(cable, "auto_label", False):
        if getattr(cable, "cable_id", ""): parts.append(str(cable.cable_id).strip())
        if not normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        ) and getattr(cable, "cable_spec", ""):
            parts.append(str(cable.cable_spec).strip())
    return " · ".join(x for x in parts if x)


def _visual_segment_info(a, b):
    ax,ay=float(a[0]),float(a[1]); bx,by=float(b[0]),float(b[1])
    dx=bx-ax; dy=by-ay; length=math.hypot(dx,dy)
    if length<=1e-12:return None
    ux=dx/length; uy=dy/length
    # Fælles kanonisk retning gør, at kabler tegnet i modsat retning stadig
    # får den samme fysiske side af centerlinjen for samme lane-indeks.
    cux,cuy=ux,uy
    if cux < -1e-12 or (abs(cux)<=1e-12 and cuy < 0.0):
        cux,cuy=-cux,-cuy
    nx,ny=-cuy,cux
    return {
        "a":(ax,ay),"b":(bx,by),"u":(ux,uy),"cu":(cux,cuy),
        "n":(nx,ny),"length":length,
    }


def _visual_segments_overlap(sa, sb, tolerance: float, min_overlap: float) -> bool:
    """Return True when two cable segments are visually the same route.

    Parallel cable detection is intentionally screen-tolerant rather than CAD-
    exact.  Real projects often contain tiny coordinate/angle differences from
    snapping, imported drawings or later edits.  If those differences are only
    a few screen pixels the user sees one merged line, so they must still be
    treated as a shared route and separated into lanes.
    """
    if sa is None or sb is None:return False
    u1=sa["cu"]; u2=sb["cu"]

    # Up to ~2 degrees is accepted, but only if the two lines also stay within
    # the screen-derived distance tolerance over the actual overlap below.
    if abs(u1[0]*u2[1]-u1[1]*u2[0]) > math.sin(math.radians(2.0)):
        return False

    ux,uy=u1
    nx,ny=sa["n"]
    def proj(pt):return float(pt[0])*ux+float(pt[1])*uy
    a0,a1=sorted((proj(sa["a"]),proj(sa["b"])))
    b0,b1=sorted((proj(sb["a"]),proj(sb["b"])))
    lo=max(a0,b0); hi=min(a1,b1)
    if hi-lo <= min_overlap:return False

    # Compare the two infinite lines at both ends of the common projected
    # interval.  This catches tiny non-collinearity while rejecting nearby
    # routes that merely cross or diverge visibly.
    bax,bay=sb["a"]; bux,buy=sb["u"]
    denom=bux*ux+buy*uy
    if abs(denom)<=1e-9:return False
    aax,aay=sa["a"]
    base_proj=proj(sb["a"])
    for t in (lo,hi,(lo+hi)*0.5):
        s=(t-base_proj)/denom
        qx=bax+bux*s; qy=bay+buy*s
        # Point on A's line with the same canonical projection.
        pa_x=aax+ux*(t-proj(sa["a"]))
        pa_y=aay+uy*(t-proj(sa["a"]))
        dist=abs((qx-pa_x)*nx+(qy-pa_y)*ny)
        if dist > tolerance:return False
    return True


def _line_intersection(p1, d1, p2, d2):
    cross=d1[0]*d2[1]-d1[1]*d2[0]
    if abs(cross)<=1e-10:return None
    qx=float(p2[0])-float(p1[0]); qy=float(p2[1])-float(p1[1])
    t=(qx*d2[1]-qy*d2[0])/cross
    return (float(p1[0])+t*d1[0],float(p1[1])+t*d1[1])


def _cable_visual_sort_key(cable, fallback_index: int = 0):
    """Stable ordering for visual lanes independent of project/list ordering."""
    cid=str(getattr(cable,"cable_id","") or "").strip().casefold()
    uid=str(getattr(cable,"uid","") or "").strip().casefold()
    spec=str(getattr(cable,"cable_spec","") or "").strip().casefold()
    return (cid or "~", uid or "~", spec, int(fallback_index))


def cable_visual_layout(cables, lane_gap: float, *, tolerance: float | None=None, fan_length: float | None=None):
    """Return visual paths, per-cable lane metadata and shared-route groups.

    ``CablePlacement.points`` is never modified.  Cables sharing a logical
    centreline are placed on stable screen-space lanes.  The lane order uses
    cable id/uid rather than list order, so adding/removing another cable does
    not randomly swap the physical side of existing lanes.
    """
    cable_list=list(cables or [])
    gap=max(abs(float(lane_gap)),0.0)
    result={id(c):[(float(x),float(y)) for x,y in getattr(c,"points",[]) or []] for c in cable_list}
    metadata={id(c):{
        "lane_index":0,"lane_count":1,"lane_offset":0.0,"max_parallel":1,
        "peer_ids":[str(getattr(c,"cable_id","") or "")],"parallel_segments":0,
    } for c in cable_list}
    if gap<=1e-12 or len(cable_list)<2:
        return result, metadata, []
    # Match routes by what the user actually sees.  Roughly 3.5 px at the
    # default 10 px lane gap may look like one anti-aliased line at overview
    # zoom, even though the CAD centre lines are not numerically identical.
    tol=max(float(tolerance) if tolerance is not None else gap*0.35,1e-8)
    min_overlap=max(gap*1.15,tol*3.5,1e-7)
    fan=max(float(fan_length) if fan_length is not None else gap*2.35,gap)

    segments=[]
    per_cable=[]
    for ci,cable in enumerate(cable_list):
        pts=[(float(x),float(y)) for x,y in getattr(cable,"points",[]) or []]
        indices=[]
        for si,(a,b) in enumerate(zip(pts,pts[1:])):
            info=_visual_segment_info(a,b)
            if info is not None:
                info.update({"cable":ci,"segment":si})
                indices.append(len(segments)); segments.append(info)
            else:
                indices.append(None)
        per_cable.append((pts,indices))

    stable_keys={ci:_cable_visual_sort_key(cable_list[ci],ci) for ci in range(len(cable_list))}
    offsets_by_segment={}
    group_candidates={}

    # 0.59.58 performance: the old implementation compared every segment with
    # every other segment on every zoom-dependent lane rebuild (O(S²)).  First
    # use a conservative expanded bounding-box sweep to reject segment pairs
    # that cannot possibly share a route.  _visual_segments_overlap remains the
    # authoritative test, so visual behaviour and tolerance rules are unchanged.
    peer_cables=[{seg["cable"]} for seg in segments]
    if len(segments)>1:
        expanded=[]
        for idx,seg in enumerate(segments):
            ax,ay=seg["a"]; bx,by=seg["b"]
            expanded.append((min(ax,bx)-tol,max(ax,bx)+tol,min(ay,by)-tol,max(ay,by)+tol,idx))
        sweep=sorted(expanded,key=lambda row:row[0])
        sweep_count=len(sweep)
        for pos,left in enumerate(sweep):
            _xmin,xmax,ymin,ymax,idx=left
            seg=segments[idx]
            # Do not slice ``sweep[pos+1:]`` here.  Even when the first x
            # coordinate rejects the candidate immediately, that slice copies
            # the complete remaining list and quietly turns a sparse plan back
            # into quadratic work.
            next_pos=pos+1
            while next_pos<sweep_count:
                other_row=sweep[next_pos]
                next_pos+=1
                oxmin,_oxmax,oymin,oymax,j=other_row
                if oxmin>xmax:
                    break
                if oymin>ymax or oymax<ymin:
                    continue
                other=segments[j]
                if other["cable"]==seg["cable"]:
                    continue
                if _visual_segments_overlap(seg,other,tol,min_overlap):
                    peer_cables[idx].add(other["cable"])
                    peer_cables[j].add(seg["cable"])

    for idx,seg in enumerate(segments):
        peers=peer_cables[idx]
        if len(peers)>1:
            order=sorted(peers,key=lambda ci:stable_keys[ci])
            lane_index=order.index(seg["cable"])
            lane=lane_index-(len(order)-1)/2.0
            peer_ids=[str(getattr(cable_list[ci],"cable_id","") or "Kabel") for ci in order]
            offsets_by_segment[(seg["cable"],seg["segment"])]=(lane*gap,lane_index,len(order),peer_ids)
            meta=metadata[id(cable_list[seg["cable"]])]
            meta["parallel_segments"]+=1
            if len(order)>int(meta.get("max_parallel",1)) or (
                len(order)==int(meta.get("max_parallel",1)) and seg["length"]>float(meta.get("_best_length",-1.0))
            ):
                meta.update({
                    "lane_index":lane_index,"lane_count":len(order),"lane_offset":lane*gap,
                    "max_parallel":len(order),"peer_ids":peer_ids,"_best_length":float(seg["length"]),
                })

            # One compact badge per peer-set, positioned on its longest shared
            # segment.  Used by the Qt overview to show e.g. “×6”.
            group_key=tuple(order)
            mid=((seg["a"][0]+seg["b"][0])*.5,(seg["a"][1]+seg["b"][1])*.5)
            old=group_candidates.get(group_key)
            if old is None or seg["length"]>old["length"]:
                group_candidates[group_key]={
                    "count":len(order),"cable_indices":list(order),"cable_ids":peer_ids,
                    "point":mid,"length":float(seg["length"]),
                }

    # Fælles fysisk afgang fra samme symbol/terminal er autoritativ for fan-out.
    # Segmentmatching alene er ikke nok: i rigtige projekter kan to kabler være
    # opdelt i forskellige knækpunkter eller afvige en anelse, selv om de visuelt
    # forlader samme tavle/lampested i samme retning. Derfor tvinges de første
    # kollineære segmenter ud på stabile baner ud fra selve endepunktsankeret.
    endpoint_records=[]
    anchor_tol=max(tol,gap*0.35,1e-8)
    direction_cos=math.cos(math.radians(12.0))
    for ci,(pts,seg_indices) in enumerate(per_cable):
        if len(pts)<2:
            continue
        conn_by_index={int(r.get("point_index",-1)):r for r in cable_symbol_connections(cable_list[ci])}
        for at_start in (True,False):
            vi=0 if at_start else len(pts)-1
            si=0 if at_start else len(pts)-2
            idx=seg_indices[si] if 0 <= si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            if info is None:
                continue
            if at_start:
                outward=info["u"]
            else:
                outward=(-info["u"][0],-info["u"][1])
            conn=conn_by_index.get(vi)
            symbol_key=None
            if conn is not None and str(conn.get("symbol_uid","") or "").strip():
                symbol_key=(str(conn.get("symbol_uid","") or "").strip(),int(conn.get("symbol_port",0) or 0))
            endpoint_records.append({
                "cable":ci,"vertex":vi,"segment":si,"at_start":at_start,
                "point":pts[vi],"outward":outward,"symbol_key":symbol_key,
            })

    def same_endpoint_anchor(a,b):
        ka=a.get("symbol_key"); kb=b.get("symbol_key")
        if ka is not None and kb is not None:
            return ka==kb
        ax,ay=a["point"]; bx,by=b["point"]
        return math.hypot(ax-bx,ay-by) <= anchor_tol

    def same_departure(a,b):
        au=a["outward"]; bu=b["outward"]
        return au[0]*bu[0]+au[1]*bu[1] >= direction_cos

    # Candidate lookup for endpoint fan-out.  The previous all-pairs loop was
    # O(C²), even when the cable ends were spread across an entire building.
    # Exact symbol/port buckets preserve the authoritative terminal rule;
    # neighbouring spatial cells cover coordinate-based legacy endpoints.
    endpoint_symbol_buckets=defaultdict(list)
    endpoint_spatial_buckets=defaultdict(list)
    endpoint_cell=max(anchor_tol,1e-8)
    endpoint_cells=[]
    for record_index,rec in enumerate(endpoint_records):
        symbol_key=rec.get("symbol_key")
        if symbol_key is not None:
            endpoint_symbol_buckets[symbol_key].append(record_index)
        px,py=rec["point"]
        cell=(math.floor(float(px)/endpoint_cell),math.floor(float(py)/endpoint_cell))
        endpoint_cells.append(cell)
        endpoint_spatial_buckets[cell].append(record_index)

    forced_endpoint_offsets={}
    for record_index,rec in enumerate(endpoint_records):
        peers={rec["cable"]}
        candidates=set(endpoint_symbol_buckets.get(rec.get("symbol_key"),())) if rec.get("symbol_key") is not None else set()
        cell_x,cell_y=endpoint_cells[record_index]
        for grid_x in range(cell_x-1,cell_x+2):
            for grid_y in range(cell_y-1,cell_y+2):
                candidates.update(endpoint_spatial_buckets.get((grid_x,grid_y),()))
        for other_index in candidates:
            other=endpoint_records[other_index]
            if other is rec or other["cable"]==rec["cable"]:
                continue
            if same_endpoint_anchor(rec,other) and same_departure(rec,other):
                peers.add(other["cable"])
        if len(peers)<2:
            continue
        order=sorted(peers,key=lambda ci:stable_keys[ci])
        lane_index=order.index(rec["cable"])
        lane=lane_index-(len(order)-1)/2.0
        peer_ids=[str(getattr(cable_list[ci],"cable_id","") or "Kabel") for ci in order]
        forced_endpoint_offsets[(rec["cable"],bool(rec["at_start"]))]=(lane*gap,lane_index,len(order),peer_ids)
        meta=metadata[id(cable_list[rec["cable"]])]
        if len(order)>int(meta.get("max_parallel",1)):
            meta.update({
                "lane_index":lane_index,"lane_count":len(order),"lane_offset":lane*gap,
                "max_parallel":len(order),"peer_ids":peer_ids,
            })

    # Propagér den tvungne bane gennem den rette afgangs-/ankomststrækning.
    # Det gør fan-out robust selv hvis samme rute er opdelt i flere små,
    # kollineære segmenter hos det ene kabel. Ved første reelle drejning stopper
    # tvangen; derfra tager den almindelige overlapdetektion over.
    collinear_cos=math.cos(math.radians(3.0))
    for (ci,at_start),rec in forced_endpoint_offsets.items():
        offset,lane_index,count,peer_ids=rec
        pts,seg_indices=per_cable[ci]
        if len(pts)<2:
            continue
        ordered=range(0,len(pts)-1) if at_start else range(len(pts)-2,-1,-1)
        base_u=None
        for si in ordered:
            idx=seg_indices[si] if si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            if info is None:
                continue
            u=info["u"] if at_start else (-info["u"][0],-info["u"][1])
            if base_u is None:
                base_u=u
            elif u[0]*base_u[0]+u[1]*base_u[1] < collinear_cos:
                break
            current=offsets_by_segment.get((ci,si))
            # Et større allerede detekteret bundt bevares; ellers er det fysiske
            # endepunktsbundt mere autoritativt end fuzzy segmentmatching.
            if current is None or int(current[2]) <= int(count):
                offsets_by_segment[(ci,si)]=(offset,lane_index,count,peer_ids)

    for meta in metadata.values():
        meta.pop("_best_length",None)

    for ci,(pts,seg_indices) in enumerate(per_cable):
        if len(pts)<2:continue
        seg_infos=[]; seg_offsets=[]
        for si in range(len(pts)-1):
            idx=seg_indices[si] if si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            seg_infos.append(info)
            rec=offsets_by_segment.get((ci,si))
            seg_offsets.append(float(rec[0]) if rec is not None else 0.0)
        if not any(abs(d)>1e-12 for d in seg_offsets):continue

        def shifted_on_segment(si, point):
            info=seg_infos[si]; d=seg_offsets[si]
            if info is None or abs(d)<=1e-12:return (float(point[0]),float(point[1]))
            nx,ny=info["n"]
            return (float(point[0])+nx*d,float(point[1])+ny*d)

        anchor_indices={int(r.get("point_index",-1)) for r in cable_symbol_connections(cable_list[ci])}
        interior=[]
        for vi in range(1,len(pts)-1):
            prev=seg_infos[vi-1]; nxt=seg_infos[vi]
            pa=shifted_on_segment(vi-1,pts[vi]); pb=shifted_on_segment(vi,pts[vi])
            dprev=seg_offsets[vi-1]; dnext=seg_offsets[vi]
            if vi in anchor_indices:
                # Fysiske mellemtilslutninger må aldrig flyttes kosmetisk væk
                # fra symbolet. Banen fletter derfor ind til det rigtige anker
                # og fanner ud igen efter symbolet.
                vx,vy=pts[vi]
                if prev is not None and abs(dprev)>1e-12:
                    f=min(fan,prev["length"]*.35)
                    interior.append((vx-prev["u"][0]*f+prev["n"][0]*dprev,
                                     vy-prev["u"][1]*f+prev["n"][1]*dprev))
                interior.append((vx,vy))
                if nxt is not None and abs(dnext)>1e-12:
                    f=min(fan,nxt["length"]*.35)
                    interior.append((vx+nxt["u"][0]*f+nxt["n"][0]*dnext,
                                     vy+nxt["u"][1]*f+nxt["n"][1]*dnext))
                continue
            hit=_line_intersection(pa,prev["u"],pb,nxt["u"]) if prev is not None and nxt is not None else None
            if hit is not None:
                interior.append(hit); continue
            if prev is not None and nxt is not None and abs(dprev-dnext)>1e-12:
                f=min(fan,prev["length"]*.25,nxt["length"]*.25)
                vx,vy=pts[vi]
                p1=(vx-prev["u"][0]*f+prev["n"][0]*dprev,
                    vy-prev["u"][1]*f+prev["n"][1]*dprev)
                p2=(vx+nxt["u"][0]*f+nxt["n"][0]*dnext,
                    vy+nxt["u"][1]*f+nxt["n"][1]*dnext)
                interior.extend((p1,p2))
            else:
                interior.append(((pa[0]+pb[0])*.5,(pa[1]+pb[1])*.5))

        out=[pts[0]]
        first=seg_infos[0]; d0=seg_offsets[0]
        if first is not None and abs(d0)>1e-12:
            f=min(fan,first["length"]*.35)
            ux,uy=first["u"]; nx,ny=first["n"]
            out.append((pts[0][0]+ux*f+nx*d0,pts[0][1]+uy*f+ny*d0))
        out.extend(interior)
        last=seg_infos[-1]; dn=seg_offsets[-1]
        if last is not None and abs(dn)>1e-12:
            f=min(fan,last["length"]*.35)
            ux,uy=last["u"]; nx,ny=last["n"]
            out.append((pts[-1][0]-ux*f+nx*dn,pts[-1][1]-uy*f+ny*dn))
        out.append(pts[-1])

        clean=[]
        for q in out:
            q=(float(q[0]),float(q[1]))
            if not clean or math.hypot(q[0]-clean[-1][0],q[1]-clean[-1][1])>1e-9:
                clean.append(q)
        result[id(cable_list[ci])]=clean

    groups=sorted(group_candidates.values(),key=lambda g:(-int(g["count"]),-float(g["length"]),tuple(g["cable_ids"])))
    return result, metadata, groups


def cable_visual_paths(cables, lane_gap: float, *, tolerance: float | None=None, fan_length: float | None=None):
    """Backward-compatible visual path helper."""
    return cable_visual_layout(cables,lane_gap,tolerance=tolerance,fan_length=fan_length)[0]
