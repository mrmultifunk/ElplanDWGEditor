from __future__ import annotations

"""Letvægtskontrol af den beregnede BOM uden at ændre projektdata."""

from datetime import date, datetime
import math


def _parse_date(value):
    text=str(value or "").strip()
    if not text:return None
    try:return datetime.fromisoformat(text[:10]).date()
    except (TypeError,ValueError):return None


def _finding(severity,code,article_no,area,message,suggestion,*,label=""):
    return {
        "severity":severity,"code":code,"article_no":str(article_no or ""),
        "label":str(label or article_no or ""),"area":area,
        "message":message,"suggestion":suggestion,
    }


def audit_bom(rows, missing=None, *, today=None, stale_days=30):
    """Kontrollér priser, artikler og pakningsgrundlag i en færdig BOM."""
    today=today or date.today()
    findings=[]
    for raw in rows or []:
        row=dict(raw or {}); article_no=str(row.get("article_no","") or "")
        if row.get("missing_article"):
            findings.append(_finding("Fejl","missing_article",article_no,"Artikel",
                "Artikelnummeret findes ikke i artikeldatabasen.",
                "Opret eller importér artiklen, så beskrivelse, enhed og pris kan kontrolleres."))
        price=row.get("unit_price")
        if price is None or str(price).strip()=="":
            findings.append(_finding("Advarsel","missing_price",article_no,"Pris",
                "Artiklen mangler en anvendelig pris.",
                "Tilføj en manuel pris eller opdatér priser fra en forhandler."))
        else:
            checked=_parse_date(row.get("price_checked"))
            if checked is None:
                findings.append(_finding("Info","price_date_missing",article_no,"Pris",
                    "Prisen har ingen kontroldato.",
                    "Angiv hvornår prisen sidst blev kontrolleret."))
            elif (today-checked).days > int(stale_days):
                findings.append(_finding("Advarsel","stale_price",article_no,"Pris",
                    f"Prisen er {(today-checked).days} dage gammel.",
                    "Kontrollér eller opdatér prisen før bestilling."))

        try:package_qty=float(row.get("sales_package_quantity",1) or 1)
        except (TypeError,ValueError):package_qty=0
        try:minimum=float(row.get("minimum_order_quantity",1) or 1)
        except (TypeError,ValueError):minimum=0
        consumption=str(row.get("consumption_unit",row.get("unit","stk")) or "stk").casefold()
        sales=str(row.get("sales_unit",row.get("unit","stk")) or "stk").casefold()
        if not math.isfinite(package_qty) or package_qty <= 0:
            findings.append(_finding("Fejl","package_quantity_invalid",article_no,"Pakning",
                "Antal pr. salgsenhed er ugyldigt.","Angiv et positivt antal pr. pakke/rulle."))
        elif package_qty > 1.0000001 and sales==consumption:
            findings.append(_finding("Advarsel","package_unit_ambiguous",article_no,"Pakning",
                f"Salgsenhed og forbrugsenhed er begge ‘{sales}’, selv om pakningen indeholder {package_qty:g}.",
                "Vælg fx ‘pakke’ eller ‘rulle’ som salgsenhed."))
        if not math.isfinite(minimum) or minimum <= 0:
            findings.append(_finding("Fejl","minimum_order_invalid",article_no,"Pakning",
                "Mindste bestillingsmængde er ugyldig.","Angiv mindst 1 salgsenhed."))
        elif abs(minimum-round(minimum)) > 1e-9:
            findings.append(_finding("Advarsel","minimum_order_fraction",article_no,"Pakning",
                "Mindste bestilling er ikke et helt antal salgsenheder.","Angiv et helt antal pakker, ruller eller styk."))

    for raw in missing or []:
        row=dict(raw or {}); label=str(row.get("part_label",row.get("symbol_name","Ukendt del")) or "Ukendt del")
        findings.append(_finding("Fejl","missing_binding","","Tilknytning",
            f"{label} mangler artikel eller stykliste.",
            "Tilknyt en artikel/stykliste i BOM eller på den relevante objektdel.",label=label))

    rank={"Fejl":0,"Advarsel":1,"Info":2}
    findings.sort(key=lambda x:(rank.get(x["severity"],9),x["area"].casefold(),x["label"].casefold(),x["code"]))
    by_article={}
    for finding in findings:
        no=finding["article_no"]
        if no:by_article.setdefault(no,[]).append(finding)
    summary={"errors":sum(x["severity"]=="Fejl" for x in findings),
             "warnings":sum(x["severity"]=="Advarsel" for x in findings),
             "info":sum(x["severity"]=="Info" for x in findings),
             "total":len(findings)}
    return {"summary":summary,"findings":findings,"by_article":by_article}
