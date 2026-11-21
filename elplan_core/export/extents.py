"""Visningsudsnit, tegnegrænser og papirplacering."""

from __future__ import annotations

import math

from reportlab.lib.pagesizes import A3, A4, landscape, portrait

from elplan_core.cables.categories import cable_visible_in_layers
from elplan_core.cables.geometry import rotate_point
from elplan_core.constants import FREE_TEXT_LAYER, PRINT_MARGIN_MM, ROOM_LAYER
from elplan_core.models import CADPrimitive
from elplan_core.symbols.clipboard import symbol_layer
from elplan_core.symbols.geometry import symbol_local_bbox


def _primitive_bbox(prim: CADPrimitive):
    """Conservative 2D bbox for a CAD primitive."""
    try:
        if prim.kind == "line":
            x1, y1, x2, y2 = prim.data
            return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if prim.kind in ("circle", "arc"):
            cx, cy, r = prim.data[:3]
            return cx-r, cy-r, cx+r, cy+r
        if prim.kind == "polyline":
            pts = prim.data
            if not pts:
                return None
            xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
            return min(xs), min(ys), max(xs), max(ys)
        if prim.kind == "point":
            x, y = prim.data
            return x, y, x, y
        if prim.kind == "text":
            x, y, text, h, _rot = prim.data
            w = max(float(h) * 0.6 * len(str(text)), float(h))
            return x, y-float(h)*0.25, x+w, y+float(h)
    except Exception:
        return None
    return None


def print_extents(cad_primitives, placements, cables=None, layer_visibility=None, texts=None,
                  rooms=None, room_labels_visible=True, room_boundaries_visible=False):
    """Return bbox for synlig CAD, el, kabler, tekst og rumlag."""
    boxes = []
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
            continue
        b = _primitive_bbox(prim)
        if b:
            boxes.append(b)
    for pl in placements:
        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol), True):
            continue
        # Brug den faktiske vektorgeometri i stedet for en stor, konservativ
        # cirkel omkring symbolet. Den gamle +/- 1,9 * size-boks kunne give
        # meget store tomme margener i PDF/udskrift, især når et symbol lå
        # tæt ved tegningens yderkant.
        x1,y1,x2,y2=symbol_local_bbox(pl.symbol,float(pl.size))
        corners=[rotate_point(x1,y1,pl.rotation),rotate_point(x1,y2,pl.rotation),
                 rotate_point(x2,y1,pl.rotation),rotate_point(x2,y2,pl.rotation)]
        xs=[pl.x+q[0] for q in corners]; ys=[pl.y+q[1] for q in corners]
        boxes.append((min(xs),min(ys),max(xs),max(ys)))
    for cable in cables or []:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        if cable.points:
            xs=[float(q[0]) for q in cable.points]; ys=[float(q[1]) for q in cable.points]
            boxes.append((min(xs),min(ys),max(xs),max(ys)))
    for item in texts or []:
        if layer_visibility is not None and not layer_visibility.get(FREE_TEXT_LAYER, True):
            continue
        h=max(float(item.height),1.0); w=max(h*.6*len(str(item.text)),h)
        # konservativ bbox, også ved rotation
        r=.55*math.hypot(w,h)
        boxes.append((item.x-r,item.y-r,item.x+r,item.y+r))
    room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
    if room_layer_visible:
        for room in rooms or []:
            if room_boundaries_visible:
                pts=list(getattr(room,"points",[]) or [])
                if pts:
                    xs=[float(q[0]) for q in pts]; ys=[float(q[1]) for q in pts]
                    boxes.append((min(xs),min(ys),max(xs),max(ys)))
            if room_labels_visible:
                # Rumnavne er kosmetisk page-space tekst. Ankerpunktet er nok
                # til at få en eventuelt frit flyttet tekst med i helplansudsnittet.
                x=float(getattr(room,"label_x",0.0)); y=float(getattr(room,"label_y",0.0))
                boxes.append((x,y,x,y))
    if not boxes:
        return (0.0, 0.0, 1000.0, 1000.0)
    xmin=min(b[0] for b in boxes); ymin=min(b[1] for b in boxes)
    xmax=max(b[2] for b in boxes); ymax=max(b[3] for b in boxes)
    if xmax <= xmin: xmax = xmin + 1.0
    if ymax <= ymin: ymax = ymin + 1.0
    return xmin, ymin, xmax, ymax


def _quantile(values, q: float):
    vals=sorted(float(v) for v in values)
    if not vals:return 0.0
    if len(vals)==1:return vals[0]
    pos=max(0.0,min(1.0,float(q)))*(len(vals)-1)
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return vals[lo]
    t=pos-lo
    return vals[lo]*(1.0-t)+vals[hi]*t




def _robust_center_range(values, factor: float = 3.0):
    vals=sorted(float(v) for v in values)
    if not vals:
        return 0.0, 0.0
    if len(vals)==1:
        return vals[0], vals[0]
    q1=_quantile(vals,0.25); q3=_quantile(vals,0.75)
    iqr=max(q3-q1,1e-9)
    return q1-factor*iqr, q3+factor*iqr

def fit_view_extents(cad_primitives, placements=None, cables=None, layer_visibility=None, texts=None):
    """Robuste extents til skærmens 'Tilpas visning'.

    Find den dominerende tegningsklynge i stedet for blot at bruge modelspace-
    extents. DWG-filer kan indeholde title blocks, konstruktionselementer,
    referencegeometri eller tekst langt fra selve plantegningen. De elementer
    må ikke få huset til at blive mikroskopisk i editoren. PDF/DWG/DXF-eksport
    påvirkes ikke af denne filtrering.
    """
    geom=[]; text_boxes=[]
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer,True):
            continue
        if prim.kind=="point":
            continue
        b=_primitive_bbox(prim)
        if not b:
            continue
        if prim.kind=="text":
            text_boxes.append(b)
        else:
            geom.append(b)

    if not geom:
        base=print_extents(cad_primitives,placements or [],cables or [],layer_visibility,texts or [])
    else:
        centers=[((b[0]+b[2])*.5,(b[1]+b[3])*.5,b) for b in geom]
        xs=[q[0] for q in centers]; ys=[q[1] for q in centers]
        mx=_quantile(xs,.5); my=_quantile(ys,.5)
        madx=_quantile([abs(x-mx) for x in xs],.5)
        mady=_quantile([abs(y-my) for y in ys],.5)
        # 10-90 %-spændet er fallback for planer, hvor mange centre ligger på
        # samme X/Y. 6 robuste sigma bevarer normal plantegningsgeometri, men
        # fjerner typisk objekter mange rum-/bygningsbredder væk.
        sx=max(madx*1.4826,(_quantile(xs,.90)-_quantile(xs,.10))/2.6,1e-9)
        sy=max(mady*1.4826,(_quantile(ys,.90)-_quantile(ys,.10))/2.6,1e-9)
        dominant=[b for cx,cy,b in centers if abs(cx-mx)<=6.0*sx and abs(cy-my)<=6.0*sy]
        if len(dominant)<max(6,int(len(geom)*.25)):
            dominant=list(geom)

        # En stor tegningsramme kan have centrum midt i huset og derfor bestå
        # centerfilteret. Fjern kun meget ekstreme enkeltprimitiver ift. 90 %-
        # størrelsen; normale lange ydervægge bevares.
        widths=[max(0.0,b[2]-b[0]) for b in dominant]
        heights=[max(0.0,b[3]-b[1]) for b in dominant]
        w90=max(_quantile(widths,.90),1e-9); h90=max(_quantile(heights,.90),1e-9)
        filtered=[b for b in dominant if (b[2]-b[0])<=w90*6.0 and (b[3]-b[1])<=h90*6.0]
        if len(filtered)>=max(6,int(len(dominant)*.85)):
            dominant=filtered

        base=(min(b[0] for b in dominant),min(b[1] for b in dominant),
              max(b[2] for b in dominant),max(b[3] for b in dominant))

        # Geninddrag geometri tæt ved den fundne hovedtegning, så ydervægge,
        # vinduer og døre ikke bliver klippet af statistikken.
        bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-9); bh=max(by2-by1,1e-9)
        guard=(bx1-bw*.05,by1-bh*.05,bx2+bw*.05,by2+bh*.05)
        nearby=[]
        for b in geom:
            cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
            if guard[0]<=cx<=guard[2] and guard[1]<=cy<=guard[3]:
                nearby.append(b)
        if nearby:
            base=(min([base[0]]+[b[0] for b in nearby]),min([base[1]]+[b[1] for b in nearby]),
                  max([base[2]]+[b[2] for b in nearby]),max([base[3]]+[b[3] for b in nearby]))

        # Kun tekst, der faktisk hører til området omkring hovedtegningen,
        # må påvirke skærm-fit.
        bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-9); bh=max(by2-by1,1e-9)
        tguard=(bx1-bw*.035,by1-bh*.035,bx2+bw*.035,by2+bh*.035)
        nearby=[]
        for b in text_boxes:
            cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
            if tguard[0]<=cx<=tguard[2] and tguard[1]<=cy<=tguard[3]:
                nearby.append(b)
        if nearby:
            base=(min([base[0]]+[b[0] for b in nearby]),min([base[1]]+[b[1] for b in nearby]),
                  max([base[2]]+[b[2] for b in nearby]),max([base[3]]+[b[3] for b in nearby]))

    # Egne el-objekter medtages kun, når de ligger tæt ved hovedtegningen.
    bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-12); bh=max(by2-by1,1e-12)
    guard=(bx1-bw*.10,by1-bh*.10,bx2+bw*.10,by2+bh*.10)
    extras=[]
    for pl in placements or []:
        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):
            continue
        r=max(float(pl.size),1.0)*1.25
        b=(pl.x-r,pl.y-r,pl.x+r,pl.y+r)
        if guard[0]<=pl.x<=guard[2] and guard[1]<=pl.y<=guard[3]:
            extras.append(b)
    for cable in cables or []:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        if not cable.points:
            continue
        xs=[float(q[0]) for q in cable.points]; ys=[float(q[1]) for q in cable.points]
        b=(min(xs),min(ys),max(xs),max(ys)); cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
        if guard[0]<=cx<=guard[2] and guard[1]<=cy<=guard[3]:
            extras.append(b)
    for item in texts or []:
        if layer_visibility is not None and not layer_visibility.get(FREE_TEXT_LAYER,True):continue
        if guard[0]<=item.x<=guard[2] and guard[1]<=item.y<=guard[3]:
            h=max(float(item.height),1.0); w=max(h*.6*len(str(item.text)),h); r=.55*math.hypot(w,h)
            extras.append((item.x-r,item.y-r,item.x+r,item.y+r))
    if extras:
        base=(min([base[0]]+[b[0] for b in extras]),min([base[1]]+[b[1] for b in extras]),
              max([base[2]]+[b[2] for b in extras]),max([base[3]]+[b[3] for b in extras]))
    if base[2]<=base[0]: base=(base[0],base[1],base[0]+1.0,base[3])
    if base[3]<=base[1]: base=(base[0],base[1],base[2],base[1]+1.0)
    return base


def crop_extents_to_aspect(extents, target_ratio: float):
    """Center-crop et CAD-område til et bestemt bredde/højde-forhold.

    Bruges for *Aktuel visning*: papir og skærm har sjældent samme aspekt.
    Hvis hele skærmviewporten blot skaleres med ``min(sx, sy)``, opstår store
    hvide felter på PDF'en. Et lille symmetrisk crop bevarer centrum/zoom og
    lader den viste plan fylde det valgte papir uden geometrisk forvrængning.
    """
    xmin,ymin,xmax,ymax=(float(v) for v in extents)
    w=max(xmax-xmin,1e-12); h=max(ymax-ymin,1e-12)
    target=max(float(target_ratio),1e-12)
    ratio=w/h
    cx=(xmin+xmax)*.5; cy=(ymin+ymax)*.5
    if ratio>target:
        # Viewporten er bredere end papiret: beskær lige meget i venstre/højre.
        nw=h*target
        return (cx-nw*.5,ymin,cx+nw*.5,ymax)
    if ratio<target:
        # Viewporten er højere/smallere end papiret: beskær top/bund.
        nh=w/target
        return (xmin,cy-nh*.5,xmax,cy+nh*.5)
    return (xmin,ymin,xmax,ymax)


def page_layout(extents, paper="A4", orientation="Auto", margin_mm=PRINT_MARGIN_MM, fill_page=False):
    """Beregn fælles PDF-layout og det effektive CAD-udsnit.

    ``fill_page=True`` bruges til *Aktuel visning* og center-cropper kun det
    nødvendige for at matche papirets disponible aspekt. Hele tegningen bruger
    fortsat fit-inside, så intet af den valgte geometri beskæres.
    """
    page=resolve_page_size(paper,orientation,extents)
    pw,ph=page
    margin=float(margin_mm)/25.4*72.0
    avail_w=max(1e-9,pw-2*margin); avail_h=max(1e-9,ph-2*margin)
    effective=tuple(float(v) for v in extents)
    if fill_page:
        effective=crop_extents_to_aspect(effective,avail_w/avail_h)
    xmin,ymin,xmax,ymax=effective
    dw=max(xmax-xmin,1e-12); dh=max(ymax-ymin,1e-12)
    scale=min(avail_w/dw,avail_h/dh)
    draw_w=dw*scale; draw_h=dh*scale
    ox=(pw-draw_w)/2.0; oy=(ph-draw_h)/2.0
    return page,effective,scale,ox,oy,draw_w,draw_h,margin


def resolve_page_size(paper: str, orientation: str, extents):
    base = A3 if str(paper).upper() == "A3" else A4
    if orientation == "Landskab":
        return landscape(base)
    if orientation == "Portræt":
        return portrait(base)
    xmin, ymin, xmax, ymax = extents
    drawing_ratio = max((xmax-xmin) / max(ymax-ymin, 1e-12), 1e-12)
    portrait_ratio = portrait(base)[0] / portrait(base)[1]
    return landscape(base) if drawing_ratio > portrait_ratio else portrait(base)
