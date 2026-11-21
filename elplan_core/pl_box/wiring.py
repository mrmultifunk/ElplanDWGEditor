"""PL-dåsens kabelben, lederprofiler og elektriske lederfordeling."""

from __future__ import annotations

import re

from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import (
    _association_text_to_index,
    association_channel_records,
    association_role,
    light_output_associations,
    light_output_records,
    normalize_associations,
)
from elplan_core.cables.categories import normalize_cable_category_id, normalize_cable_line_style
from elplan_core.cables.connections import cable_symbol_connections
from elplan_core.cables.sections import (
    cable_effective_specs,
    cable_spec_for_leg,
    normalize_cable_spec_section_overrides,
)
from elplan_core.constants import (
    DEFAULT_CABLE_CATEGORY,
    DEFAULT_CABLE_COLOR,
    DEFAULT_CABLE_LINE_STYLE,
)
from elplan_core.models import CablePlacement, Placement
from elplan_core.pl_box.model import (
    PL_BOX_LEG_CAPTIONS,
    normalize_pl_box_splices,
    normalize_pl_outlet_type,
    pl_box_conductor_key,
    pl_box_conductor_ref,
    pl_splice_member_keys,
)

PL_CONDUCTOR_VISUALS = {
    "pe": {"label": "PE", "color_name": "Gul/grøn", "color": "#16a34a", "text_color": "#ffffff", "protective": True},
    "blue": {"label": "Blå", "color_name": "Blå", "color": "#2563eb", "text_color": "#ffffff", "neutral": True},
    "brown": {"label": "Brun", "color_name": "Brun", "color": "#a87943", "text_color": "#ffffff"},
    "black": {"label": "Sort", "color_name": "Sort", "color": "#111827", "text_color": "#ffffff"},
    "grey": {"label": "Grå", "color_name": "Grå", "color": "#9ca3af", "text_color": "#111827"},
    "red": {"label": "Rød", "color_name": "Rød", "color": "#dc2626", "text_color": "#ffffff"},
    "white": {"label": "Hvid", "color_name": "Hvid", "color": "#ffffff", "text_color": "#111827"},
}


SWITCH_CONDUCTOR_TYPICAL_SUPPLY_IDS = {"pe", "blue", "brown"}


SWITCH_CONDUCTOR_PREFERRED_ORDER = ("black", "grey", "red", "white")

def cable_neighbor_connection(cable: CablePlacement, point_index: int, leg: str):
    """Find nærmeste fysiske symbolforbindelse på den valgte side af et kabelpunkt."""
    idx=int(point_index)
    rows=cable_symbol_connections(cable)
    side=str(leg or "").strip().lower()
    if side=="before" or (side=="endpoint" and idx>0):
        candidates=[r for r in rows if int(r.get("point_index",-1))<idx]
        return dict(max(candidates,key=lambda r:int(r.get("point_index",-1)))) if candidates else None
    if side=="after" or side=="endpoint":
        candidates=[r for r in rows if int(r.get("point_index",10**9))>idx]
        return dict(min(candidates,key=lambda r:int(r.get("point_index",10**9)))) if candidates else None
    return None


def cable_pl_display(cable) -> str:
    """PL-/montagevisning med fysisk kabel-ID, gruppe/kreds og ekstra mærkning."""
    cid=str(getattr(cable,"cable_id","") or "").strip()
    circuit=str(getattr(cable,"circuit_id","") or "").strip()
    extra=str(getattr(cable,"label","") or "").strip()
    parts=[]
    if cid:parts.append(cid)
    if circuit and circuit not in parts:parts.append(circuit)
    if extra and extra not in parts:parts.append(extra)
    return " · ".join(parts) or "Kabel"


def cable_legs_at_symbol(cables, symbol_uid: str) -> list[dict]:
    """Returnér de fysiske kabelben der bruger en indføring ved ét symbol.

    Et kabel der ender ved symbolet bruger ét ben. Et kabel der passerer gennem
    symbolet har ét polylinepunkt ved symbolet, men bruger to fysiske
    indføringer: Side A og Side B.
    """
    uid = str(symbol_uid or "").strip()
    out: list[dict] = []
    if not uid:
        return out
    for cable in cables or []:
        points = list(getattr(cable, "points", []) or [])
        if not points:
            continue
        cable_uid = str(getattr(cable, "uid", "") or "").strip()
        for connection in cable_symbol_connections(cable):
            if str(connection.get("symbol_uid", "") or "") != uid:
                continue
            idx = int(connection.get("point_index", 0) or 0)
            if not (0 <= idx < len(points)):
                continue
            legs: list[tuple[str, tuple[float, float]]] = []
            px, py = map(float, points[idx])
            if idx > 0:
                qx, qy = map(float, points[idx - 1])
                legs.append(("before" if idx < len(points)-1 else "endpoint", (qx-px, qy-py)))
            if idx < len(points) - 1:
                qx, qy = map(float, points[idx + 1])
                legs.append(("after" if idx > 0 else "endpoint", (qx-px, qy-py)))
            for leg, vector in legs:
                effective_spec=cable_spec_for_leg(cable,idx,leg)
                out.append({
                    "cable_uid": cable_uid,
                    "point_index": idx,
                    "leg": leg,
                    "leg_caption": PL_BOX_LEG_CAPTIONS[leg],
                    "cable_id": str(getattr(cable, "cable_id", "") or "").strip(),
                    "circuit_id": str(getattr(cable, "circuit_id", "") or "").strip(),
                    "route_chain_uid": str(getattr(cable, "route_chain_uid", "") or "").strip(),
                    "cable_extra_label": str(getattr(cable, "label", "") or "").strip(),
                    "cable_display": cable_pl_display(cable),
                    "cable_spec": effective_spec,
                    "cable_default_spec": str(getattr(cable, "cable_spec", "") or "").strip(),
                    "cable_mixed_spec": bool(normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]))),
                    # Kabelkategorien følger kabelbenet ind i PL-konfiguratoren,
                    # så montøren kan se den samme anvendelseskategori som på tegningen.
                    "cable_category": normalize_cable_category_id(getattr(cable, "cable_category", DEFAULT_CABLE_CATEGORY)),
                    "line_style": normalize_cable_line_style(getattr(cable, "line_style", DEFAULT_CABLE_LINE_STYLE)),
                    "layer": str(getattr(cable, "layer", "") or "").strip(),
                    "color": normalize_hex_color(getattr(cable, "color", DEFAULT_CABLE_COLOR)),
                    "vector": (float(vector[0]), float(vector[1])),
                    "neighbor_symbol_uid": str((cable_neighbor_connection(cable,idx,leg) or {}).get("symbol_uid","") or ""),
                })
    return out


def pl_expected_switch_connections(light: Placement, placements, cables) -> list[dict]:
    """Udled konkrete afbryderkanaler for et lampested fra eksisterende tilhørsforhold.

    En relation bliver *direkte* når et kabelben i PL-dåsen har den konkrete
    afbryder som nærmeste næste fysiske symbol på samme kabel. Kun direkte,
    ikke-korrespondance kanaler bruges som hårde lederkrav. Øvrige relationer
    vises som information, så programmet ikke gætter på korrespondancetopologi.
    """
    output_by_letter={
        str(row.get("association","") or ""):dict(row)
        for row in light_output_records(light) if str(row.get("association","") or "")
    }
    light_assoc=set(output_by_letter)
    if not light_assoc:return []
    legs=cable_legs_at_symbol(cables,str(getattr(light,"uid","") or ""))
    direct_by_switch={}
    for leg in legs:
        nuid=str(leg.get("neighbor_symbol_uid","") or "")
        if nuid:direct_by_switch.setdefault(nuid,[]).append(dict(leg))
    out=[]
    for switch in placements or []:
        if association_role(getattr(switch,"symbol",""))!="switch":continue
        for channel in association_channel_records(switch):
            letter=str(channel.get("association","") or "")
            if not letter or letter not in light_assoc:continue
            direct_legs=direct_by_switch.get(str(getattr(switch,"uid","") or ""),[])
            if direct_legs:
                for leg in direct_legs:
                    row=dict(channel)
                    row.update({
                        "function_id":f"switch:{letter}",
                        "light_output_id":str(output_by_letter[letter].get("id","") or ""),
                        "light_output_name":str(output_by_letter[letter].get("name","") or ""),
                        "direct":True,
                        "required":not bool(channel.get("manual_topology")),
                        "cable_uid":str(leg.get("cable_uid","") or ""),
                        "point_index":int(leg.get("point_index",0) or 0),
                        "leg":str(leg.get("leg","") or ""),
                        "leg_caption":str(leg.get("leg_caption","") or ""),
                        "cable_display":str(leg.get("cable_display") or leg.get("cable_id") or "Kabel"),
                    })
                    out.append(row)
            else:
                row=dict(channel)
                row.update({
                    "function_id":f"switch:{letter}","direct":False,"required":False,
                    "light_output_id":str(output_by_letter[letter].get("id","") or ""),
                    "light_output_name":str(output_by_letter[letter].get("name","") or ""),
                    "cable_uid":"","point_index":0,"leg":"","leg_caption":"","cable_display":"",
                })
                out.append(row)
    out.sort(key=lambda r:(_association_text_to_index(r.get("association","")),0 if r.get("direct") else 1,str(r.get("source_mark","")),int(r.get("channel_index",0))))
    return out


def pl_switch_requirement_status(requirements, wiring, splices=None) -> list[dict]:
    """Status pr. afbryderkanal samt dubletkontrol på dens forventede kabelben.

    Ledere der kun ligger i en Wago-sløjfe uden bro til lampestedet tæller ikke
    som en tændingsleder frem til lampestedets terminal.
    """
    rows=normalize_pl_box_wiring(wiring)
    loop_only=set()
    for splice in normalize_pl_box_splices(splices or []):
        if not bool(splice.get("connects_to_outlet",True)):
            loop_only.update(pl_splice_member_keys(splice))
    out=[]
    for raw in requirements or []:
        req=dict(raw); fid=str(req.get("function_id","") or "")
        all_matches=[x for x in rows if str(x.get("function","") or "")==fid and pl_box_conductor_key(x) not in loop_only]
        if req.get("direct"):
            local=[x for x in all_matches if str(x.get("cable_uid","") or "")==str(req.get("cable_uid","") or "") and int(x.get("point_index",0) or 0)==int(req.get("point_index",0) or 0) and str(x.get("leg","") or "")==str(req.get("leg","") or "")]
        else:
            local=[]
        if req.get("manual_topology"):
            state="manual"; detail="Korrespondance/krydsning: terminalforløb skal verificeres manuelt"
        elif req.get("required") and len(local)==1:
            state="ok"; detail="Én leder er tildelt på det forventede kabelben"
        elif req.get("required") and len(local)>1:
            state="duplicate"; detail=f"{len(local)} ledere er tildelt samme tænding på kabelbenet"
        elif req.get("required") and all_matches:
            state="wrong_cable"; detail="Tændingen er tildelt, men ikke på kabelbenet fra denne afbryder"
        elif req.get("required"):
            state="missing"; detail="Ingen leder er tildelt endnu"
        else:
            state="related"; detail="Tilhørsforhold fundet, men ingen direkte kabelvej til PL-dåsen"
        req.update({"state":state,"detail":detail,"assigned_count":len(local),"global_assigned_count":len(all_matches)})
        out.append(req)
    return out


def assign_pl_conductor_function(records, cable_legs, conductor_key, function_id: str) -> list[dict]:
    """Tildel præcis én funktion til én fysisk lederende.

    Datamodellen har ét ``function``-felt pr. unik leder-nøgle. En ny tænding
    erstatter derfor den gamle funktion på samme leder i stedet for at kunne
    lægges oveni den. Det er den centrale beskyttelse mod dobbelt anvendelse.
    """
    key=tuple(conductor_key or ())
    wiring=reconcile_pl_box_wiring(records,cable_legs)
    for row in wiring:
        if pl_box_conductor_key(row)==key:
            row["function"]=str(function_id or "").strip()
            break
    return wiring


def pl_wiring_requirement_summary(requirements, wiring, splices=None) -> dict:
    statuses=pl_switch_requirement_status(requirements,wiring,splices)
    return {
        "statuses":statuses,
        "required":sum(1 for x in statuses if x.get("required")),
        "ok":sum(1 for x in statuses if x.get("state")=="ok"),
        "missing":sum(1 for x in statuses if x.get("state")=="missing"),
        "wrong_cable":sum(1 for x in statuses if x.get("state")=="wrong_cable"),
        "duplicate":sum(1 for x in statuses if x.get("state")=="duplicate"),
        "manual":sum(1 for x in statuses if x.get("state")=="manual"),
    }


def cable_conductor_preset(cable_spec: str) -> list[dict]:
    """Returnér generelle lederfarver for almindelige G- og 4X-kabler.

    G angiver en gul/grøn beskyttelsesleder. 1G bruges derfor til en enkelt
    beskyttelses-/udligningsleder. X angiver, at kablet ikke indeholder en
    gul/grøn leder; 4X vises som tre faser og nul, men aldrig som PE.
    7G-profilen i Elplan er: gul/grøn, blå, brun, sort, grå, rød og hvid.
    Ukendte kabelopbygninger returnerer en tom liste og kan derfor ikke blive
    fejlagtigt planlagt ud fra et gæt. Den konkrete kabelartikel/datablad har
    altid forrang for denne generelle planlægningsprofil.
    """
    text=str(cable_spec or "").upper().replace(" ", "")
    m=re.search(r"(1|3|4|5|7)(G|X)(?=\d|[,\.]|MM|$)", text)
    if not m:
        # Accepter også fx "N1XZ1 5G4" hvor markøren indgår i anden normal tekst.
        m=re.search(r"(1|3|4|5|7)(G|X)", text)
    if not m:
        return []
    count=int(m.group(1))
    marker=m.group(2)
    if marker == "X":
        # Kun den kendte 4X-profil kan beskrives sikkert uden kabeldatablad.
        if count != 4:
            return []
        ids=["brown","black","grey","blue"]
    elif count==1:
        ids=["pe"]
    elif count==3:
        ids=["pe","blue","brown"]
    elif count==5:
        ids=["pe","blue","brown","black","grey"]
    else:
        ids=["pe","blue","brown","black","grey","red","white"]
    out=[]
    for core_id in ids:
        row=dict(PL_CONDUCTOR_VISUALS[core_id])
        row.update({"core_id":core_id,"display":row.get("label",core_id),"number":None})
        out.append(row)
    return out


def placement_identification_caption(placement, *, separator: str = " · ") -> str:
    """Vis gruppe/kreds og mærkning sammen uden dubletter.

    PL-dialoger, tændleder-overblik og rapporter skal bruge den samme
    identifikation, så en gruppe som G11 ikke skjuler brugerens mærkning.
    """
    group = str(getattr(placement, "group", "") or "").strip()
    label = str(getattr(placement, "label", "") or "").strip()
    parts = []
    for value in (group, label):
        if value and value not in parts:
            parts.append(value)
    return separator.join(parts) if parts else "Lampested"


def cable_switch_conductor_usage(cable_uid: str, placements, cables, *, current_placement_uid: str = "", current_wiring=None) -> dict:
    """Saml anvendelsen af lederfarver langs ét fysisk kabel.

    Funktionen bruges som planlægningshjælp i PL-konfiguratoren. Den ser på de
    gemte lederplaner ved alle lampesteder, som det samme ``CablePlacement``
    passerer, og viser især hvilke farver der allerede er anvendt som
    tændledninger. Gul/grøn, blå og brun markeres som henholdsvis PE, typisk N
    og typisk fast L og foreslås derfor ikke som nye tændledere. Det er en
    brugerhjælp - den erstatter ikke kontrol af kabelartikel/datablad eller
    gældende installationsregler.
    """
    uid=str(cable_uid or "").strip()
    cable=next((c for c in (cables or []) if str(getattr(c,"uid","") or "")==uid),None)
    if cable is None:
        return {"cable_uid":uid,"cable_id":"","cable_spec":"","cores":[],"recommended_core_id":"","conflicts":[]}
    specs=cable_effective_specs(cable)
    cable_spec=" / ".join(specs) if specs else str(getattr(cable,"cable_spec","") or "").strip()
    # Et kabel kan fra 0.54.2 skifte fx 3G→5G mellem to lampesteder. Til
    # tændleder-overblikket samles derfor lederprofilen som unionen af de
    # faktiske kabeltyper langs samme kabel, mens den konkrete PL-dåse stadig
    # kun viser de ledere, der findes på dens enkelte kabelben.
    core_profile=[]; seen_core_ids=set()
    for spec in specs or [cable_spec]:
        for meta in cable_conductor_preset(spec):
            cid=str(meta.get("core_id") or "")
            if not cid or cid in seen_core_ids:
                continue
            seen_core_ids.add(cid); core_profile.append(dict(meta))
    if not core_profile:
        return {
            "cable_uid":uid,"cable_id":str(getattr(cable,"cable_id","") or "").strip(),
            "cable_spec":cable_spec,"cores":[],"recommended_core_id":"","conflicts":[],
        }

    functions_by_core={str(c.get("core_id") or ""):set() for c in core_profile}
    usages_by_core={str(c.get("core_id") or ""):[] for c in core_profile}
    seen_usage=set()
    current_uid=str(current_placement_uid or "").strip()
    for placement in placements or []:
        puid=str(getattr(placement,"uid","") or "").strip()
        legs=cable_legs_at_symbol(cables,puid)
        if not any(str(leg.get("cable_uid","") or "")==uid for leg in legs):
            continue
        raw=current_wiring if current_uid and puid==current_uid and current_wiring is not None else getattr(placement,"pl_box_wiring",[])
        wiring=reconcile_pl_box_wiring(raw,legs)
        ident=placement_identification_caption(placement)
        for row in wiring:
            if str(row.get("cable_uid","") or "")!=uid:
                continue
            core_id=str(row.get("core_id","") or "").strip().lower()
            fid=str(row.get("function","") or "").strip()
            if not core_id or not fid or core_id not in functions_by_core:
                continue
            functions_by_core[core_id].add(fid)
            usage_key=(core_id,fid,puid)
            if usage_key in seen_usage:
                continue
            seen_usage.add(usage_key)
            usages_by_core[core_id].append({
                "function":fid,"placement_uid":puid,"placement":ident,
                "function_caption":pl_wiring_function_caption(fid,light_output_associations(placement)),
            })

    supply_captions={"pe":"PE / beskyttelsesleder","blue":"Typisk N","brown":"Typisk fast L"}
    cores=[]; conflicts=[]
    for meta in core_profile:
        core_id=str(meta.get("core_id") or "")
        functions=sorted(functions_by_core.get(core_id,set()))
        switch_functions=sorted(fid for fid in functions if fid.startswith("switch:"))
        traveller_functions=sorted(fid for fid in functions if fid.startswith("traveller:"))
        control_functions=sorted(set(switch_functions+traveller_functions))
        other_functions=sorted(fid for fid in functions if not fid.startswith(("switch:","traveller:")))
        typical_supply=core_id in SWITCH_CONDUCTOR_TYPICAL_SUPPLY_IDS
        if len(control_functions)>1:
            status="conflict"
        elif control_functions:
            status="used_switch"
        elif other_functions:
            status="assigned_other"
        elif typical_supply:
            status="typical_supply"
        else:
            status="available"
        row=dict(meta)
        row.update({
            "functions":functions,"switch_functions":switch_functions,"traveller_functions":traveller_functions,
            "control_functions":control_functions,"other_functions":other_functions,
            "usages":list(usages_by_core.get(core_id,[])),"typical_supply":typical_supply,
            "supply_caption":supply_captions.get(core_id,""),"status":status,
        })
        cores.append(row)
        if status=="conflict":
            conflicts.append({"core_id":core_id,"color_name":str(meta.get("color_name") or meta.get("label") or core_id),"switch_functions":switch_functions,"control_functions":control_functions})

    by_id={str(c.get("core_id") or ""):c for c in cores}
    recommended=""
    for core_id in SWITCH_CONDUCTOR_PREFERRED_ORDER:
        row=by_id.get(core_id)
        if row and row.get("status")=="available":
            recommended=core_id; break
    return {
        "cable_uid":uid,"cable_id":str(getattr(cable,"cable_id","") or "").strip(),
        "cable_spec":cable_spec,"cores":cores,"recommended_core_id":recommended,"conflicts":conflicts,
    }


def cable_conductor_external_allocations(cable_uid: str, core_id: str, placements, cables, *, current_placement_uid: str = "", current_wiring=None) -> dict:
    """Returnér funktioner for samme leder ved andre ender af et fysisk kabel.

    En tom lokal leder kan dermed vises som allerede anvendt andetsteds uden at
    blive betragtet som fysisk forbundet i den aktuelle PL-dåse.
    """
    usage=cable_switch_conductor_usage(
        cable_uid,placements,cables,
        current_placement_uid=current_placement_uid,current_wiring=current_wiring,
    )
    cid=str(core_id or "").strip().lower(); current=str(current_placement_uid or "").strip()
    row=next((x for x in usage.get("cores",[]) if str(x.get("core_id") or "").strip().lower()==cid),{})
    external=[dict(x) for x in row.get("usages",[]) if str(x.get("placement_uid") or "")!=current]
    functions=[]
    for item in external:
        fid=str(item.get("function") or "")
        if fid and fid not in functions:functions.append(fid)
    return {
        "cable_uid":str(cable_uid or ""),"core_id":cid,"functions":functions,
        "usages":external,"conflict":len(functions)>1,
    }


def cable_switch_conductor_assignment_advice(cable_uid: str, core_id: str, target_function: str, placements, cables, *, current_placement_uid: str = "", current_wiring=None) -> dict:
    """Vurdér en ny tændleder-tildeling mod brugen langs hele samme kabel."""
    fid=str(target_function or "").strip(); cid=str(core_id or "").strip().lower()
    usage=cable_switch_conductor_usage(
        cable_uid,placements,cables,current_placement_uid=current_placement_uid,current_wiring=current_wiring,
    )
    row=next((x for x in usage.get("cores",[]) if str(x.get("core_id") or "")==cid),{})
    control_functions=list(row.get("control_functions",row.get("switch_functions",[])) or [])
    existing=[x for x in control_functions if x!=fid]
    return {
        "is_switch":fid.startswith(("switch:","traveller:")),"core":row,"conflicting_switch_functions":existing,
        "same_switch_already_used":bool(fid and fid in control_functions),
        "typical_supply":bool(row.get("typical_supply")),"usage":usage,
    }


def pl_box_conductors(cable_legs) -> list[dict]:
    """Fold kabelben ud til fysiske ledere med farve/nummer og stabil identitet."""
    out=[]
    for leg in cable_legs or []:
        if not isinstance(leg,dict):
            continue
        cores=cable_conductor_preset(str(leg.get("cable_spec","") or ""))
        for core in cores:
            row=dict(leg); row.update(dict(core))
            out.append(row)
    return out


def normalize_pl_box_wiring(records) -> list[dict]:
    """Normalisér gemt lederfordeling uden at begrænse brugerdefinerede funktioner."""
    out=[]; seen=set()
    for raw in records or []:
        if not isinstance(raw,dict):
            continue
        cable_uid=str(raw.get("cable_uid","") or "").strip()
        leg=str(raw.get("leg","") or "").strip().lower()
        core_id=str(raw.get("core_id","") or "").strip().lower()
        if not cable_uid or leg not in PL_BOX_LEG_CAPTIONS or not core_id:
            continue
        try: point_index=max(0,int(raw.get("point_index",0) or 0))
        except (TypeError,ValueError): point_index=0
        key=(cable_uid,point_index,leg,core_id)
        if key in seen: continue
        seen.add(key)
        out.append({
            "cable_uid":cable_uid,
            "point_index":point_index,
            "leg":leg,
            "core_id":core_id,
            "function":str(raw.get("function","") or "").strip(),
            "note":str(raw.get("note","") or "").strip(),
        })
    return out


def reconcile_pl_box_wiring(records, cable_legs) -> list[dict]:
    """Synkronisér lederplanen med aktuelle kabelben og kabelspecifikationer.

    Døde kabler/ledere fjernes. Hvis kabelredigering kun har flyttet et
    tilslutningspunkt i polyline-listen, genfindes lederen via kabel + side +
    leder-id, når denne kombination er entydig.
    """
    current=normalize_pl_box_wiring(records)
    conductors=pl_box_conductors(cable_legs)
    exact={pl_box_conductor_key(x):x for x in conductors}
    by_loose={}
    for c in conductors:
        loose=(str(c.get("cable_uid","")),str(c.get("leg","")),str(c.get("core_id","")))
        by_loose.setdefault(loose,[]).append(c)
    saved_exact={pl_box_conductor_key(x):x for x in current}
    # 0.48.0 brugte num1..num6 til 7G. 0.48.1 skifter til den visuelle
    # farveprofil blå/brun/sort/grå/rød/hvid. Bevar derfor eksisterende
    # lederfunktioner ved at mappe de gamle stabile id'er til de nye.
    legacy_7g_alias={
        "blue":"num1", "brown":"num2", "black":"num3",
        "grey":"num4", "red":"num5", "white":"num6",
    }
    saved_loose={}
    for x in current:
        loose=(x["cable_uid"],x["leg"],x["core_id"])
        saved_loose.setdefault(loose,[]).append(x)
    out=[]
    for conductor in conductors:
        key=pl_box_conductor_key(conductor)
        saved=saved_exact.get(key)
        if saved is None:
            loose=(key[0],key[2],key[3])
            candidates=saved_loose.get(loose,[])
            current_candidates=by_loose.get(loose,[])
            if len(candidates)==1 and len(current_candidates)==1:
                saved=candidates[0]
            if saved is None and key[3] in legacy_7g_alias:
                legacy_loose=(key[0],key[2],legacy_7g_alias[key[3]])
                legacy_candidates=saved_loose.get(legacy_loose,[])
                if len(legacy_candidates)==1 and len(current_candidates)==1:
                    saved=legacy_candidates[0]
        out.append({
            "cable_uid":key[0], "point_index":key[1], "leg":key[2], "core_id":key[3],
            # 0.55.1: en ny PL-dåse må ikke være pre-forbundet. Bevar kun en
            # funktion, hvis den faktisk var gemt; også PE og N starter blanke.
            "function":str((saved or {}).get("function", "") or "").strip(),
            "note":str((saved or {}).get("note","") or "").strip(),
        })
    return out


def pl_wiring_function_options(associations=None, outlet_type=None) -> list[tuple[str,str]]:
    """Funktioner/samlinger som kan vælges i PL-dåsen.

    Udtagsspecifikke terminaler vises kun, når de fysisk findes. Det holder
    standard-PL enkel, men gør fx Nordtronics P/COM/dimmerudgang valgbare både
    med drag/drop og i den avancerede tabel.
    """
    letters=normalize_associations(associations or [])
    kind=normalize_pl_outlet_type(outlet_type) if outlet_type is not None else "generic"
    rows=[("","Ikke fordelt"),("pe","PE → lampested PE"),("n","N → lampested N"),("l","Fast fase L")]
    if kind=="nordtronic_zigbee":
        fid=f"switch:{letters[0]}" if letters else "switch:lamp"
        letter=letters[0] if letters else ""
        rows.extend([
            (fid,f"P · trykindgang {letter}" if letter else "P · trykindgang / fjedertryk"),
            ("com","COM · fælles til lavspændingstryk"),
            ("dimmed_out","Dæmpet udgang (~) → lampe"),
        ])
    elif letters:
        rows.extend((f"switch:{letter}",f"Tænding {letter} → lampested L({letter})") for letter in letters)
    else:
        rows.append(("switch:lamp","Tænding → lampested L"))
    rows.extend([("reserve","Reserve"),("unused","Ikke tilsluttet")])
    return rows


def pl_wiring_function_caption(function_id: str, associations=None, outlet_type=None) -> str:
    fid=str(function_id or "").strip()
    for value,caption in pl_wiring_function_options(associations,outlet_type):
        if value==fid: return caption
    if fid=="com": return "COM · fælles til lavspændingstryk"
    if fid=="dimmed_out": return "Dæmpet udgang (~) → lampe"
    if fid.startswith("switch:"):
        letter=fid.split(":",1)[1]
        if normalize_pl_outlet_type(outlet_type)=="nordtronic_zigbee":
            return f"P · trykindgang {letter}" if letter and letter!="lamp" else "P · trykindgang / fjedertryk"
        return f"Tænding {letter} → lampested L({letter})" if letter and letter!="lamp" else "Tænding → lampested L"
    if fid.startswith("traveller:"):
        bits=fid.split(":")
        letter=bits[1] if len(bits)>1 else ""
        index=bits[2] if len(bits)>2 and bits[2] in {"1","2"} else "1"
        suffix=f" · tilhørsforhold {letter}" if letter else ""
        return f"Mellemleder {index}{suffix}"
    if fid.startswith("custom:"):
        return fid.split(":",1)[1] or "Brugerdefineret"
    return fid or "Ikke fordelt"


def pl_wiring_lamp_terminal(function_id: str) -> str:
    fid=str(function_id or "")
    if fid=="pe": return "Lampested PE"
    if fid=="n": return "Lampested N"
    if fid=="l": return "Fast L"
    if fid=="com": return "COM"
    if fid=="dimmed_out": return "Dæmpet udgang (~)"
    if fid.startswith("switch:"):
        letter=fid.split(":",1)[1]
        return f"Lampested L({letter})" if letter and letter!="lamp" else "Lampested L"
    if fid.startswith("traveller:"): return ""
    return ""


def pl_box_wiring_status(records, cable_legs) -> dict:
    configured=bool(normalize_pl_box_wiring(records))
    wiring=reconcile_pl_box_wiring(records,cable_legs)
    known=len(wiring)
    assigned=sum(1 for row in wiring if str(row.get("function","") or ""))
    unknown_legs=sum(1 for leg in cable_legs or [] if not cable_conductor_preset(str(leg.get("cable_spec","") or "")))
    live_unassigned=0
    conductors={pl_box_conductor_key(x):x for x in pl_box_conductors(cable_legs)}
    for row in wiring:
        if row.get("function"): continue
        meta=conductors.get(pl_box_conductor_key(row),{})
        if not meta.get("protective") and not meta.get("neutral"):
            live_unassigned+=1
    return {"configured":configured,"known":known,"assigned":assigned,"unassigned":max(0,known-assigned),"live_unassigned":live_unassigned,"unknown_legs":unknown_legs,"wiring":wiring}


def pl_wiring_suggestions(cable_legs, wiring, requirements=None, external_allocations=None) -> list[dict]:
    """Lav forsigtige, ikke-anvendte forslag til en PL-lederplan.

    Entydig brug ved den anden kabelende samt PE/N betragtes som sikre forslag.
    Brun som fast fase og en brun tændleder kræver altid aktiv brugerkontrol.
    Resultatet er kun en forhåndsvisning; kaldende kode vælger selv, hvad der
    faktisk skal anvendes.
    """
    legs=[dict(x) for x in (cable_legs or []) if isinstance(x,dict)]
    rows=reconcile_pl_box_wiring(wiring,legs)
    meta_by_key={pl_box_conductor_key(x):x for x in pl_box_conductors(legs)}
    function_by_key={pl_box_conductor_key(x):str(x.get("function","") or "") for x in rows}
    external={tuple(k):dict(v) for k,v in (external_allocations or {}).items()
              if isinstance(k,(tuple,list)) and len(tuple(k))==4 and isinstance(v,dict)}
    suggestions=[]; reserved=set()

    def add(key,fid,confidence,reason,kind):
        key=tuple(key or ())
        if len(key)!=4 or key in reserved or function_by_key.get(key) or not fid:return False
        meta=meta_by_key.get(key,{})
        cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel")
        side=str(meta.get("leg_caption") or "")
        color=str(meta.get("color_name") or meta.get("display") or key[3])
        suggestions.append({
            "conductor_key":key,"function_id":str(fid),"confidence":str(confidence),"kind":str(kind),
            "conductor_caption":" · ".join(x for x in (cable,side,color) if x),
            "function_caption":pl_wiring_function_caption(fid).split(" → ",1)[0],
            "reason":str(reason or ""),"checked":confidence=="safe",
        })
        reserved.add(key); return True

    # Den samme fysiske lederfarve ved den anden ende er det stærkeste signal.
    for key in sorted(meta_by_key,key=lambda q:(str(q[0]),int(q[1]),str(q[2]),str(q[3]))):
        allocation=external.get(key,{})
        functions=[str(x) for x in allocation.get("functions",[]) if str(x or "")]
        if len(functions)==1 and not allocation.get("conflict"):
            usages=list(allocation.get("usages",[]) or [])
            places=[]
            for usage in usages:
                place=str(usage.get("placement") or "")
                if place and place not in places:places.append(place)
            suffix=(" ved "+", ".join(places[:3])) if places else " ved den anden kabelende"
            add(key,functions[0],"safe","Samme fysiske leder er allerede entydigt allokeret"+suffix+".","external")

    # Beskyttelsesleder og blå neutral er sikre standardforslag for de kendte
    # 3G/5G/7G-profiler. Den konkrete kabelartikel har fortsat forrang.
    for key,meta in meta_by_key.items():
        core_id=str(meta.get("core_id") or key[3])
        if core_id=="pe":add(key,"pe","safe","Gul/grøn leder i den kendte kabelprofil.","protective")
        elif core_id=="blue":add(key,"n","safe","Blå leder i den kendte kabelprofil.","neutral")

    # Manglende direkte tændinger foreslås kun på det krævede kabelben og kun
    # på en endnu fri leder. Forsyningsfarver vælges sidst og kræver kontrol.
    status_rows=pl_switch_requirement_status(requirements or [],rows,[])
    order={core_id:i for i,core_id in enumerate(SWITCH_CONDUCTOR_PREFERRED_ORDER+("brown",))}
    for req in status_rows:
        if str(req.get("state") or "")!="missing" or not req.get("required"):continue
        fid=str(req.get("function_id") or "")
        leg_key=(str(req.get("cable_uid") or ""),int(req.get("point_index",0) or 0),str(req.get("leg") or ""))
        candidates=[key for key in meta_by_key if key[:3]==leg_key and not function_by_key.get(key) and key not in reserved
                    and not external.get(key,{}).get("conflict")]
        candidates.sort(key=lambda key:order.get(str(key[3]),99))
        if not candidates:continue
        key=candidates[0]; core_id=str(key[3])
        safe=core_id in SWITCH_CONDUCTOR_PREFERRED_ORDER
        add(key,fid,"safe" if safe else "review",
            "Fri styreleder på den direkte kabelvej." if safe else "Kun en typisk forsyningsfarve er ledig; kontrollér anvendelsen.",
            "required_switch")

    # Fast fase på brun er nyttig som forslag, men aldrig forhåndsvalgt, fordi
    # en 3G-leders brune leder også kan være den tændte fase til en lampe.
    for key,meta in meta_by_key.items():
        if str(meta.get("core_id") or key[3])=="brown":
            add(key,"l","review","Brun bruges ofte som fast fase, men kan også være tændledning.","brown_live")

    rank={"external":0,"protective":1,"neutral":2,"required_switch":3,"brown_live":4}
    suggestions.sort(key=lambda row:(0 if row.get("confidence")=="safe" else 1,rank.get(str(row.get("kind")),9),str(row.get("conductor_caption") or "").casefold()))
    return suggestions
