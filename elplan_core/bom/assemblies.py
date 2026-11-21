"""Genbrugelige styklister, artikelbindinger og styklisteforbrug."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict

from elplan_core.bom.articles import (
    article_packaging,
    article_price_basis_quantity,
    normalize_article_catalog,
)
from elplan_core.bom.scope import (
    normalize_placement_bom_room_additions,
    placement_bom_room_uids,
    placement_matches_bom_room,
)
from elplan_core.rooms import room_display_text


def normalize_bom_assemblies(records):
    """Normalisér genbrugelige styklister (artikelopskrifter).

    En stykliste har et stabilt id og kan derfor ændres uden at symbolernes
    tilknytning skal skrives om. Artiklerne normaliseres efter samme princip
    som manuelle symboltilknytninger.
    """
    out=[]; seen=set()
    for raw in records or []:
        if not isinstance(raw,dict):
            continue
        assembly_id=str(raw.get("id","") or "").strip() or uuid.uuid4().hex
        if assembly_id in seen:
            continue
        name=str(raw.get("name","") or "").strip()
        if not name:
            continue
        clean=[]
        for row in raw.get("items",[]) or []:
            if not isinstance(row,dict):
                continue
            article_no=str(row.get("article_no","") or "").strip()
            if not article_no:
                continue
            try:
                qty=float(row.get("qty",1.0) or 1.0)
            except (TypeError,ValueError):
                qty=1.0
            if not math.isfinite(qty) or qty<=0:
                continue
            optional=bool(row.get("optional",False))
            included=bool(row.get("included",True)) if optional else True
            role=str(row.get("role","") or "").strip()
            note=str(row.get("note","") or "").strip()
            # Samme artikel må optræde flere gange, hvis rollen eller den
            # valgfrie status er forskellig. Det er relevant for komplette
            # montager, hvor samme varenummer kan have flere fysiske roller.
            existing=next((x for x in clean if x["article_no"]==article_no and x.get("role","")==role and bool(x.get("optional",False))==optional and bool(x.get("included",True))==included),None)
            if existing is None:
                item={"article_no":article_no,"qty":qty}
                if role:item["role"]=role
                if optional:
                    item["optional"]=True; item["included"]=included
                if note:item["note"]=note
                clean.append(item)
            else:
                existing["qty"] += qty
                if note and not existing.get("note"):existing["note"]=note
        tags=[]
        raw_tags=raw.get("tags",[])
        if isinstance(raw_tags,str):raw_tags=raw_tags.replace(";",",").split(",")
        for tag in raw_tags or []:
            text=str(tag or "").strip()
            if text and text.casefold() not in {x.casefold() for x in tags}:tags.append(text)
        # Strukturerede navneparametre er metadata for styklistebiblioteket.
        # De påvirker aldrig BOM-beregningen eller det frie brugernavn.
        try:
            import assembly_naming as _assembly_naming
            naming=_assembly_naming.normalize_naming_fields(raw.get("naming",{}))
        except Exception:
            naming={}
        out.append({
            "id":assembly_id,
            "name":name,
            "description":str(raw.get("description","") or "").strip(),
            "category":str(raw.get("category","") or "").strip(),
            "variant":str(raw.get("variant","") or "").strip(),
            "tags":tags,
            "notes":str(raw.get("notes","") or "").strip(),
            "naming":naming,
            "items":clean,
        })
        seen.add(assembly_id)
    return out



def bom_assembly_effective_items(assembly):
    """Returnér kun de komponenter som aktuelt er aktive i montagen.

    Faste komponenter er altid aktive. Valgfrie komponenter kan gemmes i
    styklisteopskriften uden at påvirke BOM, indtil ``included`` slås til.
    """
    if not isinstance(assembly,dict):
        return []
    out=[]
    for row in assembly.get("items",[]) or []:
        if not isinstance(row,dict):
            continue
        if bool(row.get("optional",False)) and not bool(row.get("included",True)):
            continue
        out.append(row)
    return out


def bom_assembly_item_counts(assembly):
    rows=list((assembly or {}).get("items",[]) or []) if isinstance(assembly,dict) else []
    optional=sum(1 for row in rows if bool(row.get("optional",False)))
    included_optional=sum(1 for row in rows if bool(row.get("optional",False)) and bool(row.get("included",True)))
    return {
        "total":len(rows),
        "required":len(rows)-optional,
        "optional":optional,
        "included_optional":included_optional,
        "active":len(bom_assembly_effective_items(assembly)),
    }

def normalize_symbol_assembly_bindings(data):
    """Normalisér symbol -> fysisk del -> stykliste-id.

    Hvis en del har en stykliste, er den aktiv i stedet for den manuelle
    artikeltilknytning. De manuelle rækker bevares dog, så brugeren kan skifte
    tilbage uden at miste en specialkonfiguration.
    """
    if not isinstance(data,dict):
        return {}
    out={}
    for symbol,parts in data.items():
        symbol=str(symbol or "").strip()
        if not symbol or not isinstance(parts,dict):
            continue
        clean={}
        for part_id,assembly_id in parts.items():
            part_id=str(part_id or "").strip(); assembly_id=str(assembly_id or "").strip()
            if part_id and assembly_id:
                clean[part_id]=assembly_id
        if clean:
            out[symbol]=clean
    return out


def bom_assembly_lookup(records):
    return {r["id"]:r for r in normalize_bom_assemblies(records)}


def normalize_symbol_article_bindings(data):
    """Normalisér symbol -> fysisk del -> artikeltilknytninger."""
    if not isinstance(data,dict):
        return {}
    out={}
    for symbol,parts in data.items():
        symbol=str(symbol or "")
        if not symbol or not isinstance(parts,dict):
            continue
        clean_parts={}
        for part_id,rows in parts.items():
            part_id=str(part_id or "")
            if not part_id:
                continue
            clean=[]
            for raw in rows or []:
                if not isinstance(raw,dict):
                    continue
                article_no=str(raw.get("article_no", "") or "").strip()
                if not article_no:
                    continue
                try:
                    qty=float(raw.get("qty",1.0) or 1.0)
                except (TypeError,ValueError):
                    qty=1.0
                if not math.isfinite(qty) or qty <= 0:
                    continue
                # Et artikelnummer må kun forekomme én gang på den samme del.
                existing=next((r for r in clean if r["article_no"]==article_no),None)
                if existing is None:
                    clean.append({"article_no":article_no,"qty":qty})
                else:
                    existing["qty"] += qty
            if clean:
                clean_parts[part_id]=clean
        if clean_parts:
            out[symbol]=clean_parts
    return out


def bom_assembly_usage(placements, article_catalog, bindings, rooms=None, assemblies=None, assembly_bindings=None,
                       room_filter_uid="", placement_room_additions=None):
    """Aggregér de genbrugelige styklister som faktisk er anvendt i BOM-scope."""
    lookup={r.get("article_no",""):r for r in normalize_article_catalog(article_catalog)}
    assembly_rows=normalize_bom_assemblies(assemblies or [])
    assembly_lookup={r["id"]:r for r in assembly_rows}
    assembly_bindings=normalize_symbol_assembly_bindings(assembly_bindings or {})
    room_list=list(rooms or [])
    additions=normalize_placement_bom_room_additions(placement_room_additions or {})
    room_by_uid={str(getattr(r,"uid","") or ""):r for r in room_list}
    selected=str(room_filter_uid or "").strip()
    usage={}
    for placement in placements or []:
        if not placement_matches_bom_room(placement,room_list,additions,selected):continue
        uid=str(getattr(placement,"uid","") or "").strip(); parts=assembly_bindings.get(uid,{}) if uid else {}
        if selected:
            room_labels=["Uden rum" if selected=="__outside__" else room_display_text(room_by_uid.get(selected))]
        else:
            ruids=placement_bom_room_uids(placement,room_list,additions,include_physical=True)
            room_labels=[room_display_text(room_by_uid[x]) for x in ruids if x in room_by_uid] or ["Uden rum"]
        for part_id,aid in parts.items():
            assembly=assembly_lookup.get(aid)
            if assembly is None:continue
            rec=usage.setdefault(aid,{"assembly_id":aid,"name":assembly.get("name",""),"description":assembly.get("description",""),"category":assembly.get("category",""),"variant":assembly.get("variant",""),"tags":list(assembly.get("tags",[]) or []),"uses":0,"rooms":[],"placement_uids":[],"items":[dict(x) for x in bom_assembly_effective_items(assembly)],"all_items":[dict(x) for x in (assembly.get("items",[]) or [])]})
            rec["uses"]+=1
            if uid and uid not in rec["placement_uids"]:rec["placement_uids"].append(uid)
            for room in room_labels:
                if room and room not in rec["rooms"]:rec["rooms"].append(room)
    out=[]
    for aid,rec in usage.items():
        currencies=defaultdict(float); priced_items=0
        child=[]
        for item in rec.get("items",[]) or []:
            ano=str(item.get("article_no","") or "").strip(); art=lookup.get(ano,{})
            qty=float(item.get("qty",1.0) or 1.0); total_qty=qty*int(rec.get("uses",0) or 0)
            try:price=float(art.get("effective_price",art.get("unit_price"))) if str(art.get("effective_price",art.get("unit_price",""))).strip()!="" else None
            except (TypeError,ValueError):price=None
            cur=str(art.get("price_currency","DKK") or "DKK").upper(); line=None
            if price is not None and math.isfinite(price) and price>=0:
                line=price*article_price_basis_quantity(art,total_qty); currencies[cur]+=line; priced_items+=1
            pack=article_packaging(art)
            child.append({"article_no":ano,"description":str(art.get("description","") or ""),"qty_per_use":qty,"qty":total_qty,"unit":pack["consumption_unit"],"unit_price":price,"price_currency":cur,"line_total":line})
        row=dict(rec); row["items"]=child; row["totals_by_currency"]=dict(currencies); row["priced_items"]=priced_items; out.append(row)
    return sorted(out,key=lambda r:str(r.get("name","") or "").casefold())
