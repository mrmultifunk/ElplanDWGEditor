from __future__ import annotations

"""Enkel, printvenlig BOM-rapport med priser.

Rapporten er bevidst smallere end Excel-eksporten: kun varenummer,
beskrivelse, antal, enhedspris og beløb medtages. Detaljer, kilder, EAN,
prisstatus og links hører fortsat hjemme i den interaktive BOM og Excel.
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from elplan_catalog import price_display


BOM_PRINT_COLUMN_TITLES=("Varenr.","Beskrivelse","Antal","Enhedspris","Beløb")


def _fmt_qty(value) -> str:
    try:number=float(value or 0)
    except (TypeError,ValueError):number=0.0
    return str(int(round(number))) if abs(number-round(number))<1e-9 else f"{number:.2f}".replace(".",",")


def _fmt_money(value,currency="DKK") -> str:
    if value is None or str(value).strip()=="":return "-"
    try:number=float(value)
    except (TypeError,ValueError):return "-"
    amount=f"{number:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    return f"{amount} {str(currency or 'DKK').upper()}"


def prepare_bom_print_data(rows,price_vat_mode="excl"):
    """Formatér de fem synlige PDF-kolonner og beregn totaler pr. valuta."""
    converted=price_display.convert_bom_rows(rows,price_vat_mode)
    printable=[]; totals=defaultdict(float); priced=0
    for raw in converted:
        row=dict(raw or {})
        currency=str(row.get("price_currency","DKK") or "DKK").upper()
        unit=str(row.get("unit","stk") or "stk")
        price_unit=str(row.get("price_unit",unit) or unit)
        unit_price=row.get("unit_price")
        line_total=row.get("line_total")
        if line_total is not None and str(line_total).strip()!="":
            totals[currency]+=float(line_total); priced+=1
        context=" · ".join(x for x in (
            str(row.get("mounting_summary","") or "").strip(),
            str(row.get("purchase_status","") or "").strip(),
        ) if x)
        description=str(row.get("description","") or "Ukendt artikel")
        if context:description+=f" · {context}"
        printable.append({
            "article_no":str(row.get("article_no","") or ""),
            "description":description,
            "quantity":f"{_fmt_qty(row.get('qty',0))} {unit}",
            "unit_price":f"{_fmt_money(unit_price,currency)} / {price_unit}" if unit_price is not None else "-",
            "line_total":_fmt_money(line_total,currency),
        })
    return printable,dict(sorted(totals.items())),priced


def _font_names():
    """Brug DejaVu når den findes, ellers ReportLabs WinAnsi-fonte."""
    candidates=(
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf","C:/Windows/Fonts/arialbd.ttf"),
    )
    for regular,bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            try:
                pdfmetrics.registerFont(TTFont("ElplanBom",regular))
                pdfmetrics.registerFont(TTFont("ElplanBomBold",bold))
                return "ElplanBom","ElplanBomBold"
            except Exception:pass
    return "Helvetica","Helvetica-Bold"


def write_bom_pdf(path,rows,missing=None,*,project_name="",room_scope="Alle rum",
                  price_vat_mode="excl",filter_caption="",include_cables=True,
                  generated_at=None,room_rows=None):
    """Skriv en enkel A4 BOM med priser og returnér den endelige sti."""
    rows=list(rows or [])
    if not rows:raise ValueError("BOM'en indeholder ingen artikler.")
    target=Path(path)
    if target.suffix.casefold()!=".pdf":target=target.with_suffix(".pdf")
    target.parent.mkdir(parents=True,exist_ok=True)

    normal,bold=_font_names()
    prepared,totals,priced=prepare_bom_print_data(rows,price_vat_mode)
    missing=list(missing or [])
    room_rows=list(room_rows or [])
    generated=generated_at or datetime.now()
    vat_caption=price_display.vat_caption(price_vat_mode)
    project=str(project_name or "Elplan-projekt").strip() or "Elplan-projekt"
    scope=str(room_scope or "Alle rum").strip() or "Alle rum"

    styles=getSampleStyleSheet()
    title=ParagraphStyle("BomTitle",parent=styles["Title"],fontName=bold,fontSize=18,leading=21,textColor=colors.HexColor("#16384f"),spaceAfter=2*mm)
    subtitle=ParagraphStyle("BomSubtitle",parent=styles["Normal"],fontName=normal,fontSize=9,leading=12,textColor=colors.HexColor("#536675"),spaceAfter=4*mm)
    body=ParagraphStyle("BomBody",parent=styles["BodyText"],fontName=normal,fontSize=8.2,leading=10.4,textColor=colors.HexColor("#17242d"),wordWrap="CJK")
    body_right=ParagraphStyle("BomRight",parent=body,alignment=TA_RIGHT)
    small=ParagraphStyle("BomSmall",parent=body,fontSize=7.6,leading=9.6,textColor=colors.HexColor("#5a6872"))
    summary=ParagraphStyle("BomSummary",parent=body,fontName=bold,fontSize=9.2,leading=11.5,textColor=colors.HexColor("#16384f"))
    section_title=ParagraphStyle("BomSection",parent=title,fontSize=16,leading=19,spaceAfter=1.5*mm)
    room_title=ParagraphStyle("BomRoom",parent=title,fontSize=12.5,leading=15,spaceAfter=.8*mm)

    def article_table(items,style_key):
        data=[[Paragraph(x,ParagraphStyle(f"Hdr{style_key}{i}",parent=body,fontName=bold,fontSize=8,textColor=colors.white,alignment=TA_RIGHT if i>=2 else TA_LEFT)) for i,x in enumerate(BOM_PRINT_COLUMN_TITLES)]]
        for row in items:
            data.append([
                Paragraph(row["article_no"],body),Paragraph(row["description"],body),
                Paragraph(row["quantity"],body_right),Paragraph(row["unit_price"],body_right),
                Paragraph(row["line_total"],body_right),
            ])
        table=Table(data,colWidths=[28*mm,82*mm,20*mm,30*mm,30*mm],repeatRows=1,splitByRow=True,hAlign="LEFT")
        rules=[
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#235a75")),
            ("LINEBELOW",(0,0),(-1,0),.6,colors.HexColor("#16384f")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LINEBELOW",(0,1),(-1,-1),.3,colors.HexColor("#dce3e7")),
        ]
        for index in range(2,len(data),2):rules.append(("BACKGROUND",(0,index),(-1,index),colors.HexColor("#f6f8f9")))
        table.setStyle(TableStyle(rules))
        return table

    def total_table(section_totals,label,style_key):
        total_rows=[]
        if section_totals:
            for currency,value in section_totals.items():
                total_rows.append([Paragraph(label,summary),Paragraph(_fmt_money(value,currency),ParagraphStyle(f"TotalValue{style_key}{currency}",parent=summary,alignment=TA_RIGHT))])
        else:
            total_rows.append([Paragraph(label,summary),Paragraph("-",ParagraphStyle(f"TotalValue{style_key}",parent=summary,alignment=TA_RIGHT))])
        table=Table(total_rows,colWidths=[55*mm,45*mm],hAlign="RIGHT")
        table.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#e7f1f5")),
            ("BOX",(0,0),(-1,-1),.7,colors.HexColor("#8daebd")),
            ("LINEABOVE",(0,0),(-1,0),.7,colors.HexColor("#6d95a8")),
            ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        return table

    def footer(canvas,doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d8e0e5")); canvas.setLineWidth(.45)
        canvas.line(doc.leftMargin,12*mm,A4[0]-doc.rightMargin,12*mm)
        canvas.setFont(normal,7); canvas.setFillColor(colors.HexColor("#71808b"))
        canvas.drawString(doc.leftMargin,8.2*mm,"Elplan BOM")
        canvas.drawRightString(A4[0]-doc.rightMargin,8.2*mm,f"Side {doc.page}")
        canvas.restoreState()

    doc=SimpleDocTemplate(
        str(target),pagesize=A4,leftMargin=10*mm,rightMargin=10*mm,
        topMargin=11*mm,bottomMargin=17*mm,title=f"BOM - {project}",author="Elplan",
    )
    story=[Paragraph("BOM",title),Paragraph(project,subtitle)]
    meta=[scope,f"Priser {vat_caption}","Kabler medtaget" if include_cables else "Kabler skjult",generated.strftime("%d-%m-%Y %H:%M")]
    if str(filter_caption or "").strip() and str(filter_caption).strip().casefold()!="alle":meta.insert(1,f"Filter: {str(filter_caption).strip()}")
    meta_table=Table([[Paragraph(" | ".join(meta),small)]],colWidths=[190*mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#eef4f7")),
        ("BOX",(0,0),(-1,-1),.45,colors.HexColor("#cad8df")),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.extend([meta_table,Spacer(1,5*mm)])

    story.extend([article_table(prepared,"main"),Spacer(1,5*mm)])

    notes=[]
    if priced<len(prepared):notes.append(f"{len(prepared)-priced} af {len(prepared)} varelinjer mangler pris.")
    missing_symbols=sum(int(x.get("count",0) or 0) for x in missing if x.get("symbol")!="__cable__")
    missing_cables=sum(int(x.get("count",0) or 0) for x in missing if x.get("symbol")=="__cable__")
    missing_parts=[]
    if missing_symbols:missing_parts.append(f"{missing_symbols} symboldele")
    if missing_cables:missing_parts.append(f"{missing_cables} kabelstræk")
    if missing_parts:notes.append("Mangler artikeltilknytning: "+" og ".join(missing_parts)+".")
    tail=[total_table(totals,f"Total {vat_caption}","main")]
    if notes:tail.extend([Spacer(1,2.5*mm),Paragraph(" ".join(notes),small)])
    story.append(KeepTogether(tail))

    if room_rows:
        grouped={}; order=[]
        for raw in room_rows:
            row=dict(raw or {}); room=str(row.get("room_display","") or "Uden rum").strip() or "Uden rum"
            if room not in grouped:grouped[room]=[]; order.append(room)
            grouped[room].append(row)
        story.extend([
            PageBreak(),Paragraph("BOM pr. rum",section_title),
            Paragraph(
                "Hvert rum summeres separat. Summen af rum kan være højere end hovedtotalen, "
                "når en fysisk vare med vilje er tilføjet til et ekstra BOM-rum.",small,
            ),Spacer(1,5*mm),
        ])
        for index,room in enumerate(order):
            if index:story.append(CondPageBreak(58*mm))
            room_prepared,room_totals,room_priced=prepare_bom_print_data(grouped[room],price_vat_mode)
            story.extend([
                Paragraph(room,room_title),
                Paragraph(f"{len(room_prepared)} varelinjer",small),Spacer(1,2.2*mm),
                article_table(room_prepared,f"room{index}"),Spacer(1,2.5*mm),
            ])
            room_tail=[total_table(room_totals,f"Delsum {vat_caption}",f"room{index}")]
            if room_priced<len(room_prepared):
                room_tail.extend([Spacer(1,1.5*mm),Paragraph(f"{len(room_prepared)-room_priced} varelinjer mangler pris i dette rum.",small)])
            story.extend([KeepTogether(room_tail),Spacer(1,5*mm)])
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return target
