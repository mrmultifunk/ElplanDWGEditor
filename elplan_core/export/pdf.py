"""Vektorbaseret PDF-eksport af den elektriske plantegning."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from annotation_layout import choose_label_origin, expand_rect
from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import (
    association_channel_letters,
    association_display,
    association_module_layout,
    association_role,
    light_output_by_id,
    light_output_records,
)
from elplan_core.cables.categories import cable_visible_in_layers, normalize_cable_line_style
from elplan_core.cables.geometry import polyline_label_point, rotate_point
from elplan_core.cables.sections import cable_section_spec_labels
from elplan_core.cables.visual import cable_plan_label, cable_visual_paths
from elplan_core.constants import (
    DEFAULT_ANNOTATION_FONT_SIZE,
    DEFAULT_ANNOTATION_STYLE,
    DEFAULT_CABLE_COLOR,
    DEFAULT_CABLE_LINE_STYLE,
    FREE_TEXT_LAYER,
    META_LAYER,
    PRINT_MARGIN_MM,
    ROOM_LAYER,
)
from elplan_core.export.extents import page_layout, print_extents
from elplan_core.export.output_profiles import (
    annotation_visual_profile,
    output_cad_text_font_size,
    output_equivalent_view_scale,
    output_free_text_font_size,
    output_switch_association_tag_profile,
    output_symbol_text_font_size,
)
from elplan_core.rooms import room_output_label
from elplan_core.symbols.clipboard import symbol_layer
from elplan_core.symbols.geometry import symbol_primitives
from elplan_core.symbols.registry import (
    _split_csv_parts,
    combo_modules,
    is_combo_symbol,
    normalize_combo_label_mode,
)


def export_vector_pdf(path: str | Path, cad_primitives, placements, cables=None,
                      layer_visibility=None, paper="A4", orientation="Auto",
                      annotation_style=DEFAULT_ANNOTATION_STYLE, annotation_font_size=DEFAULT_ANNOTATION_FONT_SIZE,
                      extents_override=None, texts=None, fill_page=False, cad_opacity=1.0,
                      annotation_mode="Auto", rooms=None, room_labels_visible=True,
                      room_codes_visible=False, room_boundaries_visible=False) -> None:
    """Write the current plan as a one-page, vector PDF.

    PDF-output uses the same text scaling rules as the Qt editor.  Earlier
    versions mixed world-scaled text, fixed PDF-point text and hard clamps;
    that made room text, CAD text, cable labels and symbol-internal text look
    very different from the on-screen drawing.
    """
    cables = cables or []
    texts = texts or []
    rooms = list(rooms or [])
    placements = list(placements or [])
    ext = tuple(extents_override) if extents_override is not None else print_extents(
        cad_primitives,placements,cables,layer_visibility,texts,rooms,
        room_labels_visible,room_boundaries_visible
    )
    page,effective_ext,scale,ox,oy,draw_w,draw_h,margin = page_layout(
        ext,paper,orientation,PRINT_MARGIN_MM,fill_page=bool(fill_page)
    )
    pw,ph=page
    xmin,ymin,xmax,ymax=effective_ext
    view_scale=output_equivalent_view_scale(scale)
    mode=str(annotation_mode or "Auto")
    if mode not in ("Auto","Tydelig","Minimal","Skjult"):
        mode="Auto"

    def mappt(x, y):
        return ox+(float(x)-xmin)*scale, oy+(float(y)-ymin)*scale

    def alpha_color(hex_value: str, alpha: float=1.0):
        h=normalize_hex_color(hex_value).lstrip("#")
        a=max(0.0,min(1.0,float(alpha)))
        return colors.Color(int(h[0:2],16)/255.0,int(h[2:4],16)/255.0,int(h[4:6],16)/255.0,alpha=a)

    def pdf_text(value) -> str:
        # ReportLab's built-in Helvetica uses WinAnsi. Keep Danish characters,
        # but replace symbols outside that encoding deterministically.
        txt=str(value or "").replace("↳","->").replace("→","->")
        return txt.encode("cp1252","replace").decode("cp1252")

    try:
        cad_opacity=max(0.0,min(1.0,float(cad_opacity)))
    except Exception:
        cad_opacity=1.0
    cad_gray=int(round(255.0*(1.0-cad_opacity)))
    cad_hex=f"#{cad_gray:02x}{cad_gray:02x}{cad_gray:02x}"
    cad_pdf_color=colors.HexColor(cad_hex)

    placement_by_uid={str(getattr(pl,"uid","") or ""):pl for pl in placements}

    def compact_combo_group(pl):
        groups=_split_csv_parts(getattr(pl,"switch_group",""), len(combo_modules(pl.symbol)))
        parts=[]
        for i,group in enumerate(groups,1):
            if group: parts.append(f"A{i}:{group}")
        socket=str(getattr(pl,"socket_group","") or "").strip()
        if socket: parts.append(f"S:{socket}")
        return "  ".join(parts)

    def combo_detail_lines(pl):
        mods=combo_modules(pl.symbol)
        groups=_split_csv_parts(getattr(pl,"switch_group",""),len(mods))
        labels=_split_csv_parts(getattr(pl,"switch_label",""),len(mods))
        out=[]
        for i,(group,label) in enumerate(zip(groups,labels),1):
            bits=[x for x in (group,label) if x]
            if bits: out.append(f"A{i}: " + " · ".join(bits))
        sg=str(getattr(pl,"socket_group","") or "").strip()
        sl=str(getattr(pl,"socket_label","") or "").strip()
        bits=[x for x in (sg,sl) if x]
        if bits: out.append("S: " + " · ".join(bits))
        return out

    def spot_parent_text(pl):
        if getattr(pl,"symbol","")!="spot": return ""
        uid=str(getattr(pl,"parent_light_uid","") or "")
        if not uid: return ""
        parent=placement_by_uid.get(uid)
        if parent is None: return "↳ Lampested ?"
        ident=str(getattr(parent,"group","") or getattr(parent,"label","") or "Lampested").strip()
        output=light_output_by_id(parent,getattr(pl,"parent_light_output_id","") or "")
        suffix=f" / {output.get('name')}" if len(light_output_records(parent))>1 else ""
        return f"↳ {ident}{suffix}"

    def annotation_content(pl):
        if mode=="Skjult": return "","","",[],""
        if mode=="Auto" and view_scale<0.055:
            return "","","",[],""
        assoc=association_display(pl)
        if association_role(pl.symbol)=="switch":
            assoc=""
        group=str(getattr(pl,"group","") or "").strip()
        label=str(getattr(pl,"label","") or "").strip()
        primary=group or label
        secondary=label if group and label else ""
        if mode=="Minimal":
            secondary=""; assoc=""
        show_secondary=bool(secondary) and (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.145))
        show_assoc=bool(assoc) and (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.055))
        extra=[]
        if is_combo_symbol(pl.symbol) and normalize_combo_label_mode(getattr(pl,"label_mode","Fælles"))=="Opdelt":
            if mode=="Tydelig" or (mode=="Auto" and view_scale>=0.20):
                extra=combo_detail_lines(pl); primary=""; secondary=""
            else:
                primary=compact_combo_group(pl) or primary; secondary=""
        spot=spot_parent_text(pl)
        if not (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.21)):
            spot=""
        if mode=="Minimal": spot=""
        return primary,(secondary if show_secondary else ""),(assoc if show_assoc else ""),extra,spot

    c = pdfcanvas.Canvas(str(path), pagesize=page, pageCompression=1)
    c.setTitle("Elplan")
    c.setLineCap(1); c.setLineJoin(1)
    c.saveState()
    if extents_override is not None or fill_page:
        clip = c.beginPath(); clip.rect(margin, margin, pw-2*margin, ph-2*margin)
        c.clipPath(clip, stroke=0, fill=0)

    # Architectural CAD.
    c.setStrokeColor(cad_pdf_color); c.setFillColor(cad_pdf_color); c.setLineWidth(0.45)
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
            continue
        try:
            if prim.kind == "line":
                x1,y1,x2,y2=prim.data; c.line(*mappt(x1,y1),*mappt(x2,y2))
            elif prim.kind == "circle":
                cx,cy,r=prim.data; x,y=mappt(cx-r,cy-r); x2,y2=mappt(cx+r,cy+r); c.ellipse(x,y,x2,y2,stroke=1,fill=0)
            elif prim.kind == "arc":
                cx,cy,r,a1,a2=prim.data; x,y=mappt(cx-r,cy-r); x2,y2=mappt(cx+r,cy+r)
                delta=(a2-a1)%360 or 360; c.arc(x,y,x2,y2,startAng=a1,extent=delta)
            elif prim.kind == "polyline":
                pts=list(prim.data)
                if len(pts)>=2:
                    pp=c.beginPath(); pp.moveTo(*mappt(*pts[0]))
                    for q in pts[1:]: pp.lineTo(*mappt(*q))
                    c.drawPath(pp,stroke=1,fill=0)
            elif prim.kind == "point":
                x,y=mappt(*prim.data); c.circle(x,y,0.8,stroke=1,fill=1)
            elif prim.kind == "text":
                x,y,t,h,rot=prim.data; sx0,sy0=mappt(x,y)
                fs=output_cad_text_font_size(h,scale)
                c.saveState(); c.translate(sx0,sy0); c.rotate(float(rot)); c.setFont("Helvetica",fs)
                try: c.drawString(0,0,str(t))
                except Exception: c.drawString(0,0,str(t).encode("cp1252","replace").decode("cp1252"))
                c.restoreState()
        except Exception:
            continue

    # Rumafgrænsninger er et selvstændigt lag og følger deres eget Vis-valg.
    # De tegnes under installationen, ligesom i editoren.
    room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
    if room_layer_visible and room_boundaries_visible:
        for room in rooms:
            pts=list(getattr(room,"points",[]) or [])
            if len(pts)<2:continue
            color=normalize_hex_color(getattr(room,"color","#0f766e"),"#0f766e")
            c.setStrokeColor(alpha_color(color,.72)); c.setFillColor(alpha_color(color,.05)); c.setLineWidth(1.0); c.setDash(5,3)
            pp=c.beginPath(); pp.moveTo(*mappt(*pts[0]))
            for q in pts[1:]:pp.lineTo(*mappt(*q))
            if len(pts)>=3:pp.close()
            c.drawPath(pp,stroke=1,fill=1 if len(pts)>=3 else 0)
        c.setDash()

    # Electrical symbols. Internal symbol text follows Qt's 0.60 scale factor.
    def _placement_page_bounds(pl):
        pts=[]
        def add(lx,ly):
            rx,ry=rotate_point(float(lx),float(ly),pl.rotation); pts.append(mappt(pl.x+rx,pl.y+ry))
        for prim in symbol_primitives(pl.symbol,pl.size):
            typ=prim[0]
            if typ=="line": add(prim[1],prim[2]); add(prim[3],prim[4])
            elif typ in {"circle","arc"}:
                _t,cx,cy,r,*_=prim
                for dx in (-r,r):
                    for dy in (-r,r): add(cx+dx,cy+dy)
            elif typ=="polyline":
                for qx,qy in prim[1]: add(qx,qy)
            elif typ in {"text","upright_text"}: add(prim[1],prim[2])
        if not pts:
            q=mappt(pl.x,pl.y); return (q[0],q[1],q[0],q[1])
        xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
        return (min(xs),min(ys),max(xs),max(ys))
    placement_page_bounds={getattr(pl,"uid",id(pl)):_placement_page_bounds(pl) for pl in placements}
    for pl in placements:
        layer=symbol_layer(pl.symbol)
        if layer_visibility is not None and not layer_visibility.get(layer, True):
            continue
        symbol_color = colors.HexColor(normalize_hex_color(pl.color))
        c.setStrokeColor(symbol_color); c.setFillColor(symbol_color)
        c.setLineWidth(max(0.1, float(pl.line_width) / 25.4 * 72.0))
        def world(lx,ly):
            rx,ry=rotate_point(lx,ly,pl.rotation); return pl.x+rx, pl.y+ry
        for prim in symbol_primitives(pl.symbol,pl.size):
            typ=prim[0]
            try:
                if typ=="line":
                    c.line(*mappt(*world(prim[1],prim[2])),*mappt(*world(prim[3],prim[4])))
                elif typ=="circle":
                    _,cx,cy,r=prim; wc=world(cx,cy); x,y=mappt(wc[0]-r,wc[1]-r); x2,y2=mappt(wc[0]+r,wc[1]+r); c.ellipse(x,y,x2,y2,stroke=1,fill=0)
                elif typ=="arc":
                    _,cx,cy,r,a1,a2=prim; wc=world(cx,cy); x,y=mappt(wc[0]-r,wc[1]-r); x2,y2=mappt(wc[0]+r,wc[1]+r)
                    c.arc(x,y,x2,y2,startAng=a1+pl.rotation,extent=a2-a1)
                elif typ=="polyline":
                    pts=[mappt(*world(x,y)) for x,y in prim[1]]
                    if len(pts)>=2:
                        pp=c.beginPath(); pp.moveTo(*pts[0])
                        for q in pts[1:]: pp.lineTo(*q)
                        c.drawPath(pp,stroke=1,fill=0)
                elif typ in {"text","upright_text"}:
                    _,x,y,t,h=prim; wx,wy=world(x,y); px,py=mappt(wx,wy); fs=output_symbol_text_font_size(h,scale)
                    text_rotation=0.0 if typ=="upright_text" else pl.rotation
                    c.saveState(); c.translate(px,py); c.rotate(text_rotation); c.setFont("Helvetica-Bold",fs); c.drawCentredString(0,-fs*0.32,str(t)); c.restoreState()
            except Exception:
                continue

    # Free text is deliberately page-space text in the editor (ItemIgnoresTransformations).
    # Therefore its PDF font size must NOT be multiplied by the CAD/page scale.
    if layer_visibility is None or layer_visibility.get(FREE_TEXT_LAYER, True):
        for item in texts:
            if not str(item.text).strip(): continue
            px,py=mappt(float(item.x),float(item.y)); fs=output_free_text_font_size(item.height)
            c.saveState(); c.translate(px,py); c.rotate(float(item.rotation)); c.setFillColor(colors.HexColor(normalize_hex_color(item.color))); c.setFont("Helvetica",fs)
            try: c.drawString(0,-fs*0.88,str(item.text))
            except Exception: c.drawString(0,-fs*0.88,str(item.text).encode("cp1252","replace").decode("cp1252"))
            c.restoreState()

    # Cables and wires. Parallel routes are separated only visually; the saved
    # logical geometry and the cable-length calculation remain untouched.
    c.setFillColor(colors.HexColor("#08752c"))
    visible_cables=[cb for cb in cables if cable_visible_in_layers(cb,layer_visibility)]
    cable_visuals=cable_visual_paths(visible_cables,5.0/max(scale,1e-12),fan_length=12.0/max(scale,1e-12))
    for cable in cables:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        display_points=cable_visuals.get(id(cable),cable.points)
        if len(display_points) < 2:
            continue
        c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))
        c.setLineWidth(max(0.1, float(cable.line_width) / 25.4 * 72.0))
        style=normalize_cable_line_style(getattr(cable,"line_style",DEFAULT_CABLE_LINE_STYLE))
        if style=="dash": c.setDash(6,4)
        elif style=="dot": c.setDash(1.2,3.0)
        elif style=="dashdot": c.setDash([6,3,1.2,3],0)
        else: c.setDash()
        pts=[mappt(float(x),float(y)) for x,y in display_points]
        pp=c.beginPath(); pp.moveTo(*pts[0])
        for q in pts[1:]: pp.lineTo(*q)
        c.drawPath(pp,stroke=1,fill=0)
        text=cable_plan_label(cable)
        if text and mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
            wx,wy=polyline_label_point(display_points); mx,my=mappt(wx,wy)
            fs=8.0; pad=1.4; dx=5.25; dy=12.75
            tw=stringWidth(text,"Helvetica-Bold",fs)
            c.setFillColor(colors.white); c.rect(mx+dx-pad,my+dy-fs*.25-pad,tw+2*pad,fs+2*pad+.5,stroke=0,fill=1)
            c.setFillColor(colors.HexColor("#0f6a3e")); c.setFont("Helvetica-Bold",fs); c.drawString(mx+dx,my+dy,text)
            c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))
        if mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
            for rec in cable_section_spec_labels(cable):
                spec=str(rec.get("cable_spec") or "").strip()
                if not spec: continue
                wx,wy=rec.get("point",(0.0,0.0)); mx,my=mappt(wx,wy)
                fs=7.0; pad=1.2; dx=5.0; dy=-3.0
                tw=stringWidth(spec,"Helvetica-Bold",fs)
                c.setFillColor(colors.white); c.rect(mx+dx-pad,my+dy-fs*.25-pad,tw+2*pad,fs+2*pad+.5,stroke=0,fill=1)
                c.setFillColor(colors.HexColor("#7c3f00")); c.setFont("Helvetica-Bold",fs); c.drawString(mx+dx,my+dy,spec)
                c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))

    # Rumnavne er kosmetisk page-space tekst og skal derfor ikke skaleres med
    # CAD-tegningen. Rummærkning/ID er bevidst et separat valg.
    if room_layer_visible and room_labels_visible:
        fs=9.0
        for room in rooms:
            label=pdf_text(room_output_label(room,room_codes_visible))
            if not label:continue
            px,py=mappt(float(getattr(room,"label_x",0.0)),float(getattr(room,"label_y",0.0)))
            c.setFillColor(colors.HexColor(normalize_hex_color(getattr(room,"color","#0f766e"),"#0f766e")))
            c.setFont("Helvetica-Bold",fs); c.drawString(px,py-fs*.88,label)

    # Metadata/relations use the same semantic zoom and font profile as the Qt editor.
    if mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
        profile=annotation_visual_profile(mode,view_scale,False)

        def draw_plain(text,x,y,font_name,font_size,color):
            text=pdf_text(text)
            c.setFillColor(alpha_color(color,0.90)); c.setFont(font_name,font_size); c.drawString(x,y,text)
            return stringWidth(text,font_name,font_size),font_size*1.18

        def draw_chip(text,x,y,font_name,font_size,fg,fill,border,pad):
            text=pdf_text(text)
            pxpad,pypad=pad
            tw=stringWidth(text,font_name,font_size)
            w=max(20.0,tw+2*pxpad); h=font_size*1.18+2*pypad
            c.setFillColor(alpha_color(fill,0.94)); c.setStrokeColor(alpha_color(border,0.88)); c.setLineWidth(0.55)
            c.roundRect(x,y,w,h,4,stroke=1,fill=1)
            c.setFillColor(alpha_color(fg,0.96)); c.setFont(font_name,font_size); c.drawString(x+pxpad,y+pypad+font_size*.14,text)
            return w,h

        def plain_size(text,font_name,font_size):
            return stringWidth(pdf_text(text),font_name,font_size),font_size*1.18

        def chip_size(text,font_name,font_size,pad):
            pxpad,pypad=pad
            return max(20.0,stringWidth(pdf_text(text),font_name,font_size)+2*pxpad),font_size*1.18+2*pypad

        def annotation_block_size(primary,secondary,assoc,extra,spot):
            width=0.0; height=0.0; row_h=0.0; row_w=0.0
            quiet_primary=(mode=="Minimal" or (mode=="Auto" and view_scale<0.145))
            if extra:
                fs=profile["primary"]*.90
                for line in extra:
                    w,h=chip_size(str(line),"Helvetica-Bold",fs,profile["pad_small"]); width=max(width,w); height+=h+profile["row_gap"]
                if extra: height=max(0.0,height-profile["row_gap"])
            else:
                if primary:
                    fs=profile["primary"]
                    w,h=plain_size(primary,"Helvetica-Bold",fs) if quiet_primary else chip_size(primary,"Helvetica-Bold",fs,profile["pad_primary"])
                    row_w+=w; row_h=max(row_h,h)
                if secondary:
                    fs=profile["secondary"]; w,h=chip_size(secondary,"Helvetica",fs,profile["pad_small"])
                    if row_w: row_w+=profile["gap"]
                    row_w+=w; row_h=max(row_h,h)
                if row_w: width=max(width,row_w); height+=row_h
            if assoc:
                if height: height+=profile["row_gap"]
                fs=max(4.8,profile["assoc"]*.90) if (mode=="Auto" and view_scale<0.145) else profile["assoc"]
                w,h=plain_size(assoc,"Helvetica-Bold",fs) if (mode=="Auto" and view_scale<0.145) else chip_size(assoc,"Helvetica-Bold",fs,profile["pad_small"])
                width=max(width,w); height+=h
            if spot:
                if height: height+=profile["row_gap"]
                fs=profile["spot"]; w,h=chip_size(spot,"Helvetica",fs,profile["pad_small"]); width=max(width,w); height+=h
            return max(1.0,width),max(1.0,height)

        symbol_blockers=[expand_rect(bounds,1.4) for bounds in placement_page_bounds.values()]
        metadata_occupied=[]
        page_container=(margin*.55,margin*.55,pw-margin*.55,ph-margin*.55)

        for pl in placements:
            if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):
                continue
            primary,secondary,assoc,extra,spot=annotation_content(pl)
            if not (primary or secondary or assoc or extra or spot):
                continue
            # All automatic metadata shares one collision map. Symbol silhouettes are
            # hard blockers; already placed group/marking/relation labels reserve space.
            bounds=placement_page_bounds.get(getattr(pl,"uid",id(pl)),mappt(pl.x,pl.y)*2)
            anchor=mappt(pl.x,pl.y); block_w,block_h=annotation_block_size(primary,secondary,assoc,extra,spot)
            tx,ty,_side,occupied_rect=choose_label_origin(
                anchor,bounds,block_w,block_h,blockers=symbol_blockers,occupied=metadata_occupied,
                preferred="right",gap=4.8,collision_padding=1.25,container=page_container
            )
            metadata_occupied.append(occupied_rect)
            x=tx; y=ty; row_h=0.0
            quiet_primary=(mode=="Minimal" or (mode=="Auto" and view_scale<0.145))
            if extra:
                font_size=profile["primary"]*.90
                for line in extra:
                    _w,h=draw_chip(str(line),tx,y,"Helvetica-Bold",font_size,"#35564a","#ffffff","#aebeb6",profile["pad_small"])
                    y+=h+profile["row_gap"]
            else:
                if primary:
                    fs=profile["primary"]
                    if quiet_primary:
                        w,h=draw_plain(primary,x,y,"Helvetica-Bold",fs,"#2d5242")
                    else:
                        w,h=draw_chip(primary,x,y,"Helvetica-Bold",fs,"#174e39","#ffffff","#a0b4a9",profile["pad_primary"])
                    x+=w+profile["gap"]; row_h=max(row_h,h)
                if secondary:
                    fs=profile["secondary"]
                    w,h=draw_chip(secondary,x,y,"Helvetica",fs,"#69736f","#f8f9f9","#cfd5d2",profile["pad_small"])
                    x+=w; row_h=max(row_h,h)
                if primary or secondary:
                    y+=row_h+profile["row_gap"]
            if assoc:
                fs=max(4.8,profile["assoc"]*.90) if (mode=="Auto" and view_scale<0.145) else profile["assoc"]
                if mode=="Auto" and view_scale<0.145:
                    _w,h=draw_plain(assoc,tx,y,"Helvetica-Bold",fs,"#31608b")
                else:
                    _w,h=draw_chip(assoc,tx,y,"Helvetica-Bold",fs,"#31608b","#edf5fc","#87abca",profile["pad_small"])
                y+=h+profile["row_gap"]
            if spot:
                fs=profile["spot"]
                _w,h=draw_chip(spot,tx,y,"Helvetica",fs,"#2b6b68","#edf8f7","#97c2bf",profile["pad_small"])
                y+=h

        # Switch a/b/c labels are anchored to the physical module instead of being
        # collapsed into one combined label at the whole combo symbol.
        if mode not in ("Minimal","Skjult") and not (mode=="Auto" and view_scale<0.055):
            overview=(mode=="Auto" and view_scale<0.145)
            tag=output_switch_association_tag_profile(overview)
            fs=float(tag["font_size"]); pad_x=float(tag["pad_x"]); pad_y=float(tag["pad_y"])
            for pl in placements:
                if association_role(pl.symbol)!="switch": continue
                if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True): continue
                channels=association_channel_letters(pl)
                for rec in association_module_layout(pl.symbol,pl.size):
                    _module_no,_base,lx,ly,_radius,indices=rec
                    letters=[channels[i] for i in indices if i < len(channels) and channels[i]]
                    if not letters: continue
                    text=pdf_text(" · ".join(letters))
                    wx,wy=rotate_point(lx,ly,pl.rotation); wx+=pl.x; wy+=pl.y
                    ax,ay=mappt(wx,wy)
                    tw=stringWidth(text,"Helvetica-Bold",fs); h=fs*1.18+2*pad_y; w=max(float(tag["min_width"]),tw+2*pad_x)
                    bounds=placement_page_bounds.get(getattr(pl,"uid",id(pl)),(ax,ay,ax,ay))
                    left,bottom,right,top=map(float,bounds); preferred="below" if (right-left)>(top-bottom)*1.12 else "right"
                    tx,ty,_side,occupied_rect=choose_label_origin(
                        (ax,ay),bounds,w,h,blockers=symbol_blockers,occupied=metadata_occupied,
                        preferred=preferred,gap=3.8 if overview else 4.6,collision_padding=1.15,container=page_container
                    )
                    metadata_occupied.append(occupied_rect)
                    c.setFillColor(alpha_color("#f5faff",float(tag["fill_alpha"])))
                    c.setStrokeColor(alpha_color("#7aa4c7",float(tag["border_alpha"])))
                    c.setLineWidth(float(tag["line_width"]))
                    c.roundRect(tx,ty,w,h,float(tag["radius"]),stroke=1,fill=1)
                    c.setFillColor(alpha_color("#2d5b84",float(tag["text_alpha"])))
                    c.setFont("Helvetica-Bold",fs); c.drawString(tx+pad_x,ty+pad_y+fs*.14,text)

    c.restoreState()
    c.showPage(); c.save()
