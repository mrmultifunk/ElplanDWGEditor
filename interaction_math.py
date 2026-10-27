from __future__ import annotations


def wheel_zoom_factor(angle_y: float = 0.0, pixel_y: float = 0.0, base: float = 1.18) -> float | None:
    """Return a zoom factor for a *vertical* wheel gesture.

    Qt can emit wheel events with a zero vertical angle delta, for example for
    horizontal scrolling, touchpad phase begin/end events or driver-generated
    synthetic events. Those events must never be interpreted as zoom-out.

    Traditional mouse wheels use ``angle_y`` (normally +/-120 per notch). High
    resolution touchpads may instead use ``pixel_y``. Pixel scrolling is mapped
    to a smooth fractional zoom step while a classic wheel notch keeps the
    established 1.18x behaviour.
    """
    try:
        ay = float(angle_y)
    except (TypeError, ValueError):
        ay = 0.0
    try:
        py = float(pixel_y)
    except (TypeError, ValueError):
        py = 0.0

    if abs(ay) > 1e-9:
        return float(base) if ay > 0.0 else 1.0 / float(base)

    if abs(py) > 1e-9:
        # 120 screen pixels corresponds roughly to one classic wheel notch.
        # Clamp a single event to one step so a driver spike cannot jump the view.
        step = max(-1.0, min(1.0, py / 120.0))
        return float(base) ** step

    return None


def axis_alignment_snap(x: float, y: float, candidates, tolerance: float):
    """Snap X and Y independently to the nearest candidate coordinate.

    Returns ``(snapped_x, snapped_y, guide_x, guide_y)``. ``guide_x`` and
    ``guide_y`` are ``None`` when that axis did not snap.  Keeping this helper
    independent of Qt makes the CAD-style alignment behaviour regression-testable.
    """
    try:
        x=float(x); y=float(y); tol=max(0.0,float(tolerance))
    except (TypeError, ValueError):
        return float(x), float(y), None, None
    best_x=None; best_y=None
    best_dx=float("inf"); best_dy=float("inf")
    for point in candidates or ():
        try:
            px=float(point[0]); py=float(point[1])
        except (TypeError, ValueError, IndexError):
            continue
        dx=abs(px-x); dy=abs(py-y)
        if dx <= tol and dx < best_dx:
            best_dx=dx; best_x=px
        if dy <= tol and dy < best_dy:
            best_dy=dy; best_y=py
    return (best_x if best_x is not None else x,
            best_y if best_y is not None else y,
            best_x, best_y)


def spot_row_axis_assist(x: float, y: float, start, tolerance: float, disabled: bool = False):
    """Soft 0/90-degree snapping for a spot row endpoint.

    The row remains freely diagonal outside the screen-scaled tolerance.  When
    both axes are close (normally only very near the start point), the nearest
    axis wins so the endpoint is never snapped onto the start on both axes.
    ``disabled`` is used for Alt = free angle.

    Returns ``(x, y, guide_x, guide_y, label)``.
    """
    try:
        x=float(x); y=float(y); sx=float(start[0]); sy=float(start[1]); tol=max(0.0,float(tolerance))
    except (TypeError, ValueError, IndexError):
        return x, y, None, None, ""
    if disabled:
        return x, y, None, None, ""
    dx=abs(x-sx)
    dy=abs(y-sy)
    vertical=dx <= tol
    horizontal=dy <= tol
    if vertical and horizontal:
        # Snap only one axis; choose the smaller perpendicular correction.
        if dy <= dx:
            return x, sy, None, sy, "VANDRET"
        return sx, y, sx, None, "LODRET"
    if horizontal:
        return x, sy, None, sy, "VANDRET"
    if vertical:
        return sx, y, sx, None, "LODRET"
    return x, y, None, None, ""


def room_axis_assist(x: float, y: float, anchors, tolerance: float, disabled: bool = False):
    """Soft horizontal/vertical assistance for room polygon editing.

    ``anchors`` contains the neighbouring room vertices.  X and Y are snapped
    independently when the cursor is within ``tolerance`` of an anchor axis.
    This keeps rectangles easy to draw while still allowing arbitrary diagonal
    geometry simply by moving outside the tolerance.  ``disabled`` is used for
    the explicit Alt = free-angle override.

    Returns ``(x, y, guide_x, guide_y, label)`` where ``guide_x`` means a
    vertical alignment and ``guide_y`` a horizontal alignment.
    """
    if disabled:
        try:
            return float(x), float(y), None, None, ""
        except (TypeError, ValueError):
            return x, y, None, None, ""
    sx, sy, gx, gy = axis_alignment_snap(x, y, anchors, tolerance)
    labels=[]
    if gy is not None:
        labels.append("VANDRET")
    if gx is not None:
        labels.append("LODRET")
    return sx, sy, gx, gy, " · ".join(labels)

def room_wall_axis_snap(raw_x: float, raw_y: float, anchor, segment, tolerance: float, disabled: bool = False):
    """Combine CAD-wall snap with soft room 0/90-degree assistance.

    ``segment`` is one physical CAD wall line ``(x1,y1,x2,y2)`` and ``anchor``
    is the neighbouring room vertex.  The returned point is *always on the
    wall segment*.  When the cursor is close enough to the wall/axis
    intersection the endpoint is moved to that intersection, allowing a room
    edge to remain exactly horizontal/vertical while also snapping to the CAD
    wall.  ``Alt``/``disabled`` leaves the regular wall snap untouched.

    Returns ``(x, y, guide_x, guide_y, label)`` or ``None`` when no combined
    wall+axis candidate is close enough.
    """
    if disabled:
        return None
    try:
        rx=float(raw_x); ry=float(raw_y); ax=float(anchor[0]); ay=float(anchor[1])
        x1,y1,x2,y2=map(float,segment[:4]); tol=max(0.0,float(tolerance))
    except (TypeError,ValueError,IndexError):
        return None
    dx=x2-x1; dy=y2-y1
    candidates=[]

    # Horizontal room edge: y = anchor.y, endpoint constrained to the wall.
    if abs(dy) > 1e-12:
        t=(ay-y1)/dy
        if -1e-9 <= t <= 1.0+1e-9:
            t=max(0.0,min(1.0,t)); candidates.append((x1+t*dx,ay,None,ay,'VANDRET'))
    elif abs(y1-ay) <= tol:
        # Wall itself is horizontal and coincident with the desired axis.
        den=dx*dx
        t=0.0 if den <= 1e-18 else ((rx-x1)*dx)/den
        t=max(0.0,min(1.0,t)); candidates.append((x1+t*dx,ay,None,ay,'VANDRET'))

    # Vertical room edge: x = anchor.x, endpoint constrained to the wall.
    if abs(dx) > 1e-12:
        t=(ax-x1)/dx
        if -1e-9 <= t <= 1.0+1e-9:
            t=max(0.0,min(1.0,t)); candidates.append((ax,y1+t*dy,ax,None,'LODRET'))
    elif abs(x1-ax) <= tol:
        den=dy*dy
        t=0.0 if den <= 1e-18 else ((ry-y1)*dy)/den
        t=max(0.0,min(1.0,t)); candidates.append((ax,y1+t*dy,ax,None,'LODRET'))

    if not candidates:
        return None
    best=min(candidates,key=lambda q:(q[0]-rx)**2+(q[1]-ry)**2)
    if ((best[0]-rx)**2+(best[1]-ry)**2)**0.5 > tol:
        return None
    return best

def room_nearest_edge_insert(points, scene_x: float, scene_y: float):
    """Return (insert_index, cad_point) on the room edge nearest a scene point."""
    pts=[]
    for point in points or ():
        try:pts.append((float(point[0]),float(point[1])))
        except (TypeError,ValueError,IndexError):continue
    if len(pts)<2:return None
    try:px,py=float(scene_x),float(scene_y)
    except (TypeError,ValueError):return None
    best=None
    for i,(ax_cad,ay_cad) in enumerate(pts):
        bx_cad,by_cad=pts[(i+1)%len(pts)]
        ax,ay=ax_cad,-ay_cad; bx,by=bx_cad,-by_cad
        vx,vy=bx-ax,by-ay; denom=vx*vx+vy*vy
        t=0.0 if denom<=1e-18 else max(0.0,min(1.0,((px-ax)*vx+(py-ay)*vy)/denom))
        qx,qy=ax+t*vx,ay+t*vy; dist2=(px-qx)**2+(py-qy)**2
        candidate=(dist2,i+1,(float(qx),float(-qy)))
        if best is None or candidate[0]<best[0]:best=candidate
    return (best[1],best[2]) if best is not None else None

