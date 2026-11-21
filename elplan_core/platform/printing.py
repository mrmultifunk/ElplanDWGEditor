"""Direkte vektorudskrivning via Windows GDI."""

from __future__ import annotations

import math
import os

from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import association_display, association_world_point
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
from elplan_core.export.extents import crop_extents_to_aspect, print_extents, resolve_page_size
from elplan_core.rooms import room_output_label
from elplan_core.symbols.clipboard import symbol_annotation_lines, symbol_layer
from elplan_core.symbols.geometry import symbol_primitives


def print_vector_windows(cad_primitives, placements, cables=None, layer_visibility=None,
                         paper="A4", orientation="Auto",
                         annotation_style=DEFAULT_ANNOTATION_STYLE,
                         annotation_font_size=DEFAULT_ANNOTATION_FONT_SIZE,
                         extents_override=None, printer_name=None, texts=None, fill_page=False,
                         cad_opacity=1.0, rooms=None, room_labels_visible=True,
                         room_codes_visible=False, room_boundaries_visible=False) -> str:
    """Print planen direkte som Windows GDI-vektorer.

    Tidligere blev en PDF sendt til ``os.startfile(..., "print")``. Den vej lader
    PDF-programmet/printerdriveren vælge papir og ender ofte i A4, selv når PDF'en
    er A3. Her oprettes i stedet en printer-DC med en DEVMODE, hvor A3/A4 og
    orientering sættes eksplicit før jobbet startes.

    Returnerer navnet på den printer, der modtog jobbet.
    """
    if os.name != "nt":
        raise RuntimeError("Direkte Windows-udskrivning er kun tilgængelig på Windows.")

    import pywintypes
    import win32api
    import win32con
    import win32gui
    import win32print

    cables = cables or []
    texts = texts or []
    rooms = list(rooms or [])
    try:
        cad_opacity=max(0.0,min(1.0,float(cad_opacity)))
    except Exception:
        cad_opacity=1.0
    cad_gray=int(round(255.0*(1.0-cad_opacity)))
    cad_hex=f"#{cad_gray:02x}{cad_gray:02x}{cad_gray:02x}"
    ext = tuple(extents_override) if extents_override is not None else print_extents(
        cad_primitives,placements,cables,layer_visibility,texts,rooms,
        room_labels_visible,room_boundaries_visible
    )
    xmin, ymin, xmax, ymax = ext
    if xmax <= xmin or ymax <= ymin:
        raise RuntimeError("Det valgte udskriftsområde er tomt.")

    requested_paper = str(paper).upper()
    paper_code = win32con.DMPAPER_A3 if requested_paper == "A3" else win32con.DMPAPER_A4

    # Auto-orientering følger samme logik som PDF-eksporten.
    page_pts = resolve_page_size(requested_paper, orientation, ext)
    is_landscape = page_pts[0] > page_pts[1]
    orient_code = win32con.DMORIENT_LANDSCAPE if is_landscape else win32con.DMORIENT_PORTRAIT

    pname = printer_name or win32print.GetDefaultPrinter()
    hprinter = None
    hdc = None
    doc_started = False
    page_started = False
    created_objects = []
    try:
        hprinter = win32print.OpenPrinter(pname)
        info = win32print.GetPrinter(hprinter, 2)
        print_processor = info.get("pPrintProcessor") or "winprint"

        # Brug printerens fulde driver-specifikke DEVMODE-størrelse, jf. pywin32s
        # eget print_desktop.py-eksempel. Det er mere robust end at bygge en
        # minimal DEVMODE, som visse drivere afviser.
        dmsize = win32print.DocumentProperties(0, hprinter, pname, None, None, 0)
        driverextra = max(0, int(dmsize) - pywintypes.DEVMODEType().Size)
        dm = pywintypes.DEVMODEType(driverextra)
        win32print.DocumentProperties(0, hprinter, pname, dm, None, win32con.DM_OUT_BUFFER)
        dm.Fields |= win32con.DM_ORIENTATION | win32con.DM_PAPERSIZE | win32con.DM_COPIES
        dm.Orientation = orient_code
        dm.PaperSize = paper_code
        dm.Copies = 1
        result = win32print.DocumentProperties(
            0, hprinter, pname, dm, dm, win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER
        )
        if result < 0:
            raise RuntimeError("Printerdriveren afviste de valgte papirindstillinger.")

        hdc = win32gui.CreateDC(print_processor, pname, dm)
        if not hdc:
            raise RuntimeError("Windows kunne ikke oprette en printerkontekst.")

        dpi_x = max(1, win32print.GetDeviceCaps(hdc, win32con.LOGPIXELSX))
        dpi_y = max(1, win32print.GetDeviceCaps(hdc, win32con.LOGPIXELSY))
        printable_w = max(1, win32print.GetDeviceCaps(hdc, win32con.HORZRES))
        printable_h = max(1, win32print.GetDeviceCaps(hdc, win32con.VERTRES))
        phys_w = max(1, win32print.GetDeviceCaps(hdc, win32con.PHYSICALWIDTH))
        phys_h = max(1, win32print.GetDeviceCaps(hdc, win32con.PHYSICALHEIGHT))

        # Fang den klassiske fejl: driveren har ignoreret A3 og faldet tilbage
        # til A4. Vi måler den fysiske side i stedet for at stole på comboboxen.
        mm_w = phys_w / dpi_x * 25.4
        mm_h = phys_h / dpi_y * 25.4
        short_mm, long_mm = sorted((mm_w, mm_h))
        if requested_paper == "A3" and (short_mm < 270 or long_mm < 390):
            raise RuntimeError(
                f"Printerdriveren skiftede tilbage til ca. {short_mm:.0f}×{long_mm:.0f} mm i stedet for A3. "
                "Kontrollér at den valgte printer faktisk understøtter A3."
            )

        margin_mm = PRINT_MARGIN_MM
        mx = margin_mm / 25.4 * dpi_x
        my = margin_mm / 25.4 * dpi_y
        avail_w = max(1.0, printable_w - 2.0 * mx)
        avail_h = max(1.0, printable_h - 2.0 * my)

        # *Aktuel visning* skal fylde siden på samme måde som PDF'en. Skærmens
        # aspekt og printerens printable område er sjældent identiske, så vi
        # center-cropper kun den overskydende rand før skalering.
        if fill_page:
            physical_ratio=(avail_w/dpi_x)/max(avail_h/dpi_y,1e-12)
            xmin,ymin,xmax,ymax=crop_extents_to_aspect((xmin,ymin,xmax,ymax),physical_ratio)
        dw = xmax - xmin; dh = ymax - ymin
        # Fysisk uniform skalering: samme antal millimeter pr. CAD-enhed i X/Y,
        # også på printere hvor LOGPIXELSX og LOGPIXELSY er forskellige.
        inch_per_unit = min((avail_w / dpi_x) / dw, (avail_h / dpi_y) / dh)
        sx = inch_per_unit * dpi_x
        sy = inch_per_unit * dpi_y
        draw_w = dw * sx; draw_h = dh * sy
        ox = (printable_w - draw_w) / 2.0
        oy = (printable_h - draw_h) / 2.0

        def mappt(x, y):
            return int(round(ox + (float(x) - xmin) * sx)), int(round(oy + (ymax - float(y)) * sy))

        def colorref(value):
            h = normalize_hex_color(value).lstrip("#")
            return win32api.RGB(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

        def select_pen(hex_color, width_mm, line_style="solid"):
            px = max(1, int(round(float(width_mm) / 25.4 * (dpi_x + dpi_y) / 2.0)))
            style=normalize_cable_line_style(line_style)
            ps={"dash":getattr(win32con,"PS_DASH",win32con.PS_SOLID),"dot":getattr(win32con,"PS_DOT",win32con.PS_SOLID),"dashdot":getattr(win32con,"PS_DASHDOT",win32con.PS_SOLID)}.get(style,win32con.PS_SOLID)
            pen = win32gui.CreatePen(ps, px, colorref(hex_color))
            created_objects.append(pen)
            old = win32gui.SelectObject(hdc, pen)
            return old, pen

        def draw_segment(a, b):
            win32gui.MoveToEx(hdc, int(a[0]), int(a[1]))
            win32gui.LineTo(hdc, int(b[0]), int(b[1]))

        def draw_polyline(points):
            pts = list(points)
            if len(pts) < 2:
                return
            a = pts[0]
            win32gui.MoveToEx(hdc, int(a[0]), int(a[1]))
            for q in pts[1:]:
                win32gui.LineTo(hdc, int(q[0]), int(q[1]))

        def arc_world_points(cx, cy, r, a1, a2, transform=lambda x, y:(x, y)):
            delta = (float(a2) - float(a1)) % 360.0
            if abs(delta) < 1e-9:
                delta = 360.0
            n = max(8, int(abs(delta) / 5.0) + 1)
            out=[]
            for i in range(n + 1):
                a = math.radians(float(a1) + delta * i / n)
                x = float(cx) + float(r) * math.cos(a)
                y = float(cy) + float(r) * math.sin(a)
                out.append(transform(x, y))
            return out

        def draw_text_world(x, y, text, h_world, rotation=0.0, color="#111111", bold=False):
            px_h = max(5, int(abs(float(h_world)) * sy * 0.78))
            lf = win32gui.LOGFONT()
            lf.lfHeight = -px_h
            lf.lfWeight = 700 if bold else 400
            lf.lfEscapement = int(round(float(rotation) * 10.0))
            lf.lfOrientation = lf.lfEscapement
            lf.lfFaceName = "Arial"
            font = win32gui.CreateFontIndirect(lf); created_objects.append(font)
            old_font = win32gui.SelectObject(hdc, font)
            try:
                win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
                win32gui.SetTextColor(hdc, colorref(color))
                px, py = mappt(x, y)
                win32gui.TextOut(hdc, px, py - px_h, str(text))
            finally:
                win32gui.SelectObject(hdc, old_font)

        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        old_brush = win32gui.SelectObject(hdc, null_brush)

        win32print.StartDoc(hdc, ("Elplan", None, None, 0)); doc_started = True
        win32print.StartPage(hdc); page_started = True
        try:
            # Arkitekttegning. Dæmpning er neutral grå og gælder kun CAD-baggrunden.
            old_pen, _ = select_pen(cad_hex, 0.16)
            try:
                for prim in cad_primitives:
                    if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
                        continue
                    try:
                        if prim.kind == "line":
                            x1,y1,x2,y2=prim.data; draw_segment(mappt(x1,y1),mappt(x2,y2))
                        elif prim.kind == "circle":
                            cx,cy,r=prim.data; a=mappt(cx-r,cy+r); b=mappt(cx+r,cy-r)
                            win32gui.Ellipse(hdc,min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
                        elif prim.kind == "arc":
                            cx,cy,r,a1,a2=prim.data
                            draw_polyline(mappt(x,y) for x,y in arc_world_points(cx,cy,r,a1,a2))
                        elif prim.kind == "polyline":
                            draw_polyline(mappt(*q) for q in prim.data)
                        elif prim.kind == "point":
                            x,y=mappt(*prim.data); rr=max(1,int((dpi_x+dpi_y)/1200)); win32gui.Ellipse(hdc,x-rr,y-rr,x+rr,y+rr)
                        elif prim.kind == "text":
                            x,y,t,h,rot=prim.data; draw_text_world(x,y,t,h,rot,cad_hex,False)
                    except Exception:
                        continue
            finally:
                win32gui.SelectObject(hdc, old_pen)

            room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
            if room_layer_visible and room_boundaries_visible:
                for room in rooms:
                    pts=list(getattr(room,"points",[]) or [])
                    if len(pts)<2:continue
                    old_pen,_=select_pen(getattr(room,"color","#0f766e"),0.18,"dash")
                    try:
                        mapped=[mappt(*q) for q in pts]
                        if len(pts)>=3:mapped.append(mapped[0])
                        draw_polyline(mapped)
                    finally:win32gui.SelectObject(hdc,old_pen)

            # El-symboler.
            for pl in placements:
                layer=symbol_layer(pl.symbol)
                if layer_visibility is not None and not layer_visibility.get(layer, True):
                    continue
                old_pen, _ = select_pen(pl.color, max(0.05,float(pl.line_width)))
                try:
                    def world(lx,ly):
                        rx,ry=rotate_point(lx,ly,pl.rotation); return pl.x+rx,pl.y+ry
                    for prim in symbol_primitives(pl.symbol,pl.size):
                        typ=prim[0]
                        if typ=="line": draw_segment(mappt(*world(prim[1],prim[2])),mappt(*world(prim[3],prim[4])))
                        elif typ=="circle":
                            _,cx,cy,r=prim; wc=world(cx,cy)
                            a=mappt(wc[0]-r,wc[1]+r); b=mappt(wc[0]+r,wc[1]-r)
                            win32gui.Ellipse(hdc,min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
                        elif typ=="arc":
                            _,cx,cy,r,a1,a2=prim
                            pts=arc_world_points(cx,cy,r,a1,a2,world)
                            draw_polyline(mappt(*q) for q in pts)
                        elif typ=="polyline": draw_polyline(mappt(*world(x,y)) for x,y in prim[1])
                        elif typ in {"text","upright_text"}:
                            _,x,y,t,h=prim; wx,wy=world(x,y)
                            text_rotation=0.0 if typ=="upright_text" else pl.rotation
                            draw_text_world(wx,wy,t,h,text_rotation,pl.color,True)
                finally:
                    win32gui.SelectObject(hdc,old_pen)

            # Fri tekst/rumnavne.
            if layer_visibility is None or layer_visibility.get(FREE_TEXT_LAYER,True):
                for item in texts:
                    if str(item.text).strip():
                        draw_text_world(item.x,item.y,item.text,item.height,item.rotation,item.color,False)

            # Kabler/ledninger. Samme kosmetiske lane-separation som PDF'en.
            visible_cables=[cb for cb in cables if layer_visibility is None or layer_visibility.get(cb.layer,True)]
            avg_dpi=max((dpi_x+dpi_y)*.5,1.0); avg_scale=max((sx+sy)*.5,1e-12)
            lane_world=(5.0/72.0*avg_dpi)/avg_scale
            fan_world=(12.0/72.0*avg_dpi)/avg_scale
            cable_visuals=cable_visual_paths(visible_cables,lane_world,fan_length=fan_world)
            for cable in cables:
                if not cable_visible_in_layers(cable,layer_visibility):
                    continue
                display_points=cable_visuals.get(id(cable),cable.points)
                if len(display_points)<2:continue
                old_pen,_=select_pen(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR),max(0.05,float(cable.line_width)),getattr(cable,"line_style",DEFAULT_CABLE_LINE_STYLE))
                try:draw_polyline(mappt(float(x),float(y)) for x,y in display_points)
                finally:win32gui.SelectObject(hdc,old_pen)

            if room_layer_visible and room_labels_visible:
                # draw_text_world tager en verdenshøjde; omregn fra faste 9 pt,
                # så Windows-print matcher PDF'ens kosmetiske rumtekst.
                room_h_world=(9.0/72.0*dpi_y)/max(sy*.78,1e-12)
                for room in rooms:
                    label=room_output_label(room,room_codes_visible)
                    if label:
                        draw_text_world(getattr(room,"label_x",0.0),getattr(room,"label_y",0.0),label,
                                        room_h_world,0.0,getattr(room,"color","#0f766e"),True)

            # Diskret page-space metadata oven på vektorerne. Den har fast fysisk
            # skriftstørrelse ligesom PDF-eksporten, så den ikke eksploderer i
            # størrelse ved zoom.
            if layer_visibility is None or layer_visibility.get(META_LAYER, True):
                try: fs_pt=max(5.5,min(8.0,float(annotation_font_size)-1.5))
                except Exception: fs_pt=6.5
                font_px=max(6,int(round(fs_pt/72.0*dpi_y)))
                lf=win32gui.LOGFONT(); lf.lfHeight=-font_px; lf.lfWeight=400; lf.lfFaceName="Arial"
                font=win32gui.CreateFontIndirect(lf); created_objects.append(font)
                old_font=win32gui.SelectObject(hdc,font)
                white_brush=win32gui.CreateSolidBrush(win32api.RGB(255,255,255)); created_objects.append(white_brush)
                old_b=win32gui.SelectObject(hdc,white_brush)
                white_pen=win32gui.CreatePen(win32con.PS_SOLID,1,win32api.RGB(255,255,255)); created_objects.append(white_pen)
                old_p=win32gui.SelectObject(hdc,white_pen)
                win32gui.SetBkMode(hdc,win32con.TRANSPARENT); win32gui.SetTextColor(hdc,colorref("#176b3a"))
                try:
                    pad=max(1,int(round(dpi_x/300.0)))
                    gap=max(2,int(round(5.0/72.0*dpi_x)))
                    for pl in placements:
                        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):continue
                        assoc=association_display(pl)
                        if assoc:
                            ax,ay=association_world_point(pl); rx,ry=mappt(ax,ay)
                            tw,th=win32gui.GetTextExtentPoint32(hdc,assoc)
                            win32gui.Rectangle(hdc,rx-pad,ry-th-pad,rx+tw+pad,ry+pad)
                            win32gui.SetTextColor(hdc,colorref("#285d9b")); win32gui.TextOut(hdc,rx,ry-th,assoc)
                            win32gui.SetTextColor(hdc,colorref("#176b3a"))
                        lines=symbol_annotation_lines(pl,annotation_style)
                        if not lines:continue
                        x,y=mappt(pl.x,pl.y); x+=gap; y-=gap
                        sizes=[win32gui.GetTextExtentPoint32(hdc,str(t)) for t in lines]
                        bw=max((q[0] for q in sizes),default=1)+2*pad; bh=sum(q[1] for q in sizes)+2*pad
                        top=y-bh
                        win32gui.Rectangle(hdc,x-pad,top-pad,x+bw,y+pad)
                        yy=top+pad
                        for line,sz in zip(lines,sizes):
                            win32gui.TextOut(hdc,x,yy,str(line)); yy+=sz[1]
                    for cable in cables:
                        if not cable_visible_in_layers(cable,layer_visibility):continue
                        text=cable_plan_label(cable)
                        if text:
                            wx,wy=polyline_label_point(cable_visuals.get(id(cable),cable.points)); x,y=mappt(wx,wy); x+=gap; y-=gap
                            tw,th=win32gui.GetTextExtentPoint32(hdc,text)
                            win32gui.Rectangle(hdc,x-pad,y-th-pad,x+tw+pad,y+pad)
                            win32gui.TextOut(hdc,x,y-th,text)
                        for rec in cable_section_spec_labels(cable):
                            spec=str(rec.get("cable_spec") or "").strip()
                            if not spec: continue
                            wx,wy=rec.get("point",(0.0,0.0)); x,y=mappt(wx,wy); x+=gap; y+=gap
                            tw,th=win32gui.GetTextExtentPoint32(hdc,spec)
                            win32gui.Rectangle(hdc,x-pad,y-th-pad,x+tw+pad,y+pad)
                            win32gui.SetTextColor(hdc,colorref("#7c3f00")); win32gui.TextOut(hdc,x,y-th,spec)
                            win32gui.SetTextColor(hdc,colorref("#176b3a"))
                finally:
                    win32gui.SelectObject(hdc,old_p); win32gui.SelectObject(hdc,old_b); win32gui.SelectObject(hdc,old_font)

        finally:
            win32gui.SelectObject(hdc, old_brush)
            if page_started:
                try: win32print.EndPage(hdc)
                finally: page_started = False
            if doc_started:
                try: win32print.EndDoc(hdc)
                finally: doc_started = False

        return pname
    except Exception:
        # Hvis et job allerede er startet kan EndDoc fejle; Windows rydder DC'en
        # ved DeleteDC. Vi genkaster den oprindelige fejl til GUI'en.
        raise
    finally:
        if hdc and doc_started:
            try: win32print.AbortDoc(hdc)
            except Exception: pass
        # GDI-objekter må først slettes efter de ikke længere er valgt i DC'en.
        for obj in reversed(created_objects):
            try: win32gui.DeleteObject(obj)
            except Exception: pass
        if hdc:
            try: win32gui.DeleteDC(hdc)
            except Exception: pass
        if hprinter:
            try: win32print.ClosePrinter(hprinter)
            except Exception: pass
