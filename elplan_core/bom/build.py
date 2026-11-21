"""BOM-beregning, bidragssporing og projektkontrol."""

from __future__ import annotations

import math

from elplan_core.associations import (
    association_channel_records,
    association_role,
    light_output_associations,
    light_output_records,
)
from elplan_core.bom.articles import (
    article_packaging,
    article_purchase_requirement,
    bom_article_category,
    cable_article_key,
    cable_type_display,
    normalize_article_catalog,
    normalize_article_unit,
    normalize_cable_article_bindings,
)
from elplan_core.bom.assemblies import (
    bom_assembly_effective_items,
    bom_assembly_lookup,
    normalize_bom_assemblies,
    normalize_symbol_article_bindings,
    normalize_symbol_assembly_bindings,
)
from elplan_core.bom.procurement import (
    bom_purchase_segment_key,
    placement_procurement_context,
)
from elplan_core.bom.scope import (
    normalize_placement_bom_room_additions,
    placement_bom_room_uids,
    placement_matches_bom_room,
)
from elplan_core.cables.lengths import cable_estimated_length_metres, cable_length_by_spec_metres
from elplan_core.cables.sections import cable_effective_specs, normalize_cable_spec_section_overrides
from elplan_core.constants import CABLE_LAYER, CUSTOM_SWITCH_TYPES, SYMBOL_GROUPS
from elplan_core.pl_box.model import normalize_pl_box_splices, pl_splice_member_keys
from elplan_core.pl_box.wiring import cable_legs_at_symbol, pl_box_wiring_status
from elplan_core.rooms import (
    cable_length_by_spec_room_metres,
    cable_room_length_metres,
    cable_rooms,
    polyline_room_lengths,
    room_display_text,
    room_for_point,
)
from elplan_core.symbols.registry import (
    combo_modules,
    combo_socket_kind,
    is_combo_symbol,
    symbol_display_name,
)


def _bom_switch_label(code: str) -> str:
    reverse={v:k for k,v in CUSTOM_SWITCH_TYPES.items()}
    return reverse.get(code, symbol_display_name(code))


def _bom_socket_label(code: str) -> str:
    names={
        "socket":"Stikkontakt",
        "socket_earth":"Stikkontakt med jordtilslutning",
    }
    return names.get(code, symbol_display_name(code))


def bom_symbol_parts(symbol: str):
    """Returnér de fysiske BOM-dele for et symbol.

    Kombisymboler opdeles efter *fysiske moduler*, ikke efter logiske
    tændingskanaler.  En kroneafbryder er derfor ét artikelmodul selv om den har
    to lystilhørsforhold.  Dette matcher den grafiske modulopdeling i
    tilhørs-guiden.
    """
    symbol=str(symbol or "")
    if is_combo_symbol(symbol):
        parts=[]
        for module_no,base in enumerate(combo_modules(symbol),start=1):
            parts.append({
                "id":f"module:{module_no}",
                "label":f"Modul {module_no} · {_bom_switch_label(base)}",
                "kind":"switch",
                "base":base,
                "required":True,
            })
        socket_kind=combo_socket_kind(symbol)
        if socket_kind and socket_kind!="none":
            parts.append({
                "id":"socket",
                "label":_bom_socket_label(socket_kind),
                "kind":"socket",
                "base":socket_kind,
                "required":True,
            })
        # Fx ramme, dåse, adapter eller fælles afdækning.  Valgfri, så en
        # kombination ikke rapporteres som ufuldstændig blot fordi den ikke bruges.
        parts.append({
            "id":"common",
            "label":"Fælles / ramme / tilbehør",
            "kind":"common",
            "base":symbol,
            "required":False,
        })
        return parts

    # Dette ældre symbol er i praksis også en fysisk kombination, selv om det
    # ligger i stikkontaktgruppen og ikke i Kombi-paletten.
    if symbol=="socket_switch":
        return [
            {"id":"module:1","label":"Modul 1 · 1-polet afbryder","kind":"switch","base":"switch_1","required":True},
            {"id":"socket","label":"Stikkontakt","kind":"socket","base":"socket","required":True},
            {"id":"common","label":"Fælles / ramme / tilbehør","kind":"common","base":symbol,"required":False},
        ]

    switch_codes=set(SYMBOL_GROUPS.get("Afbrydere",{}).values())
    socket_codes=set(SYMBOL_GROUPS.get("Stikkontakter",{}).values())
    data_codes=set(SYMBOL_GROUPS.get("Data / netværk",{}).values())
    solar_codes=set(SYMBOL_GROUPS.get("Solceller / energi",{}).values())
    if symbol in switch_codes:
        return [{"id":"symbol","label":symbol_display_name(symbol),"kind":"switch","base":symbol,"required":True}]
    if symbol in socket_codes:
        return [{"id":"symbol","label":symbol_display_name(symbol),"kind":"socket","base":symbol,"required":True}]
    if symbol in data_codes:
        return [{"id":"symbol","label":symbol_display_name(symbol),"kind":"data","base":symbol,"required":True}]
    if symbol in solar_codes:
        kind={
            "solar_panel":"solar_panel",
            "solar_inverter":"solar_inverter",
            "solar_battery":"solar_battery",
        }.get(symbol,"solar")
        return [{"id":"symbol","label":symbol_display_name(symbol),"kind":kind,"base":symbol,"required":True}]
    if symbol in {"light_connection","wall_light_outlet"}:
        # Lampeudtag er valgfrit i BOM: brugeren kan eksplicit tilknytte fx
        # Nordtronic 98425033, men der gættes aldrig automatisk en artikel.
        label="Lampeudtag i vægdåse" if symbol=="wall_light_outlet" else "Lampeudtag / lysstyring"
        return [{"id":"outlet","label":label,"kind":"outlet","base":symbol,"required":False}]
    return []


def bom_supported_symbol(symbol: str) -> bool:
    return bool(bom_symbol_parts(symbol))


def bom_symbol_bindings(symbol: str, bindings):
    all_bindings=normalize_symbol_article_bindings(bindings)
    return all_bindings.get(str(symbol or ""),{})




def project_control_issues(placements, cables, rooms=None, project_raw=None, assemblies=None) -> list[dict]:
    """Returnér handlingsorienterede projektkontrolpunkter uden Qt-afhængighed."""
    placements=list(placements or []); cables=list(cables or []); room_list=list(rooms or []); raw=dict(project_raw or {})
    bindings=normalize_symbol_article_bindings(raw.get("placement_articles",{}))
    assembly_bindings=normalize_symbol_assembly_bindings(raw.get("placement_assemblies",{}))
    assembly_lookup={a["id"]:a for a in normalize_bom_assemblies(assemblies or [])}
    cable_bindings=normalize_cable_article_bindings(raw.get("cable_instance_articles",{}))
    issues=[]
    def caption(p):
        ident=" · ".join(x for x in (str(getattr(p,"group","") or "").strip(),str(getattr(p,"label","") or "").strip()) if x)
        return ident or symbol_display_name(str(getattr(p,"symbol","") or ""))
    def add(severity,category,title,detail,object_type="",uid=""):
        issues.append({"severity":severity,"category":category,"title":title,"detail":detail,"object_type":object_type,"uid":str(uid or "")})
    switch_channels_by_letter={}
    light_targets_by_letter={}
    for placement in placements:
        role=association_role(str(getattr(placement,"symbol","") or ""))
        if role=="switch":
            for rec in association_channel_records(placement):
                letter=str(rec.get("association","") or "")
                if letter:switch_channels_by_letter.setdefault(letter,[]).append(rec)
        elif role=="light":
            if str(getattr(placement,"symbol","") or "")=="spot" and str(getattr(placement,"parent_light_uid","") or ""):
                continue
            for letter in light_output_associations(placement):
                light_targets_by_letter.setdefault(letter,[]).append(placement)
    for placement in placements:
        uid=str(getattr(placement,"uid","") or ""); symbol=str(getattr(placement,"symbol","") or ""); name=caption(placement)
        role=association_role(symbol)
        if role=="light" and symbol!="emergency_light" and not (symbol=="spot" and str(getattr(placement,"parent_light_uid","") or "")):
            outputs=light_output_records(placement)
            for output_index,output in enumerate(outputs,1):
                letter=str(output.get("association","") or "")
                output_name=str(output.get("name","") or f"Tænding {output_index}")
                suffix=f" · {output_name}" if len(outputs)>1 else ""
                if not letter:
                    add("warning","Tilknytning",f"{name}{suffix} er ikke tilknyttet en afbryder","Vælg en afbryderkanal og tilknyt udgangen på planen.","placement",uid)
                elif letter not in switch_channels_by_letter:
                    add("error","Tilknytning",f"{name}{suffix} peger på et manglende tilhørsforhold",f"Bogstav {letter} bruges ikke længere af en afbryderkanal.","placement",uid)
        elif role=="switch":
            for rec in association_channel_records(placement):
                letter=str(rec.get("association","") or "")
                if letter and not light_targets_by_letter.get(letter):
                    add("warning","Tilknytning",f"{name}: {rec.get('channel_caption','Betjening')} har intet lampested",f"Tilhørsbogstav {letter} er ikke anvendt af et lampested.","placement",uid)
        ib=bindings.get(uid,{}) if uid else {}; ab=assembly_bindings.get(uid,{}) if uid else {}; missing=[]
        for part in bom_symbol_parts(symbol):
            if not part.get("required",True):continue
            pid=part["id"]; aid=ab.get(pid,""); assembly=assembly_lookup.get(aid) if aid else None
            rows=bom_assembly_effective_items(assembly) if assembly is not None else ib.get(pid,[])
            if not rows:missing.append(str(part.get("label") or pid))
        if missing:add("warning","BOM",f"{name} mangler artikel",", ".join(missing),"placement",uid)
        for splice in normalize_pl_box_splices(getattr(placement,"pl_box_splices",[]) or []):
            if not str(splice.get("article_no","") or "").strip():
                add("warning","BOM",f"{name} har Wago uden artikel","Vælg Wago-artikel i PL-dåsekonfiguratoren.","placement",uid); break
        if symbol=="light_connection":
            legs=cable_legs_at_symbol(cables,uid); status=pl_box_wiring_status(getattr(placement,"pl_box_wiring",[]),legs); live=int(status.get("live_unassigned",0) or 0)
            if live:add("warning","PL-dåse",f"{name}: {live} aktiv(e) leder(e) uden funktion","Åbn lederfordelingen og fordel eller saml de aktive ledere.","placement",uid)
        if room_list and room_for_point(room_list,float(getattr(placement,"x",0.0)),float(getattr(placement,"y",0.0))) is None:
            add("info","Rum",f"{name} ligger uden for et defineret rum","Kontrollér rumafgrænsningen eller behold objektet uden rum.","placement",uid)
    for cable in cables:
        uid=str(getattr(cable,"uid","") or ""); cid=str(getattr(cable,"cable_id","") or "Kabel")
        if not str(getattr(cable,"cable_spec","") or "").strip():add("error","Kabel",f"{cid} mangler kabeltype","Angiv fx 3G1,5 eller 5G1,5.","cable",uid)
        if not cable_bindings.get(uid,""):add("warning","BOM",f"{cid} mangler kabelartikel","Tilknyt en fysisk kabelartikel til kabelstrækket.","cable",uid)
        if not str(getattr(cable,"label","") or "").strip():add("info","Mærkning",f"{cid} mangler ekstra mærkning","Brug Mærk kabler eller angiv mærkningen manuelt.","cable",uid)
    order={"error":0,"warning":1,"info":2}
    issues.sort(key=lambda x:(order.get(x["severity"],9),x["category"].casefold(),x["title"].casefold()))
    return issues


def bom_source_breakdown(placements, article_catalog, bindings, rooms=None, cables=None, cable_bindings=None,
                         assemblies=None, assembly_bindings=None, room_filter_uid="", placement_room_additions=None,
                         metres_per_unit=None, reserve_percent=0.0):
    """Returnér sporbare BOM-bidrag uden at ændre BOM-totalen.

    Hver post beskriver *hvorfor* en artikel optræder i BOM'en: en genbrugelig
    stykliste, en direkte/manuelt valgt artikel, en Wago-samling eller et
    fysisk kabel. Funktionen bruges kun til navigation/UX; ``build_bom`` er
    fortsat den autoritative mængdeberegning.
    """
    lookup={r.get("article_no",""):r for r in normalize_article_catalog(article_catalog)}
    bindings=normalize_symbol_article_bindings(bindings)
    assembly_bindings=normalize_symbol_assembly_bindings(assembly_bindings or {})
    assembly_lookup={r["id"]:r for r in normalize_bom_assemblies(assemblies or [])}
    cable_bindings=normalize_cable_article_bindings(cable_bindings or {})
    room_list=list(rooms or [])
    additions=normalize_placement_bom_room_additions(placement_room_additions or {})
    selected=str(room_filter_uid or "").strip()
    room_by_uid={str(getattr(r,"uid","") or ""):r for r in room_list}
    out=[]

    def placement_rooms(placement):
        if selected:
            return ["Uden rum" if selected=="__outside__" else room_display_text(room_by_uid.get(selected))]
        uids=placement_bom_room_uids(placement,room_list,additions,include_physical=True)
        labels=[room_display_text(room_by_uid[uid]) for uid in uids if uid in room_by_uid]
        return [x for x in labels if x] or ["Uden rum"]

    for placement in placements or []:
        if not placement_matches_bom_room(placement,room_list,additions,selected):
            continue
        uid=str(getattr(placement,"uid","") or "").strip()
        symbol=str(getattr(placement,"symbol","") or "")
        symbol_name=symbol_display_name(symbol)
        identity=" · ".join(x for x in (str(getattr(placement,"group","") or "").strip(),str(getattr(placement,"label","") or "").strip()) if x)
        rooms_text=" | ".join(placement_rooms(placement))
        procurement=placement_procurement_context(placement)
        ib=bindings.get(uid,{}) if uid else {}
        ab=assembly_bindings.get(uid,{}) if uid else {}
        for part in bom_symbol_parts(symbol):
            pid=part["id"]; aid=ab.get(pid,""); assembly=assembly_lookup.get(aid) if aid else None
            rows=bom_assembly_effective_items(assembly) if assembly is not None else ib.get(pid,[])
            source_type="assembly" if assembly is not None else "manual"
            source_label=str(assembly.get("name","") or "") if assembly is not None else "Direkte artikeltilknytning"
            for bound in rows or []:
                ano=str(bound.get("article_no","") or "").strip()
                if not ano:continue
                try:qty=float(bound.get("qty",1.0) or 1.0)
                except (TypeError,ValueError):qty=1.0
                art=lookup.get(ano,{})
                out.append({
                    "article_no":ano,"description":str(art.get("description","") or ""),
                    "purchase_segment_key":bom_purchase_segment_key(ano,procurement),**procurement,
                    "source_type":source_type,"source_label":source_label,
                    "component_role":str(bound.get("role","") or ""),
                    "assembly_id":str(aid or ""),"assembly_name":str(assembly.get("name","") or "") if assembly else "",
                    "placement_uid":uid,"cable_uid":"","symbol":symbol,"symbol_name":symbol_name,
                    "object_label":identity or symbol_name,"group_circuit":str(getattr(placement,"group","") or "").strip(),"part_id":pid,"part_label":str(part.get("label",pid) or pid),
                    "qty":qty,"unit":str(art.get("unit","stk") or "stk"),"room_display":rooms_text,
                    "detail":f"{symbol_name} · {part.get('label',pid)}" + (f" · {identity}" if identity else ""),
                })
        for splice in normalize_pl_box_splices(getattr(placement,"pl_box_splices",[]) or []):
            ano=str(splice.get("article_no","") or "").strip()
            if not ano:continue
            art=lookup.get(ano,{})
            members=len(pl_splice_member_keys(splice))
            out.append({
                "article_no":ano,"description":str(art.get("description","") or ""),
                "purchase_segment_key":bom_purchase_segment_key(ano,procurement),**procurement,
                "source_type":"wago","source_label":"Wago-samling i PL-dåse","assembly_id":"","assembly_name":"",
                "placement_uid":uid,"cable_uid":"","symbol":symbol,"symbol_name":symbol_name,
                "object_label":identity or symbol_name,"group_circuit":str(getattr(placement,"group","") or "").strip(),"part_id":str(splice.get("id","") or "wago"),"part_label":"Wago-samling",
                "qty":1.0,"unit":str(art.get("unit","stk") or "stk"),"room_display":rooms_text,
                "detail":f"{members} ledere + bro" if members else "PL-dåse / Wago",
            })

    outside=selected=="__outside__"; selected_room_uid=None if outside else selected
    for cable in cables or []:
        uid=str(getattr(cable,"uid","") or "").strip(); ano=cable_bindings.get(uid,"") if uid else ""
        if not ano:continue
        # build_bom kan ikke bruge én artikel på et fysisk kabelobjekt med flere
        # kabelspecifikationer, så kildelaget følger samme regel.
        if normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")):
            continue
        length=None
        if metres_per_unit is not None and float(metres_per_unit or 0)>0:
            if selected:
                length=cable_room_length_metres(cable,room_list,selected_room_uid,metres_per_unit,reserve_percent)
                if length is not None and float(length)<=1e-9:continue
            else:
                length=cable_estimated_length_metres(cable,metres_per_unit,reserve_percent)
        elif selected:
            lengths=polyline_room_lengths(getattr(cable,"points",[]) or [],room_list)
            if float(lengths.get(None if outside else selected_room_uid,0.0) or 0.0)<=1e-9:continue
        if selected:
            room_text="Uden rum" if outside else room_display_text(room_by_uid.get(selected_room_uid))
        else:
            cr=cable_rooms(cable,room_list) if room_list else []
            room_text=" | ".join(room_display_text(r) for r in cr if room_display_text(r)) or "Uden rum"
        art=lookup.get(ano,{})
        cid=str(getattr(cable,"cable_id","") or "Kabel").strip() or "Kabel"
        spec=str(getattr(cable,"cable_spec","") or "").strip()
        detail=f"{cid}" + (f" · {spec}" if spec else "")
        if length is not None:detail+=f" · {float(length):.2f} m inkl. reserve"
        out.append({
            "article_no":ano,"description":str(art.get("description","") or ""),
            "purchase_segment_key":bom_purchase_segment_key(ano,placement_procurement_context(None)),**placement_procurement_context(None),
            "source_type":"cable","source_label":"Kabelstræk","assembly_id":"","assembly_name":"",
            "placement_uid":"","cable_uid":uid,"symbol":"__cable__","symbol_name":"Kabel",
            "object_label":cid,"group_circuit":str(getattr(cable,"circuit_id","") or "").strip(),"part_id":"cable","part_label":spec or "Kabel",
            "qty":float(length) if length is not None else 1.0,
            "unit":"m behov" if length is not None else str(art.get("unit","stk") or "stk"),
            "room_display":room_text,"detail":detail,
        })
    return out


def bom_article_source_uids(article_no, placements, bindings, rooms=None, cables=None, cable_bindings=None,
                            assemblies=None, assembly_bindings=None, room_filter_uid="", placement_room_additions=None):
    """Find de konkrete symbol-/kabelobjekter som bidrager til en BOM-artikel.

    Bruges af BOM ↔ plantegning-navigation. Resultatet er kun navigationsdata;
    BOM-mængder ændres ikke.
    """
    wanted=str(article_no or "").strip()
    if not wanted:return {"placement_uids":[],"cable_uids":[]}
    room_list=list(rooms or [])
    bindings=normalize_symbol_article_bindings(bindings)
    assembly_bindings=normalize_symbol_assembly_bindings(assembly_bindings or {})
    assembly_lookup={r["id"]:r for r in normalize_bom_assemblies(assemblies or [])}
    cable_bindings=normalize_cable_article_bindings(cable_bindings or {})
    additions=normalize_placement_bom_room_additions(placement_room_additions or {})
    puids=[]; cuids=[]
    for placement in placements or []:
        if not placement_matches_bom_room(placement,room_list,additions,room_filter_uid):continue
        uid=str(getattr(placement,"uid","") or "").strip()
        ib=bindings.get(uid,{}) if uid else {}; ab=assembly_bindings.get(uid,{}) if uid else {}
        found=False
        for part in bom_symbol_parts(str(getattr(placement,"symbol","") or "")):
            pid=part["id"]; aid=ab.get(pid,""); assembly=assembly_lookup.get(aid) if aid else None
            rows=bom_assembly_effective_items(assembly) if assembly is not None else ib.get(pid,[])
            if any(str(x.get("article_no","") or "").strip()==wanted for x in rows or []):found=True; break
        if not found:
            for splice in normalize_pl_box_splices(getattr(placement,"pl_box_splices",[]) or []):
                if str(splice.get("article_no","") or "").strip()==wanted:found=True; break
        if found and uid and uid not in puids:puids.append(uid)
    selected=str(room_filter_uid or "").strip(); outside=selected=="__outside__"; room_uid=None if outside else selected
    for cable in cables or []:
        uid=str(getattr(cable,"uid","") or "").strip()
        if not uid or cable_bindings.get(uid,"")!=wanted:continue
        if normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")):continue
        if selected:
            lengths=polyline_room_lengths(getattr(cable,"points",[]) or [],room_list)
            key=None if outside else room_uid
            if float(lengths.get(key,0.0) or 0.0)<=1e-9:continue
        cuids.append(uid)
    return {"placement_uids":puids,"cable_uids":cuids}

def bom_article_room_usage(placements, bindings, rooms=None, cables=None, cable_bindings=None,
                           assemblies=None, assembly_bindings=None, placement_room_additions=None) -> dict[str, list[str]]:
    """Returnér de rum der bidrager til hvert artikelnummer i BOM'en.

    Funktionen ændrer ikke BOM-mængderne. Den giver alene UI'et rumkontekst til
    sortering/visning. Symbolartikler og Wago-artikler får rummet for den fysiske
    symbolplacering; kabelartikler får alle rum som det fysiske kabel løber igennem.
    Bidrag uden for et defineret rum vises som ``Uden rum``.
    """
    room_list=list(rooms or [])
    bindings=normalize_symbol_article_bindings(bindings)
    assembly_bindings=normalize_symbol_assembly_bindings(assembly_bindings or {})
    assembly_lookup={r["id"]:r for r in normalize_bom_assemblies(assemblies or [])}
    cable_bindings=normalize_cable_article_bindings(cable_bindings or {})
    additions=normalize_placement_bom_room_additions(placement_room_additions or {})
    room_by_uid={str(getattr(r,"uid","") or ""):r for r in room_list}
    usage: dict[str, list[str]]={}

    def _add(article_no, room_rows):
        article_no=str(article_no or "").strip()
        if not article_no:return
        captions=[]
        for room in room_rows or []:
            caption=room_display_text(room)
            if caption and caption not in captions:captions.append(caption)
        if not captions:captions=["Uden rum"]
        dest=usage.setdefault(article_no,[])
        for caption in captions:
            if caption not in dest:dest.append(caption)

    for placement in placements or []:
        symbol=str(getattr(placement,"symbol","") or "")
        uid=str(getattr(placement,"uid","") or "").strip()
        room_uids=placement_bom_room_uids(placement,room_list,additions,include_physical=True)
        room_rows=[room_by_uid[ruid] for ruid in room_uids if ruid in room_by_uid]
        instance_bindings=bindings.get(uid,{}) if uid else {}
        instance_assemblies=assembly_bindings.get(uid,{}) if uid else {}
        for part in bom_symbol_parts(symbol):
            part_id=part["id"]
            aid=instance_assemblies.get(part_id,"")
            assembly=assembly_lookup.get(aid) if aid else None
            rows=bom_assembly_effective_items(assembly) if assembly is not None else instance_bindings.get(part_id,[])
            for bound in rows or []:_add(bound.get("article_no",""),room_rows)
        for splice in normalize_pl_box_splices(getattr(placement,"pl_box_splices",[]) or []):
            _add(splice.get("article_no",""),room_rows)

    for cable in cables or []:
        uid=str(getattr(cable,"uid","") or "").strip()
        article_no=cable_bindings.get(uid,"") if uid else ""
        if not article_no:continue
        _add(article_no,cable_rooms(cable,room_list) if room_list else [])
    return usage


def build_bom(placements, article_catalog, bindings, cables=None, cable_bindings=None,
              metres_per_unit=None, reserve_percent=0.0, assemblies=None, assembly_bindings=None,
              rooms=None, room_filter_uid: str = "", placement_room_additions=None):
    """Byg BOM ud fra eksplicitte instanstilknytninger.

    Når ``room_filter_uid`` er sat, medtages kun bidrag fra det valgte rum.
    Værdien ``__outside__`` betyder areal uden for alle definerede rum.
    Kabelmængder fordeles efter den faktiske del af kabelruten i rummet i
    stedet for at tælle hele kabelstrækket i hvert rum det krydser.
    """
    # ``bindings``/``assembly_bindings`` er instansbaserede; der foretages
    # ingen automatisk arv fra symbol- eller kabeltype. Uden tilknytning
    # rapporteres bidraget i ``unassigned``.
    catalog=normalize_article_catalog(article_catalog)
    lookup={r["article_no"]:r for r in catalog}
    bindings=normalize_symbol_article_bindings(bindings)
    assemblies=normalize_bom_assemblies(assemblies or [])
    assembly_lookup={r["id"]:r for r in assemblies}
    assembly_bindings=normalize_symbol_assembly_bindings(assembly_bindings or {})
    cable_bindings=normalize_cable_article_bindings(cable_bindings or {})
    room_list=list(rooms or [])
    placement_room_additions=normalize_placement_bom_room_additions(placement_room_additions or {})
    selected_room_uid=str(room_filter_uid or "").strip()
    room_filter_active=bool(selected_room_uid)
    outside_filter=selected_room_uid=="__outside__"
    wanted_room_uid=None if outside_filter else selected_room_uid

    def _placement_in_selected_room(placement):
        return placement_matches_bom_room(placement,room_list,placement_room_additions,selected_room_uid)

    totals={}
    missing={}

    # Symboler / fysiske kombimoduler. Kun den konkrete placerings UID bruges.
    # Manuelt oprettede Wago-samlinger i PL-dåser er også eksplicitte fysiske
    # BOM-dele. De tælles via den artikel, brugeren har valgt på samlingen.
    wago_missing=[]
    for placement in placements or []:
        if not _placement_in_selected_room(placement):
            continue
        symbol=str(getattr(placement,"symbol","") or "")
        placement_uid=str(getattr(placement,"uid","") or "").strip()
        procurement=placement_procurement_context(placement)
        parts=bom_symbol_parts(symbol)
        if parts:
            instance_bindings=bindings.get(placement_uid,{}) if placement_uid else {}
            instance_assemblies=assembly_bindings.get(placement_uid,{}) if placement_uid else {}
            for part in parts:
                part_id=part["id"]
                assembly_id=instance_assemblies.get(part_id,"")
                assembly=assembly_lookup.get(assembly_id) if assembly_id else None
                bound_rows=bom_assembly_effective_items(assembly) if assembly is not None else instance_bindings.get(part_id,[])
                if not bound_rows:
                    if part.get("required",True):
                        label=part["label"]
                        if assembly_id and assembly is None:
                            label += " · valgt stykliste findes ikke"
                        elif assembly is not None:
                            label += f" · stykliste ‘{assembly.get('name','')}’ er tom"
                        key=(symbol,part_id,label)
                        missing[key]=missing.get(key,0.0)+1.0
                    continue
                for bound in bound_rows:
                    article_no=bound["article_no"]
                    qty=float(bound.get("qty",1.0) or 1.0)
                    segment_key=bom_purchase_segment_key(article_no,procurement)
                    entry=totals.setdefault(segment_key,{"article_no":article_no,"qty":0.0,**procurement})
                    entry["qty"]+=qty

        for splice in normalize_pl_box_splices(getattr(placement,"pl_box_splices",[]) or []):
            article_no=str(splice.get("article_no","") or "").strip()
            members=len(pl_splice_member_keys(splice))
            if article_no:
                segment_key=bom_purchase_segment_key(article_no,procurement)
                entry=totals.setdefault(segment_key,{"article_no":article_no,"qty":0.0,**procurement})
                entry["qty"]+=1.0
            else:
                wago_missing.append({
                    "symbol":"__pl_wago__",
                    "symbol_name":"PL-dåse / Wago",
                    "part_id":str(splice.get("id","") or "wago"),
                    "part_label":f"Wago-samling · {members} ledere + bro",
                    "qty":1.0,"count":1,"unit":"stk",
                    "detail":"Ingen Wago-artikel valgt",
                })

    # Kabler. Hvert stræk skal eksplicit have valgt en artikel via kabel-UID.
    cable_required_by_article={}
    cable_procurement=placement_procurement_context(None)
    cable_missing={}
    cable_scale_ok=metres_per_unit is not None and float(metres_per_unit or 0) > 0
    for cable in cables or []:
        spec=str(getattr(cable,"cable_spec","") or "").strip()
        layer=str(getattr(cable,"layer",CABLE_LAYER) or CABLE_LAYER)
        cable_uid=str(getattr(cable,"uid","") or "").strip()
        article_no=cable_bindings.get(cable_uid,"") if cable_uid else ""
        mixed=bool(normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]),spec))
        room_units=None
        if room_filter_active:
            key=None if outside_filter else wanted_room_uid
            room_units=float(polyline_room_lengths(getattr(cable,"points",[]) or [],room_list).get(key,0.0))
            if room_units<=1e-9:
                continue
        if mixed:
            # Én eksisterende kabelartikel kan ikke sandfærdigt beskrive både
            # fx 3G1,5 og 5G1,5 på samme CablePlacement. Indtil artikelvalg også
            # bliver afsnitsvist, rapporteres de faktiske meter derfor som
            # manglende artikel pr. kabeltype i stedet for at give en forkert BOM.
            by_spec=(cable_length_by_spec_room_metres(cable,room_list,None if outside_filter else wanted_room_uid,metres_per_unit) if room_filter_active else cable_length_by_spec_metres(cable,metres_per_unit)) if cable_scale_ok else None
            specs=cable_effective_specs(cable) or ([spec] if spec else [""])
            for local_spec in specs:
                miss_key=(layer,local_spec)
                entry=cable_missing.setdefault(miss_key,{"qty":0.0,"known":True,"count":0,"mixed":False})
                entry["count"] += 1; entry["mixed"] = True
                if by_spec is None:
                    entry["known"]=False
                else:
                    base=float(by_spec.get(local_spec,0.0))
                    entry["qty"] += base*(1.0+max(0.0,float(reserve_percent))/100.0)
            continue
        length=(cable_room_length_metres(cable,room_list,None if outside_filter else wanted_room_uid,metres_per_unit,reserve_percent) if room_filter_active else cable_estimated_length_metres(cable,metres_per_unit,reserve_percent)) if cable_scale_ok else None
        if not article_no:
            miss_key=(layer,spec)
            entry=cable_missing.setdefault(miss_key,{"qty":0.0,"known":True,"count":0,"mixed":False})
            entry["count"] += 1
            if length is None:
                entry["known"]=False
            else:
                entry["qty"] += float(length)
            continue
        segment_key=bom_purchase_segment_key(article_no,cable_procurement)
        entry=cable_required_by_article.setdefault(segment_key,{"article_no":article_no,"metres":0.0,"known":True,"count":0,**cable_procurement})
        entry["count"] += 1
        if length is None:
            entry["known"]=False
        else:
            entry["metres"] += float(length)

    out=[]
    all_segment_keys=set(totals)|set(cable_required_by_article)
    for segment_key in sorted(all_segment_keys,key=str.lower):
        segment=totals.get(segment_key) or cable_required_by_article.get(segment_key) or {}
        article_no=str(segment.get("article_no","") or "")
        article=lookup.get(article_no,{})
        symbol_qty=float((totals.get(segment_key) or {}).get("qty",0.0))
        cable_info=cable_required_by_article.get(segment_key)
        procurement={key:segment.get(key,value) for key,value in placement_procurement_context(None).items()}
        qty=symbol_qty
        detail=""
        if cable_info is not None:
            needed=float(cable_info.get("metres",0.0))
            known=bool(cable_info.get("known",False))
            try:
                package=float(article.get("package_length_m",0.0) or 0.0)
            except (TypeError,ValueError):
                package=0.0
            if known:
                if package > 0:
                    cable_qty=float(math.ceil(max(0.0,needed)/package - 1e-12)) if needed > 0 else 0.0
                    detail=f"{needed:.2f} m behov → {int(cable_qty)} × {package:g} m"
                else:
                    cable_qty=needed
                    detail=f"{needed:.2f} m inkl. reserve"
                qty += cable_qty
            else:
                detail="Kabellængde kan ikke beregnes – skala/kalibrering mangler"
        try:
            unit_price=float(article.get("effective_price", article.get("unit_price"))) if str(article.get("effective_price", article.get("unit_price", ""))).strip() != "" else None
        except (TypeError,ValueError):
            unit_price=None
        if unit_price is not None and (not math.isfinite(unit_price) or unit_price < 0):
            unit_price=None
        price_currency=str(article.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK"
        article_unit=str(article.get("unit","stk") or "stk").strip() or "stk"
        price_unit=str(article.get("price_unit","") or article_unit).strip() or article_unit
        packaging=article_packaging(article)
        purchase_required=(float(cable_info.get("metres",0.0) or 0.0)
                           if cable_info is not None and cable_info.get("known") else qty)
        purchase=article_purchase_requirement(article,purchase_required)
        # En pris pr. forbrugsenhed bruger det faktiske behov. En pris pr.
        # salgsenhed bruger det afrundede antal pakker/ruller. Dermed kan fx en
        # pakkepris og en normaliseret stykpris sameksistere uden fejlsummering.
        price_basis_qty=qty
        normalized_price_unit=normalize_article_unit(price_unit)
        if normalized_price_unit==packaging["consumption_unit"]:
            price_basis_qty=purchase_required
        elif normalized_price_unit==packaging["sales_unit"]:
            price_basis_qty=purchase["purchase_quantity"]
        line_total=(price_basis_qty*unit_price if unit_price is not None else None)
        already_purchased=bool(procurement.get("already_purchased",False))
        if not detail and (packaging["sales_package_quantity"] > 1.0000001 or packaging["minimum_order_quantity"] > 1.0000001):
            detail=purchase["summary"]
        out.append({
            "article_no":article_no,
            "purchase_segment_key":segment_key,
            **procurement,
            "description":str(article.get("description","") or ""),
            "manufacturer":str(article.get("manufacturer","") or ""),
            "bom_category":bom_article_category(article),
            "ean":str(article.get("ean","") or ""),
            "el_no":str(article.get("el_no","") or ""),
            "product_page":str(article.get("product_page","") or article.get("source","") or ""),
            "supplier_page":str(article.get("supplier_page","") or ""),
            "unit":(packaging["sales_unit"] if cable_info is not None and float(article.get("package_length_m",0) or 0)>0 else packaging["consumption_unit"]),
            "qty":qty,
            "detail":detail,
            "estimated_price":article.get("estimated_price"),
            "manual_price":article.get("manual_price"),
            "effective_price":unit_price,
            "unit_price":unit_price,
            "price_currency":price_currency,
            "price_unit":price_unit,
            "price_kind":str(article.get("price_kind", "") or ""),
            "price_status":str(article.get("price_status", "") or ""),
            "price_source":str(article.get("price_source", "") or ""),
            "price_checked":str(article.get("price_checked", "") or ""),
            "line_total":line_total,
            "price_basis_qty":price_basis_qty,
            "consumption_unit":packaging["consumption_unit"],
            "sales_unit":packaging["sales_unit"],
            "sales_package_quantity":packaging["sales_package_quantity"],
            "minimum_order_quantity":packaging["minimum_order_quantity"],
            "package_label":packaging["package_label"],
            "purchase_quantity":purchase["purchase_quantity"],
            "quantity_to_buy":0.0 if already_purchased else qty,
            "purchase_quantity_to_buy":0.0 if already_purchased else purchase["purchase_quantity"],
            "line_total_to_buy":0.0 if already_purchased and line_total is not None else line_total,
            "purchased_consumption_quantity":purchase["purchased_consumption_quantity"],
            "surplus_quantity":purchase["surplus_quantity"],
            "purchase_summary":purchase["summary"],
            "required_length_m":float(cable_info.get("metres",0.0)) if cable_info and cable_info.get("known") else None,
            "missing_article":article_no not in lookup,
        })

    unassigned=[]
    for (symbol,part_id,label),qty in sorted(missing.items(),key=lambda kv:(symbol_display_name(kv[0][0]).lower(),kv[0][1])):
        unassigned.append({
            "symbol":symbol,
            "symbol_name":symbol_display_name(symbol),
            "part_id":part_id,
            "part_label":label,
            "qty":qty,
            "count":int(round(qty)),
            "unit":"stk",
            "detail":"Ingen artikel/stykliste tilknyttet",
        })
    for (layer,spec),info in sorted(cable_missing.items(),key=lambda kv:(cable_type_display(kv[0][0]).lower(),kv[0][1].lower())):
        qty=float(info["qty"]) if info["known"] else float(info["count"])
        unit="m" if info["known"] else "stræk"
        detail=(
            f"{info['count']} blandet kabelstræk · afsnitsvis artikeltilknytning kræves"
            if info.get("mixed") else f"{info['count']} kabelstræk uden artikel"
        )
        if info["known"]:
            detail += " · meterbehov inkl. reserve"
        else:
            detail += " · skala/kalibrering mangler"
        unassigned.append({
            "symbol":"__cable__",
            "symbol_name":cable_type_display(layer),
            "part_id":cable_article_key(layer,spec),
            "part_label":spec or "Uden kabelspecifikation",
            "qty":qty,
            "count":int(info["count"]),
            "unit":unit,
            "detail":detail,
        })
    unassigned.extend(wago_missing)
    return out,unassigned

def bom_binding_summary(symbol: str, article_catalog, bindings, assemblies=None, assembly_bindings=None, binding_key: str | None=None) -> str:
    parts=bom_symbol_parts(symbol)
    if not parts:
        return "Ikke medtaget i BOM"
    lookup={r["article_no"]:r for r in normalize_article_catalog(article_catalog)}
    key=str(binding_key or symbol or "")
    sb=normalize_symbol_article_bindings(bindings).get(key,{})
    assembly_lookup=bom_assembly_lookup(assemblies or [])
    sab=normalize_symbol_assembly_bindings(assembly_bindings or {}).get(key,{})
    assigned_required=0; required=0
    effective={}
    for p in parts:
        aid=sab.get(p["id"],"")
        assembly=assembly_lookup.get(aid) if aid else None
        effective[p["id"]]=bom_assembly_effective_items(assembly) if assembly is not None else sb.get(p["id"],[])
        if p.get("required",True):
            required += 1
            if effective[p["id"]]:
                assigned_required += 1
    article_count=sum(len(effective.get(p["id"],[])) for p in parts)
    if article_count==0:
        return f"Ingen artikler tilknyttet · {required} obligatoriske del(e)"
    names=[]
    for p in parts:
        for b in effective.get(p["id"],[]):
            art=lookup.get(b["article_no"],{})
            desc=str(art.get("description","") or "")
            names.append(b["article_no"] + (f" · {desc}" if desc else ""))
    suffix=f" · {assigned_required}/{required} obligatoriske dele har artikel" if required else ""
    assembly_count=sum(1 for p in parts if sab.get(p["id"],"") in assembly_lookup)
    assembly_suffix=f" · {assembly_count} del(e) via stykliste" if assembly_count else ""
    return f"{article_count} artikeltilknytning(er){suffix}{assembly_suffix}" + (f" · {names[0]}" if len(names)==1 else "")
