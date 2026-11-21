"""PDF-montagerapport for PL-dåser."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as pdfcanvas

from elplan_core.associations import light_output_associations
from elplan_core.constants import APP_NAME, APP_VERSION
from elplan_core.pl_box.model import (
    PL_OUTLET_TYPES,
    normalize_pl_box_orientation,
    normalize_pl_outlet_type,
    pl_box_conductor_key,
    pl_box_port_layout,
    pl_box_status,
    pl_outlet_profile,
    pl_splice_member_keys,
    reconcile_pl_box_entries,
)
from elplan_core.pl_box.wago import (
    pl_montage_status,
    reconcile_pl_box_splices,
)
from elplan_core.pl_box.wiring import (
    cable_legs_at_symbol,
    pl_box_conductors,
    pl_expected_switch_connections,
    pl_wiring_function_caption,
    placement_identification_caption,
    reconcile_pl_box_wiring,
)

def _pdf_wrap_lines(text, font_name, font_size, max_width, max_lines=3):
    words=str(text or "").replace("\n"," ").split()
    if not words:return []
    lines=[]; current=""
    for word in words:
        candidate=(current+" "+word).strip()
        if not current or stringWidth(candidate,font_name,font_size)<=max_width:
            current=candidate; continue
        lines.append(current); current=word
        if len(lines)>=max_lines:break
    if len(lines)<max_lines and current:lines.append(current)
    if len(lines)==max_lines and words:
        # Gør det synligt at teksten er afkortet uden at være afhængig af Unicode-ellipsis.
        last=lines[-1]
        while last and stringWidth(last+"...",font_name,font_size)>max_width:last=last[:-1]
        lines[-1]=last.rstrip()+"..." if last.rstrip()!=str(text or "").strip() else last
    return lines


def _pdf_fit_text(text, font_name, font_size, max_width):
    """Kort tekst af med ASCII-punkter, så tabelceller ikke overlapper."""
    value=str(text or "")
    if stringWidth(value,font_name,font_size)<=max_width:
        return value
    suffix="..."
    while value and stringWidth(value+suffix,font_name,font_size)>max_width:
        value=value[:-1]
    return value.rstrip()+suffix if value else suffix


def pl_report_wiring_rows(placement, placements, cables) -> list[dict]:
    """Byg en entydig, printvenlig lederliste for én PL-dåse.

    Rækkerne beskriver den fysiske leder fra kabelindføringen til dens faktiske
    montagedestination: direkte lampeudtagsklemme, Wago med bro, ren
    Wago-sløjfe eller løs/ikke fordelt leder. Funktionen bruges af PDF-rapporten
    og er bevidst uafhængig af Qt-grafikken.
    """
    legs=cable_legs_at_symbol(cables,str(getattr(placement,"uid","") or ""))
    entries=reconcile_pl_box_entries(getattr(placement,"pl_box_entries",{}),legs)
    wiring=reconcile_pl_box_wiring(getattr(placement,"pl_box_wiring",[]),legs)
    splices=reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),wiring,legs)
    associations=light_output_associations(placement)
    outlet_type=normalize_pl_outlet_type(getattr(placement,"lamp_outlet_type","generic"))
    profile=pl_outlet_profile(outlet_type,associations)
    terminal_by_fid={str(t.get("function_id","") or ""):str(t.get("label") or "") for t in profile.get("terminals",[]) if str(t.get("function_id","") or "")}

    port_by_leg={}
    for raw_port,entry in entries.items():
        key=(str(entry.get("cable_uid","") or ""),int(entry.get("point_index",0) or 0),str(entry.get("leg","") or ""))
        try: port_by_leg[key]=int(raw_port)
        except (TypeError,ValueError): continue

    wiring_by_key={pl_box_conductor_key(row):row for row in wiring}
    splice_by_member={}
    for splice in splices:
        for key in pl_splice_member_keys(splice):
            splice_by_member[key]=splice

    rows=[]
    seen_leg_keys=set()
    for meta in pl_box_conductors(legs):
        leg_key=(str(meta.get("cable_uid","") or ""),int(meta.get("point_index",0) or 0),str(meta.get("leg","") or ""))
        port=port_by_leg.get(leg_key)
        if port is None:
            continue
        seen_leg_keys.add(leg_key)
        key=pl_box_conductor_key(meta)
        wr=wiring_by_key.get(key,{})
        fid=str(wr.get("function","") or "")
        splice=splice_by_member.get(key)
        terminal_label=terminal_by_fid.get(fid,"")
        function_caption=pl_wiring_function_caption(fid,associations,outlet_type) if fid else "Ikke fordelt"
        if fid.startswith("switch:"):
            letter=fid.split(":",1)[1]
            if outlet_type=="nordtronic_zigbee":
                switch_name=f"P · tryk {letter}" if letter and letter!="lamp" else "P · trykindgang"
            else:
                switch_name=f"Tænding {letter}" if letter and letter!="lamp" else "Tænding"
            function_short=f"{switch_name} ({terminal_label})" if terminal_label and terminal_label not in switch_name else switch_name
        else:
            function_short=terminal_label or function_caption.replace("→","->").split(" -> ",1)[0]
        if splice is not None:
            article=str(splice.get("article_no","") or "Wago").strip() or "Wago"
            if bool(splice.get("connects_to_outlet",True)):
                destination=f"WAGO {article} -> {function_short}"
                route="wago_outlet"
            else:
                destination=f"WAGO {article} (kun sløjfe)"
                route="wago_loop"
        elif not fid:
            destination="Løs / ikke fordelt"
            route="loose"
        elif terminal_label:
            destination=f"{function_short} - direkte"
            route="direct"
        else:
            destination=f"{function_short} - ingen fysisk klemme"
            route="unsupported"
        rows.append({
            "port":port,
            "cable":str(meta.get("cable_display") or meta.get("cable_id") or "Kabel"),
            "cable_spec":str(meta.get("cable_spec") or ""),
            "leg_caption":str(meta.get("leg_caption") or ""),
            "core_id":str(meta.get("core_id") or ""),
            "color_name":str(meta.get("color_name") or meta.get("display") or meta.get("core_id") or "Leder"),
            "color":str(meta.get("color") or "#64748b"),
            "function_id":fid,
            "function":function_short,
            "destination":destination,
            "route":route,
        })

    # Hvis kabeltypen ikke har en kendt 3G/5G/7G-profil, vises den stadig i
    # lederafsnittet som en eksplicit ukendt opbygning i stedet for at forsvinde.
    leg_by_key={(str(l.get("cable_uid","") or ""),int(l.get("point_index",0) or 0),str(l.get("leg","") or "")):l for l in legs}
    for leg_key,port in port_by_leg.items():
        if leg_key in seen_leg_keys:
            continue
        leg=leg_by_key.get(leg_key,{})
        rows.append({
            "port":port,"cable":str(leg.get("cable_display") or leg.get("cable_id") or "Kabel"),
            "cable_spec":str(leg.get("cable_spec") or ""),"leg_caption":str(leg.get("leg_caption") or ""),
            "core_id":"","color_name":"Ukendt","color":"#94a3b8","function_id":"",
            "function":"","destination":"Ukendt lederopbygning - kontroller kabelartikel/datablad","route":"unknown",
        })

    core_order={"pe":0,"blue":1,"brown":2,"black":3,"grey":4,"red":5,"white":6}
    rows.sort(key=lambda r:(int(r.get("port",99)),core_order.get(str(r.get("core_id") or ""),99),str(r.get("color_name") or "")))
    return rows


def _draw_pl_report_box(c, placement, placements, cables, x, y, w, h):
    """Tegn ét printvenligt PL-montagekort med tydelig lederfordeling."""
    legs=cable_legs_at_symbol(cables,str(getattr(placement,"uid","") or ""))
    entries=reconcile_pl_box_entries(getattr(placement,"pl_box_entries",{}),legs)
    wiring=reconcile_pl_box_wiring(getattr(placement,"pl_box_wiring",[]),legs)
    splices=reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),wiring,legs)
    orientation=normalize_pl_box_orientation(getattr(placement,"pl_box_orientation",0))
    outlet_type=normalize_pl_outlet_type(getattr(placement,"lamp_outlet_type","generic"))
    requirements=pl_expected_switch_connections(placement,placements,cables)
    montage=pl_montage_status(outlet_type,light_output_associations(placement),wiring,splices,requirements,legs)
    box_status=pl_box_status(entries,legs)
    wiring_rows=pl_report_wiring_rows(placement,placements,cables)
    state=str(montage.get("state") or "ready")
    status_text={"ready":"Klar","warning":"Kontrol","error":"Fejl"}.get(state,"Kontrol")
    status_fill={"ready":"#dcfce7","warning":"#fef3c7","error":"#fee2e2"}.get(state,"#f1f5f9")
    status_stroke={"ready":"#16a34a","warning":"#d97706","error":"#dc2626"}.get(state,"#64748b")

    c.setStrokeColor(colors.HexColor("#94a3b8")); c.setLineWidth(0.8); c.setFillColor(colors.white); c.roundRect(x,y,w,h,7,stroke=1,fill=1)
    header_h=54.0
    c.setFillColor(colors.HexColor("#f8fafc")); c.roundRect(x+0.8,y+h-header_h,w-1.6,header_h-0.8,6,stroke=0,fill=1)
    group=str(getattr(placement,"group","") or "").strip()
    label=str(getattr(placement,"label","") or "").strip()
    ident=placement_identification_caption(placement)
    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",11); c.drawString(x+12,y+h-17,f"PL-dåse {ident}")
    c.setFont("Helvetica-Bold",7.0); c.setFillColor(colors.HexColor("#334155"))
    identification=f"Gruppe/kreds: {group or '—'}   |   Mærkning: {label or '—'}"
    c.drawString(x+12,y+h-30,_pdf_fit_text(identification,"Helvetica-Bold",7.0,w-95))
    c.setFont("Helvetica",7.2); c.setFillColor(colors.HexColor("#64748b"))
    outlet_caption=PL_OUTLET_TYPES.get(outlet_type,"Generisk PL")
    c.drawString(x+12,y+h-43,f"{outlet_caption}  |  Orientering {orientation}°  |  Indføringer {box_status['used']}/{box_status['capacity']}")
    pill_w=max(42.0,stringWidth(status_text,"Helvetica-Bold",7.5)+16)
    c.setFillColor(colors.HexColor(status_fill)); c.setStrokeColor(colors.HexColor(status_stroke)); c.roundRect(x+w-pill_w-10,y+h-27,pill_w,18,7,stroke=1,fill=1)
    c.setFillColor(colors.HexColor(status_stroke)); c.setFont("Helvetica-Bold",7.5); c.drawCentredString(x+w-pill_w/2-10,y+h-21,status_text)

    inner_x=x+10; inner_w=w-20
    content_top=y+h-header_h-8
    top_h=214.0
    top_y=content_top-top_h
    diagram_w=min(226.0,inner_w*0.43)
    table_x=inner_x+diagram_w+10
    table_w=inner_x+inner_w-table_x

    # --- Fysisk orientering / kabelindføringer ---
    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",8.2); c.drawString(inner_x,content_top-8,"Fysisk orientering og kabelindføringer")
    c.setStrokeColor(colors.HexColor("#e2e8f0")); c.line(inner_x,content_top-13,inner_x+inner_w,content_top-13)

    # Referencepil til plantegningens top.
    arrow_x=inner_x+10; arrow_y=content_top-27
    c.setStrokeColor(colors.HexColor("#64748b")); c.setFillColor(colors.HexColor("#475569")); c.setLineWidth(1)
    c.line(arrow_x,arrow_y-15,arrow_x,arrow_y); c.line(arrow_x,arrow_y,arrow_x-3,arrow_y-5); c.line(arrow_x,arrow_y,arrow_x+3,arrow_y-5)
    c.setFont("Helvetica",6.3); c.drawString(arrow_x+6,arrow_y-5,"Plantegning op")

    # Fysisk dåsetegning med roterede indføringer.
    cx=inner_x+diagram_w*0.52; cy=top_y+top_h*0.45; bd=min(96.0,diagram_w*0.46,top_h*0.48)
    bx=cx-bd/2; by=cy-bd/2
    c.setFillColor(colors.HexColor("#f8fafc")); c.setStrokeColor(colors.HexColor("#475569")); c.setLineWidth(1.2); c.roundRect(bx,by,bd,bd,9,stroke=1,fill=1)
    cd=bd*0.68; c.setFillColor(colors.white); c.circle(cx,cy,cd/2,stroke=1,fill=1); c.line(cx-7,cy,cx+7,cy); c.line(cx,cy-7,cx,cy+7)
    if orientation in {0,180}:
        for lx in (bx-15,bx+bd-3):
            c.setFillColor(colors.HexColor("#f8fafc")); c.roundRect(lx,cy-16,18,32,4,stroke=1,fill=1); c.circle(lx+9,cy,2.6,stroke=1,fill=0)
    else:
        for ly in (by-15,by+bd-3):
            c.setFillColor(colors.HexColor("#f8fafc")); c.roundRect(cx-16,ly,32,18,4,stroke=1,fill=1); c.circle(cx,ly+9,2.6,stroke=1,fill=0)

    layout=pl_box_port_layout(orientation)
    port_w=42.0; port_h=23.0; gap=2.0
    group_w=port_w*3+gap*2; group_h=port_h*3+gap*2
    top_port_y=by+bd+12; bottom_port_y=by-port_h-12; left_port_x=bx-port_w-12; right_port_x=bx+bd+12
    gx=cx-group_w/2; gy=cy-group_h/2
    leg_by_key={(str(l.get("cable_uid","") or ""),int(l.get("point_index",0) or 0),str(l.get("leg","") or "")):l for l in legs}
    for port,(side,index) in layout.items():
        if side=="top":px,py=gx+index*(port_w+gap),top_port_y
        elif side=="bottom":px,py=gx+index*(port_w+gap),bottom_port_y
        elif side=="left":px,py=left_port_x,gy+(2-index)*(port_h+gap)
        else:px,py=right_port_x,gy+(2-index)*(port_h+gap)
        entry=entries.get(str(port)); leg=None
        if entry:
            key=(str(entry.get("cable_uid","") or ""),int(entry.get("point_index",0) or 0),str(entry.get("leg","") or "")); leg=leg_by_key.get(key)
        c.setFillColor(colors.white if leg else colors.HexColor("#f8fafc")); c.setStrokeColor(colors.HexColor("#64748b")); c.setLineWidth(0.7); c.roundRect(px,py,port_w,port_h,3,stroke=1,fill=1)
        c.setFillColor(colors.HexColor("#334155")); c.setFont("Helvetica-Bold",6.0); c.drawString(px+3,py+port_h-7,str(port))
        if leg:
            cid=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel"); spec=str(leg.get("cable_spec") or "")
            c.setFont("Helvetica-Bold",5.5); c.setFillColor(colors.HexColor("#991b1b")); c.drawCentredString(px+port_w/2,py+9.5,_pdf_fit_text(cid,"Helvetica-Bold",5.5,port_w-5))
            c.setFont("Helvetica",5.1); c.setFillColor(colors.HexColor("#64748b")); c.drawCentredString(px+port_w/2,py+3.2,_pdf_fit_text(spec,"Helvetica",5.1,port_w-5))
            c.setStrokeColor(colors.HexColor("#475569")); c.setLineWidth(3.6)
            if side=="top":c.line(px+port_w/2,py,bx+(px+port_w/2-gx)/max(1,group_w)*bd,by+bd)
            elif side=="bottom":c.line(px+port_w/2,py+port_h,bx+(px+port_w/2-gx)/max(1,group_w)*bd,by)
            elif side=="left":c.line(px+port_w,py+port_h/2,bx,py+port_h/2)
            else:c.line(px,py+port_h/2,bx+bd,py+port_h/2)
        else:
            c.setFont("Helvetica",5.2); c.setFillColor(colors.HexColor("#94a3b8")); c.drawCentredString(px+port_w/2,py+6.5,"Ledig")

    # Kabelindføringstabel til højre.
    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",7.5); c.drawString(table_x,content_top-27,"Kabelindføringer")
    row_y=content_top-43; row_h=20.0
    c.setFont("Helvetica-Bold",5.7); c.setFillColor(colors.HexColor("#64748b"))
    for tx,text in ((table_x,"Nr."),(table_x+22,"Kabel"),(table_x+96,"Type"),(table_x+145,"Forbindelse")):
        c.drawString(tx,row_y+5,text)
    row_y-=3
    for port in range(1,7):
        row_y-=row_h
        if port%2==0:
            c.setFillColor(colors.HexColor("#f8fafc")); c.rect(table_x,row_y,table_w,row_h,stroke=0,fill=1)
        c.setFillColor(colors.HexColor("#334155")); c.setFont("Helvetica-Bold",6.2); c.drawString(table_x+2,row_y+6,str(port))
        entry=entries.get(str(port)); leg=None
        if entry:
            key=(str(entry.get("cable_uid","") or ""),int(entry.get("point_index",0) or 0),str(entry.get("leg","") or "")); leg=leg_by_key.get(key)
        if leg:
            c.setFont("Helvetica",6.0)
            c.drawString(table_x+22,row_y+6,_pdf_fit_text(str(leg.get("cable_display") or leg.get("cable_id") or "Kabel"),"Helvetica",6.0,70))
            c.drawString(table_x+96,row_y+6,_pdf_fit_text(str(leg.get("cable_spec") or ""),"Helvetica",6.0,45))
            c.drawString(table_x+145,row_y+6,_pdf_fit_text(str(leg.get("leg_caption") or ""),"Helvetica",6.0,max(30,table_w-148)))
        else:
            c.setFillColor(colors.HexColor("#94a3b8")); c.setFont("Helvetica",6.0); c.drawString(table_x+22,row_y+6,"Ledig")

    # --- Tydelig lederfordeling ---
    wiring_h=270.0
    wiring_y=top_y-wiring_h-8
    c.setFillColor(colors.HexColor("#ffffff")); c.setStrokeColor(colors.HexColor("#cbd5e1")); c.setLineWidth(0.7); c.roundRect(inner_x,wiring_y,inner_w,wiring_h,5,stroke=1,fill=1)
    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",8.4); c.drawString(inner_x+8,wiring_y+wiring_h-15,"Lederfordeling - fysisk montage")
    c.setFillColor(colors.HexColor("#64748b")); c.setFont("Helvetica",5.9); c.drawString(inner_x+8,wiring_y+wiring_h-25,"Hver række er én fysisk leder. Destination viser direkte klemme, Wago med bro eller ren Wago-sløjfe.")

    col_gap=10.0
    max_per_col=21
    col_count=1 if len(wiring_rows)<=max_per_col else 2
    col_w=(inner_w-16-col_gap*(col_count-1))/col_count
    col_xs=[inner_x+8+i*(col_w+col_gap) for i in range(col_count)]
    header_y=wiring_y+wiring_h-42
    row_h=10.35
    # Almindelige PL-dåser med højst 21 ledere får én bred tabel. Først ved
    # større lederantal deles listen i to kolonner, så tekst ikke unødigt
    # forkortes på de mest almindelige 3G/5G/7G-installationer.
    if col_count==1:
        cable_off,lead_off,dest_off=26.0,132.0,225.0
        cable_width,color_width=99.0,54.0
        body_font=5.9
    else:
        cable_off,lead_off,dest_off=24.0,73.0,125.0
        cable_width,color_width=45.0,31.0
        body_font=5.45
    for col_x in col_xs:
        c.setFillColor(colors.HexColor("#f1f5f9")); c.rect(col_x,header_y-1,col_w,12,stroke=0,fill=1)
        c.setFillColor(colors.HexColor("#475569")); c.setFont("Helvetica-Bold",5.6 if col_count==1 else 5.4)
        c.drawString(col_x+2,header_y+3,"Indf.")
        c.drawString(col_x+cable_off,header_y+3,"Kabel")
        c.drawString(col_x+lead_off,header_y+3,"Leder")
        c.drawString(col_x+dest_off,header_y+3,"Destination")

    display_rows=wiring_rows[:max_per_col*2]
    for index,row in enumerate(display_rows):
        col=index//max_per_col; ridx=index%max_per_col
        col_x=col_xs[col]; ry=header_y-4-(ridx+1)*row_h
        port=int(row.get("port",0) or 0)
        if ridx==0 or (index>0 and int(display_rows[index-1].get("port",0) or 0)!=port):
            c.setStrokeColor(colors.HexColor("#e2e8f0")); c.setLineWidth(0.45); c.line(col_x,ry+row_h-1,col_x+col_w,ry+row_h-1)
        c.setFillColor(colors.HexColor("#334155")); c.setFont("Helvetica-Bold",5.7 if col_count==1 else 5.55); c.drawString(col_x+3,ry+2.4,str(port))
        c.setFont("Helvetica",body_font); c.drawString(col_x+cable_off,ry+2.4,_pdf_fit_text(str(row.get("cable") or ""),"Helvetica",body_font,cable_width))

        # Farveprøve + farvenavn. Hvid får mørk kontur, PE får gul stribe.
        sw_x=col_x+lead_off+1; sw_y=ry+4.7
        lead_color=str(row.get("color") or "#64748b")
        if str(row.get("core_id") or "")=="white":
            c.setStrokeColor(colors.HexColor("#64748b")); c.setLineWidth(3.8); c.line(sw_x,sw_y,sw_x+13,sw_y)
            c.setStrokeColor(colors.white); c.setLineWidth(2.5); c.line(sw_x,sw_y,sw_x+13,sw_y)
        else:
            c.setStrokeColor(colors.HexColor(lead_color)); c.setLineWidth(3.4); c.line(sw_x,sw_y,sw_x+13,sw_y)
        if str(row.get("core_id") or "")=="pe":
            c.setStrokeColor(colors.HexColor("#facc15")); c.setLineWidth(1.1); c.line(sw_x+2,sw_y,sw_x+5,sw_y); c.line(sw_x+8,sw_y,sw_x+11,sw_y)
        c.setFillColor(colors.HexColor("#334155")); c.setFont("Helvetica",5.55 if col_count==1 else 5.25); c.drawString(sw_x+17,ry+2.4,_pdf_fit_text(str(row.get("color_name") or ""),"Helvetica",5.55 if col_count==1 else 5.25,color_width))

        route=str(row.get("route") or "")
        dest_color={"wago_outlet":"#92400e","wago_loop":"#92400e","loose":"#b45309","unsupported":"#b91c1c","unknown":"#b45309"}.get(route,"#334155")
        dest_font="Helvetica-Bold" if route.startswith("wago") else "Helvetica"
        c.setFillColor(colors.HexColor(dest_color)); c.setFont(dest_font,body_font)
        c.drawString(col_x+dest_off,ry+2.4,_pdf_fit_text(str(row.get("destination") or ""),dest_font,body_font,col_w-dest_off-4))

    if len(wiring_rows)>max_per_col*2:
        c.setFillColor(colors.HexColor("#b91c1c")); c.setFont("Helvetica-Bold",5.8); c.drawRightString(inner_x+inner_w-8,wiring_y+5,f"+ {len(wiring_rows)-max_per_col*2} ledere - se avanceret lederplan")
    elif not wiring_rows:
        c.setFillColor(colors.HexColor("#94a3b8")); c.setFont("Helvetica",7); c.drawString(inner_x+8,wiring_y+wiring_h/2,"Ingen kendte lederprofiler på de placerede kabler.")

    # --- Wago / terminaler / montagekontrol ---
    bottom_y=y+12
    bottom_h=max(82.0,wiring_y-bottom_y-8)
    split=inner_x+inner_w*0.54
    c.setStrokeColor(colors.HexColor("#cbd5e1")); c.setLineWidth(0.7); c.roundRect(inner_x,bottom_y,inner_w,bottom_h,5,stroke=1,fill=0)
    c.line(split,bottom_y+6,split,bottom_y+bottom_h-6)

    c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",7.8); c.drawString(inner_x+8,bottom_y+bottom_h-15,"Wago / samlinger")
    wy=bottom_y+bottom_h-27
    c.setFont("Helvetica",6.0); c.setFillColor(colors.HexColor("#475569"))
    if splices:
        for splice in splices[:5]:
            fid=str(splice.get("function") or ""); art=str(splice.get("article_no") or "artikel ikke valgt"); mode="1 bro til udtag" if splice.get("connects_to_outlet",True) else "kun sløjfe"; members=len(pl_splice_member_keys(splice))
            function_label=pl_wiring_function_caption(fid,light_output_associations(placement)).replace("→","->").split(" -> ",1)[0]
            text=f"{function_label}: {art} | {members} leder(e) | {mode}"
            c.drawString(inner_x+8,wy,_pdf_fit_text(text,"Helvetica",6.0,split-inner_x-16)); wy-=10
        if len(splices)>5:
            c.setFillColor(colors.HexColor("#64748b")); c.setFont("Helvetica-Bold",5.8)
            c.drawString(inner_x+8,wy,f"+ {len(splices)-5} yderligere Wago-samling(er) i PL-dåsen")
    else:
        c.drawString(inner_x+8,wy,"Ingen Wago-samlinger")

    mx=split+8; my=bottom_y+bottom_h-15
    c.setFillColor(colors.HexColor(status_stroke)); c.setFont("Helvetica-Bold",7.8); c.drawString(mx,my,f"Montagekontrol: {status_text}")
    my-=12
    # Terminalbelastning giver installatøren en hurtig fysisk checkliste.
    c.setFillColor(colors.HexColor("#334155")); c.setFont("Helvetica",5.8)
    term_parts=[]
    for terminal in montage.get("terminals",[]):
        label=str(terminal.get("label") or terminal.get("function_id") or "")
        count=int(terminal.get("terminal_count",0) or 0); cap=terminal.get("capacity")
        suffix=f"{count}/{cap}" if cap else str(count)
        if terminal.get("has_wago"):suffix+= " Wago"
        term_parts.append(f"{label} {suffix}")
    for line in _pdf_wrap_lines(" | ".join(term_parts),"Helvetica",5.8,inner_x+inner_w-mx-8,2):
        c.drawString(mx,my,line); my-=8
    messages=list(montage.get("errors") or [])+list(montage.get("warnings") or [])
    if not messages:messages=["Ingen kendte montagekonflikter."]
    c.setFont("Helvetica",5.7); c.setFillColor(colors.HexColor("#475569"))
    for msg in messages[:4]:
        for line in _pdf_wrap_lines(msg,"Helvetica",5.7,inner_x+inner_w-mx-8,2):
            c.drawString(mx,my,line); my-=7.2


def export_pl_box_report_pdf(path, placements, cables, project_name="") -> str:
    """Eksportér en A4-montagerapport med én tydelig PL-dåse pr. side.

    Én dåse pr. side giver plads til en komplet lederfordeling med op til 42
    fysiske 7G-ledere (seks indføringer) uden at gøre tekst/farver ulæselige.
    """
    target=Path(path)
    boxes=[p for p in (placements or []) if str(getattr(p,"symbol","") or "")=="light_connection"]
    boxes.sort(key=lambda p:(str(getattr(p,"group","") or ""),str(getattr(p,"label","") or ""),float(getattr(p,"y",0.0) or 0.0),float(getattr(p,"x",0.0) or 0.0)))
    page=A4; pw,ph=page; margin=28.0; page_header=36.0; footer=18.0
    card_h=ph-margin*2-page_header-footer; card_w=pw-margin*2
    c=pdfcanvas.Canvas(str(target),pagesize=page,pageCompression=1)
    generated=datetime.now().strftime("%d-%m-%Y %H:%M")
    page_count=max(1,len(boxes))
    for page_index in range(page_count):
        c.setFillColor(colors.HexColor("#0f172a")); c.setFont("Helvetica-Bold",14); c.drawString(margin,ph-margin-4,"PL-dåserapport")
        c.setFont("Helvetica",7); c.setFillColor(colors.HexColor("#64748b"))
        subtitle=str(project_name or "Projekt"); c.drawString(margin,ph-margin-17,f"{subtitle}  |  Orientering relativt til plantegningens top  |  Genereret {generated}")
        c.setStrokeColor(colors.HexColor("#cbd5e1")); c.line(margin,ph-margin-page_header+7,pw-margin,ph-margin-page_header+7)
        if boxes:
            top=ph-margin-page_header
            y=top-card_h
            _draw_pl_report_box(c,boxes[page_index],boxes,cables,margin,y,card_w,card_h)
        else:
            c.setFillColor(colors.HexColor("#64748b")); c.setFont("Helvetica",10); c.drawString(margin,ph/2,"Projektet indeholder ingen PL-lampesteder.")
        c.setFont("Helvetica",6.5); c.setFillColor(colors.HexColor("#94a3b8")); c.drawRightString(pw-margin,12,f"Side {page_index+1}/{page_count}  |  {APP_NAME} {APP_VERSION}")
        if page_index<page_count-1:c.showPage()
    c.save()
    return str(target)
