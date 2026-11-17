"""Qt-uafhængig geometri for kabelruter."""

from __future__ import annotations

import math

from elplan_core.cables.connections import normalize_cable_symbol_connections
from elplan_core.models import CablePlacement


def cable_route_points_to(start, end, orthogonal: bool = False) -> list[tuple[float, float]]:
    """Return points to append from ``start`` to ``end`` for the chosen route mode.

    Free/diagonal routing is a direct segment. Orthogonal routing keeps the
    legacy dominant-axis-first L shape. The helper is GUI-independent so the
    exact drawing behaviour can be regression-tested without Qt.
    """
    end=(float(end[0]),float(end[1]))
    if start is None or not orthogonal:
        return [end]
    start=(float(start[0]),float(start[1]))
    dx=abs(end[0]-start[0]); dy=abs(end[1]-start[1])
    if dx < 1e-9 or dy < 1e-9:
        return [end]
    if dx >= dy:
        return [(end[0],start[1]),end]
    return [(start[0],end[1]),end]


def convert_cable_route_mode_geometry(points, connections=None, *, from_orthogonal: bool, to_orthogonal: bool):
    """Convert an existing cable centreline when its routing mode changes.

    The editor historically stored only the rendered polyline, not which
    orthogonal vertices were inserted automatically.  For old 90° cables we
    therefore reconstruct the most likely user waypoints segment-by-segment:
    an unconnected L-corner between two points is treated as the automatic
    elbow, while endpoints and physical symbol connections are always kept.

    Returning remapped ``symbol_connections`` keeps PL boxes and other physical
    cable endpoints attached to the same logical waypoint after conversion.
    The function is intentionally Qt-independent so route conversion is fully
    regression-testable.
    """
    pts=[(float(p[0]),float(p[1])) for p in (points or []) if isinstance(p,(list,tuple)) and len(p)>=2]
    records=normalize_cable_symbol_connections(connections or [],len(pts))
    if len(pts)<2 or bool(from_orthogonal)==bool(to_orthogonal):
        return pts, records

    protected={0,len(pts)-1}
    protected.update(int(r.get("point_index",0) or 0) for r in records)

    def axis(a,b):
        return math.isclose(a[0],b[0],abs_tol=1e-9) or math.isclose(a[1],b[1],abs_tol=1e-9)

    if from_orthogonal and not to_orthogonal:
        # Rebuild likely click/connection waypoints. The legacy orthogonal
        # generator emitted [auto elbow, clicked target] for diagonal spans,
        # and [clicked target] for already-axis-aligned spans.
        kept=[0]
        i=0
        while i < len(pts)-1:
            if i+1 in protected:
                kept.append(i+1); i+=1; continue
            if i+2 < len(pts):
                a,b,c=pts[i],pts[i+1],pts[i+2]
                is_l=(axis(a,b) and axis(b,c) and not axis(a,c))
                if is_l and (i+1 not in protected):
                    kept.append(i+2); i+=2; continue
            kept.append(i+1); i+=1
        # Deduplicate while preserving order; protected connection points are
        # never discarded by the loop above.
        ordered=[]; seen=set()
        for idx in kept:
            if idx not in seen:
                ordered.append(idx); seen.add(idx)
        new_pts=[pts[idx] for idx in ordered]
        index_map={old:new for new,old in enumerate(ordered)}
    else:
        # Free -> 90°: every existing vertex is an intentional waypoint. Insert
        # at most one elbow between each pair and keep an exact old->new map.
        new_pts=[pts[0]]
        index_map={0:0}
        for old_idx,target in enumerate(pts[1:],start=1):
            for point in cable_route_points_to(new_pts[-1],target,True):
                if math.hypot(point[0]-new_pts[-1][0],point[1]-new_pts[-1][1])>1e-9:
                    new_pts.append(point)
            index_map[old_idx]=len(new_pts)-1

    remapped=[]
    for row in records:
        old_idx=int(row.get("point_index",0) or 0)
        if old_idx not in index_map:
            # Defensive fallback. Protected connection points should always be
            # present, but nearest coordinate keeps corrupted legacy data safe.
            target=pts[max(0,min(old_idx,len(pts)-1))]
            new_idx=min(range(len(new_pts)),key=lambda j:math.hypot(new_pts[j][0]-target[0],new_pts[j][1]-target[1]))
        else:
            new_idx=index_map[old_idx]
        rec=dict(row); rec["point_index"]=int(new_idx); remapped.append(rec)
    return new_pts, normalize_cable_symbol_connections(remapped,len(new_pts))


def polyline_length(points) -> float:
    """Geometric length of a CAD polyline in drawing units."""
    total = 0.0
    pts = [(float(p[0]), float(p[1])) for p in (points or [])]
    for a, b in zip(pts, pts[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total


def _clean_polyline_points(points, tol=1e-9):
    """Fjern dubletter og rent kollineære mellemknæk fra en polyline."""
    pts=[]
    for q in points:
        q=(float(q[0]),float(q[1]))
        if not pts or math.hypot(q[0]-pts[-1][0],q[1]-pts[-1][1])>tol:
            pts.append(q)
    changed=True
    while changed and len(pts)>=3:
        changed=False; out=[pts[0]]
        for i in range(1,len(pts)-1):
            a=out[-1]; b=pts[i]; c=pts[i+1]
            same_x=abs(a[0]-b[0])<=tol and abs(b[0]-c[0])<=tol
            same_y=abs(a[1]-b[1])<=tol and abs(b[1]-c[1])<=tol
            if same_x or same_y:
                changed=True; continue
            out.append(b)
        out.append(pts[-1]); pts=out
    return pts


def move_polyline_vertex(points, index: int, target, orthogonal=False):
    """Flyt et knækpunkt. Ortogonal routing bevarer 90° ved at lave et lille dogleg."""
    pts=[(float(x),float(y)) for x,y in points]
    if not (0 < index < len(pts)-1): return pts
    q=(float(target[0]),float(target[1]))
    if not orthogonal:
        pts[index]=q; return _clean_polyline_points(pts)
    a=pts[index-1]; old=pts[index]; c=pts[index+1]
    prev_h=abs(old[0]-a[0]) >= abs(old[1]-a[1])
    if prev_h:
        p1=(q[0],a[1]); p2=(c[0],q[1])
    else:
        p1=(a[0],q[1]); p2=(q[0],c[1])
    return _clean_polyline_points(pts[:index] + [p1,q,p2] + pts[index+1:])


def constrain_polyline_target_to_locked_neighbors(points, index: int, target, locked_indices=None, orthogonal=False):
    """Legacy-kompatibel målbegrænsning.

    Fra 0.43.3 låses frie kabelknæk ikke længere til en akse blot fordi deres
    nabo er en fysisk symboltilslutning. I stedet bevarer redigeringsalgoritmen
    ankeret og indsætter om nødvendigt et ekstra 90°-knæk. Funktionen returnerer
    derfor målet uændret og beholdes kun for ældre kald/tests.
    """
    return (float(target[0]), float(target[1]))


def _axis_aligned(a, b, tol=1e-9):
    return abs(float(a[0])-float(b[0])) <= tol or abs(float(a[1])-float(b[1])) <= tol


def move_polyline_vertex_flexible(points, index: int, target, orthogonal=False):
    """Flyt ét frit ruteknæk uden at flytte naboerne.

    I 90°-tilstand kan et knæk ligge mellem to fysiske symbolankre. I stedet for
    at fryse knækket indsættes automatisk ét eller to lokale dogleg-punkter, så
    brugeren kan trække ruten frit mens nabopunkterne bliver stående.

    Returnerer ``(nye_punkter, nyt_indeks_for_det_trukne_punkt, delta)`` hvor
    ``delta`` er ændringen i antal punkter efter det oprindelige indeks. Det gør
    det muligt at forskyde gemte symbolforbindelsesindeks sikkert.
    """
    pts=[(float(x),float(y)) for x,y in points]
    index=int(index)
    if not (0 < index < len(pts)-1):
        return pts, index, 0
    q=(float(target[0]),float(target[1]))
    if not orthogonal:
        pts[index]=q
        return pts,index,0

    prev=pts[index-1]; old=pts[index]; nxt=pts[index+1]
    prev_h=abs(old[0]-prev[0]) >= abs(old[1]-prev[1])
    next_h=abs(nxt[0]-old[0]) >= abs(nxt[1]-old[1])
    replacement=[]

    # Bevar retningen på segmentet ind mod knækket, men lad selve målet følge
    # musen. Hvis prev allerede ligger på samme X/Y som målet, er ekstra knæk
    # unødvendigt.
    if not _axis_aligned(prev,q):
        replacement.append((q[0],prev[1]) if prev_h else (prev[0],q[1]))
    q_offset=len(replacement)
    replacement.append(q)
    if not _axis_aligned(q,nxt):
        replacement.append((q[0],nxt[1]) if next_h else (nxt[0],q[1]))

    moved=pts[:index] + replacement + pts[index+1:]
    q_index=index+q_offset
    return moved,q_index,len(replacement)-1


def move_polyline_endpoint_flexible(points, index: int, target, orthogonal=False):
    """Flyt et frit kabelendepunkt og bevar nabopunktet som fast geometri.

    Hvis 90°-føring kræver det, indsættes ét lokalt hjørne i stedet for at
    begrænse endepunktet til samme X/Y som nabopunktet.
    """
    pts=[(float(x),float(y)) for x,y in points]
    index=int(index)
    if len(pts)<2 or index not in (0,len(pts)-1):
        return pts,index,0
    q=(float(target[0]),float(target[1]))
    if not orthogonal:
        pts[index]=q
        return pts,index,0

    if index==0:
        old=pts[0]; nxt=pts[1]
        if _axis_aligned(q,nxt):
            return [q]+pts[1:],0,0
        was_h=abs(nxt[0]-old[0]) >= abs(nxt[1]-old[1])
        # q -> elbow -> nxt. Retningen ind mod nxt følger det oprindelige segment.
        elbow=(q[0],nxt[1]) if was_h else (nxt[0],q[1])
        return [q,elbow]+pts[1:],0,1

    old=pts[-1]; prev=pts[-2]
    if _axis_aligned(prev,q):
        return pts[:-1]+[q],len(pts)-1,0
    was_h=abs(old[0]-prev[0]) >= abs(old[1]-prev[1])
    elbow=(q[0],prev[1]) if was_h else (prev[0],q[1])
    moved=pts[:-1]+[elbow,q]
    return moved,len(moved)-1,1


def move_polyline_vertex_stable(points, index: int, target, orthogonal=False, locked_indices=None):
    """Kompatibilitetswrapper for ældre kode.

    Funktionen tillader nu fri redigering og kan derfor ændre antallet af lokale
    geometripunkter. Nye GUI-kald bruger ``move_polyline_vertex_flexible``
    direkte for også at remappe symbolforbindelsesindeks.
    """
    moved,_q_index,_delta=move_polyline_vertex_flexible(points,index,target,orthogonal)
    return moved


def move_polyline_endpoint(points, index: int, target, orthogonal=False, locked_indices=None):
    """Flyt et frit kabelendepunkt; 90°-føring opretter om nødvendigt et dogleg."""
    moved,_q_index,_delta=move_polyline_endpoint_flexible(points,index,target,orthogonal)
    return _clean_polyline_points(moved) if not locked_indices else moved


def move_polyline_endpoint_stable(points, index: int, target, orthogonal=False, locked_indices=None):
    """Kompatibilitetswrapper for fri endpoint-redigering med faste ankre."""
    moved,_q_index,_delta=move_polyline_endpoint_flexible(points,index,target,orthogonal)
    return moved


def rotate_point(x: float, y: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return x * ca - y * sa, x * sa + y * ca


def polyline_label_point(points) -> tuple[float,float]:
    """Placér en mærkning midt på det længste segment i en vilkårlig polyline."""
    pts=[(float(p[0]),float(p[1])) for p in (points or [])]
    if not pts:return (0.0,0.0)
    if len(pts)==1:return pts[0]
    best=(pts[0],pts[1]); best_len=-1.0
    for a,b in zip(pts,pts[1:]):
        d=math.hypot(b[0]-a[0],b[1]-a[1])
        if d>best_len:best=(a,b);best_len=d
    a,b=best; return ((a[0]+b[0])/2,(a[1]+b[1])/2)


def cable_label_point(cable: CablePlacement) -> tuple[float,float]:
    """Placér mærkning midt på det længste logiske kabelsegment."""
    return polyline_label_point(cable.points)
