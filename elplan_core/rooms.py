"""Rumgeometri, rumtekster og rumfordelt kabellængde."""

from __future__ import annotations

import math

from elplan_core.cables.connections import cable_symbol_connections
from elplan_core.cables.sections import cable_spec_section_at_segment


def room_polygon_centroid(points) -> tuple[float, float]:
    pts=[(float(x),float(y)) for x,y in (points or [])]
    if not pts:
        return 0.0,0.0
    if len(pts)<3:
        return sum(x for x,_ in pts)/len(pts),sum(y for _,y in pts)/len(pts)
    area2=0.0; cx=0.0; cy=0.0
    for i,(x1,y1) in enumerate(pts):
        x2,y2=pts[(i+1)%len(pts)]
        cross=x1*y2-x2*y1
        area2+=cross; cx+=(x1+x2)*cross; cy+=(y1+y2)*cross
    if abs(area2)<1e-9:
        return sum(x for x,_ in pts)/len(pts),sum(y for _,y in pts)/len(pts)
    return cx/(3.0*area2),cy/(3.0*area2)


def room_contains_point(room, x: float, y: float) -> bool:
    """Ray-casting point-in-polygon including points on the boundary."""
    pts=list(getattr(room,"points",[]) or [])
    if len(pts)<3:return False
    px=float(x); py=float(y); inside=False
    eps=1e-7
    for i,(ax,ay) in enumerate(pts):
        bx,by=pts[(i+1)%len(pts)]
        ax=float(ax); ay=float(ay); bx=float(bx); by=float(by)
        dx=bx-ax; dy=by-ay
        cross=(px-ax)*dy-(py-ay)*dx
        if abs(cross)<=eps*max(1.0,abs(dx)+abs(dy)):
            dot=(px-ax)*(px-bx)+(py-ay)*(py-by)
            if dot<=eps:return True
        if (ay>py)!=(by>py):
            xin=ax+(py-ay)*(bx-ax)/(by-ay)
            if px < xin:inside=not inside
    return inside


def room_for_point(rooms, x: float, y: float):
    """Returnér det mindste rum som indeholder punktet ved overlap."""
    hits=[]
    for room in rooms or []:
        if room_contains_point(room,x,y):
            pts=list(getattr(room,"points",[]) or [])
            area=0.0
            for i,(x1,y1) in enumerate(pts):
                x2,y2=pts[(i+1)%len(pts)]; area+=float(x1)*float(y2)-float(x2)*float(y1)
            hits.append((abs(area)*0.5,room))
    return min(hits,key=lambda row:row[0])[1] if hits else None


def room_display_text(room) -> str:
    code=str(getattr(room,"code","") or "").strip()
    name=str(getattr(room,"name","") or "").strip()
    return f"{code} · {name}" if code and name else (name or code or "Rum")


def room_output_label(room, show_code: bool = False) -> str:
    """Rumnavn til planvisning/udskrift med valgfri separat rummærkning."""
    code=str(getattr(room,"code","") or "").strip()
    name=str(getattr(room,"name","") or "").strip()
    if bool(show_code) and code:
        return f"{code} · {name}" if name else code
    return name or "Rum"


def _segment_edge_intersection_t(a, b, c, d, eps: float = 1e-9):
    """Returnér t på segment a→b hvor det skærer c→d, ellers None.

    Kollineære kanter behøver ikke særlige t-værdier: interval-midtpunkterne
    bliver stadig klassificeret af ``room_for_point`` og grænsen tæller som
    inde i et rum.
    """
    ax,ay=map(float,a); bx,by=map(float,b); cx,cy=map(float,c); dx,dy=map(float,d)
    rx=bx-ax; ry=by-ay; sx=dx-cx; sy=dy-cy
    den=rx*sy-ry*sx
    if abs(den)<=eps:return None
    qx=cx-ax; qy=cy-ay
    t=(qx*sy-qy*sx)/den; u=(qx*ry-qy*rx)/den
    if -eps<=t<=1.0+eps and -eps<=u<=1.0+eps:return min(1.0,max(0.0,t))
    return None


def rooms_along_polyline(rooms, points):
    """Rum som en polyline faktisk løber igennem, i rutens rækkefølge.

    Der samples mellem præcise skæringer med rumgrænser i stedet for på en
    fast afstand. Det gør resultatet uafhængigt af tegningens målestok og
    fanger også små rum. Kun rum som kablet har et reelt interval i medtages;
    et enkelt tangent-berøringspunkt skaber derfor ikke en falsk rummærkning.
    """
    pts=[(float(x),float(y)) for x,y in (points or [])]
    room_list=list(rooms or [])
    if not room_list or not pts:return []
    if len(pts)==1:
        hit=room_for_point(room_list,*pts[0]); return [hit] if hit is not None else []
    out=[]
    for p0,p1 in zip(pts,pts[1:]):
        if abs(p1[0]-p0[0])+abs(p1[1]-p0[1])<=1e-12:continue
        cuts=[0.0,1.0]
        for room in room_list:
            poly=list(getattr(room,'points',[]) or [])
            if len(poly)<3:continue
            for i,q0 in enumerate(poly):
                q1=poly[(i+1)%len(poly)]
                t=_segment_edge_intersection_t(p0,p1,q0,q1)
                if t is not None:cuts.append(float(t))
        cuts=sorted(cuts)
        uniq=[]
        for t in cuts:
            if not uniq or abs(t-uniq[-1])>1e-8:uniq.append(t)
        for ta,tb in zip(uniq,uniq[1:]):
            if tb-ta<=1e-8:continue
            t=(ta+tb)*0.5
            x=p0[0]+(p1[0]-p0[0])*t; y=p0[1]+(p1[1]-p0[1])*t
            room=room_for_point(room_list,x,y)
            if room is not None and (not out or getattr(out[-1],'uid',None)!=getattr(room,'uid',None)):
                out.append(room)
    return out


def cable_rooms(cable, rooms):
    return rooms_along_polyline(rooms,getattr(cable,'points',[]) or [])


def polyline_room_lengths(points, rooms):
    """Fordel en polylines geometriske længde på rum og areal uden rum.

    Resultatet er ``{room_uid: længde, None: længde_uden_rum}`` i tegneenheder.
    Segmenter deles ved præcise skæringer med rumgrænser, så funktionen kan
    bruges til en rumfiltreret kabel-BOM uden at tælle et helt kabel i hvert
    rum, det blot passerer igennem.
    """
    pts=[(float(x),float(y)) for x,y in (points or [])]
    room_list=list(rooms or [])
    totals={}
    for p0,p1 in zip(pts,pts[1:]):
        seg_len=math.hypot(p1[0]-p0[0],p1[1]-p0[1])
        if seg_len<=1e-12:continue
        cuts=[0.0,1.0]
        for room in room_list:
            poly=list(getattr(room,'points',[]) or [])
            if len(poly)<3:continue
            for i,q0 in enumerate(poly):
                q1=poly[(i+1)%len(poly)]
                t=_segment_edge_intersection_t(p0,p1,q0,q1)
                if t is not None:cuts.append(float(t))
        cuts=sorted(cuts); uniq=[]
        for t in cuts:
            if not uniq or abs(t-uniq[-1])>1e-8:uniq.append(t)
        for ta,tb in zip(uniq,uniq[1:]):
            if tb-ta<=1e-8:continue
            tm=(ta+tb)*0.5
            x=p0[0]+(p1[0]-p0[0])*tm; y=p0[1]+(p1[1]-p0[1])*tm
            room=room_for_point(room_list,x,y) if room_list else None
            key=str(getattr(room,'uid','') or '') if room is not None else None
            totals[key]=totals.get(key,0.0)+seg_len*(tb-ta)
    return totals


def cable_room_length_metres(cable, rooms, room_uid: str | None, metres_per_unit: float | None, reserve_percent: float = 0.0):
    """Kabellængde som fysisk ligger i ét valgt rum (eller uden for alle rum)."""
    if metres_per_unit is None or float(metres_per_unit)<=0:return None
    key=str(room_uid or '').strip() or None
    base=float(polyline_room_lengths(getattr(cable,'points',[]) or [],rooms).get(key,0.0))*float(metres_per_unit)
    return base*(1.0+max(0.0,float(reserve_percent))/100.0)


def cable_length_by_spec_room_metres(cable, rooms, room_uid: str | None, metres_per_unit: float | None):
    """Som ``cable_length_by_spec_metres``, men kun for den del der ligger i valgt rum."""
    if metres_per_unit is None or float(metres_per_unit)<=0:return None
    pts=[(float(x),float(y)) for x,y in (getattr(cable,'points',[]) or [])]
    room_list=list(rooms or []); wanted=str(room_uid or '').strip() or None; factor=float(metres_per_unit)
    default=str(getattr(cable,'cable_spec','') or '').strip() or '—'; totals={}
    for index,(p0,p1) in enumerate(zip(pts,pts[1:])):
        seg_len=math.hypot(p1[0]-p0[0],p1[1]-p0[1])
        if seg_len<=1e-12:continue
        cuts=[0.0,1.0]
        for room in room_list:
            poly=list(getattr(room,'points',[]) or [])
            if len(poly)<3:continue
            for i,q0 in enumerate(poly):
                q1=poly[(i+1)%len(poly)]
                t=_segment_edge_intersection_t(p0,p1,q0,q1)
                if t is not None:cuts.append(float(t))
        cuts=sorted(cuts); uniq=[]
        for t in cuts:
            if not uniq or abs(t-uniq[-1])>1e-8:uniq.append(t)
        section=cable_spec_section_at_segment(cable,index)
        spec=str((section or {}).get('cable_spec') or default).strip() or '—'
        for ta,tb in zip(uniq,uniq[1:]):
            if tb-ta<=1e-8:continue
            tm=(ta+tb)*0.5
            x=p0[0]+(p1[0]-p0[0])*tm; y=p0[1]+(p1[1]-p0[1])*tm
            room=room_for_point(room_list,x,y) if room_list else None
            key=str(getattr(room,'uid','') or '') if room is not None else None
            if key!=wanted:continue
            totals[spec]=totals.get(spec,0.0)+seg_len*(tb-ta)*factor
    return totals


def cable_room_marking(cable, rooms, style: str = 'name', separator: str = ' → ') -> str:
    """Forslag til *ekstra kabelmærkning* baseret på gennemløbte rum.

    Funktionen ændrer aldrig kabelobjektet og rører dermed hverken ``cable_id``
    eller ``circuit_id``. Gentagne rum samles i første rute-rækkefølge, så en
    kabelrute der kort forlader og genindtræder i samme rum ikke bliver støjende.
    """
    seen=set(); ordered=[]
    for room in cable_rooms(cable,rooms):
        uid=str(getattr(room,'uid','') or id(room))
        if uid in seen:continue
        seen.add(uid); ordered.append(room)
    def caption(room):
        name=str(getattr(room,'name','') or '').strip()
        code=str(getattr(room,'code','') or '').strip()
        if style=='code':return code or name or 'Rum'
        if style=='display':return room_display_text(room)
        return name or code or 'Rum'
    return str(separator).join(caption(room) for room in ordered)


def cable_light_endpoint_marking(cable, placements, separator: str = ' → ') -> str:
    """Forslag fra *lampestedernes egne mærkninger* på et fysisk kabel.

    Bruges som fallback/alternativ til rumbaserede forslag. Kun fysiske
    ``light_connection``-endepunkter tæller, og kun ``Placement.label`` bruges;
    gruppe/kreds indgår aldrig i resultatet. Funktionen ændrer ingen data.
    """
    by_uid={str(getattr(p,'uid','') or ''):p for p in (placements or [])}
    rows=sorted(cable_symbol_connections(cable),key=lambda r:int(r.get('point_index',0) or 0))
    if len(rows)<2:return ''
    first=by_uid.get(str(rows[0].get('symbol_uid','') or ''))
    last=by_uid.get(str(rows[-1].get('symbol_uid','') or ''))
    if first is None or last is None:return ''
    if str(getattr(first,'symbol','') or '')!='light_connection' or str(getattr(last,'symbol','') or '')!='light_connection':return ''
    a=str(getattr(first,'label','') or '').strip()
    b=str(getattr(last,'label','') or '').strip()
    if a and b:
        return a if a==b else f"{a}{separator}{b}"
    return a or b
