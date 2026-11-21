"""Wago-samlinger, terminalbelastning og montagekontrol for PL-dåser."""

from __future__ import annotations

import math

from elplan_core.associations import normalize_associations
from elplan_core.pl_box.model import (
    normalize_pl_box_splices,
    normalize_pl_passthrough_role,
    pl_box_conductor_key,
    pl_box_conductor_ref,
    pl_outlet_profile,
    pl_splice_member_keys,
)
from elplan_core.pl_box.wiring import (
    SWITCH_CONDUCTOR_PREFERRED_ORDER,
    cable_conductor_preset,
    normalize_pl_box_wiring,
    pl_box_conductors,
    pl_box_wiring_status,
    pl_switch_requirement_status,
    pl_wiring_function_caption,
    pl_wiring_requirement_summary,
    reconcile_pl_box_wiring,
)

PL_WAGO_ARTICLE_PORTS = {
    "221-412": 2,
    "221-413": 3,
    "221-415": 5,
    "221-420": 10,
    "2273-202": 2,
    "2273-203": 3,
    "2273-204": 4,
    "2273-205": 5,
    "2273-208": 8,
}

def pl_wago_article_capacity(article_no: str) -> int:
    return int(PL_WAGO_ARTICLE_PORTS.get(str(article_no or "").strip(),0) or 0)


def pl_wago_required_ports(member_count: int, connects_to_outlet: bool = True) -> int:
    """Antal Wago-porte til kabelledere samt evt. én bro til lampeudtaget."""
    return max(0,int(member_count or 0)) + (1 if bool(connects_to_outlet) else 0)


def pl_recommended_wago_article(member_count: int, connects_to_outlet: bool = True) -> str:
    """Mindste anbefalede WAGO 221 til medlemmer og evt. bro til udtaget.

    2273 / P100 kan vælges manuelt i PL-dåsekonfiguratoren, men de automatiske
    anbefalinger holder fortsat fast i 221-serien af hensyn til bagudkompatibilitet
    og fordi 221 er den mest universelle standard i projekterne.
    """
    needed=pl_wago_required_ports(member_count,connects_to_outlet)
    # En tom planlagt samling får stadig den mindste praktiske Wago som forslag.
    needed=max(1,needed)
    preferred=("221-412","221-413","221-415","221-420")
    for article_no in preferred:
        ports=pl_wago_article_capacity(article_no)
        if ports>=needed:
            return article_no
    return ""


def reconcile_pl_box_splices(records, wiring, cable_legs) -> list[dict]:
    """Synkronisér Wago-samlinger mod den aktuelle lederplan.

    Hver Wago beholder sine eksplicit valgte medlemmer, hvis lederne stadig
    findes og fortsat har samme elektriske funktion. Flere Wago'er kan derfor
    eksistere side om side på samme funktion. Medlemskab er globalt entydigt:
    én fysisk leder kan højst ligge i én Wago.
    """
    rows=reconcile_pl_box_wiring(wiring,cable_legs)
    functions={pl_box_conductor_key(x):str(x.get("function","") or "") for x in rows}
    valid=set(functions)
    out=[]; used=set()
    for raw in normalize_pl_box_splices(records):
        fid=str(raw.get("function","") or "")
        source=[k for k in pl_splice_member_keys(raw) if k in valid and functions.get(k)==fid]
        members=[]
        for key in source:
            if key in used:continue
            used.add(key); members.append(pl_box_conductor_ref(key))
        item=dict(raw); item["members"]=members; out.append(item)
    return out


def pl_outlet_terminal_capacity(outlet_type, associations, function_id: str):
    fid=str(function_id or "")
    for terminal in pl_outlet_profile(outlet_type,associations).get("terminals",[]):
        if str(terminal.get("function_id","") or "")==fid:
            cap=terminal.get("capacity")
            return int(cap) if cap else None
    return None


def pl_terminal_occupancy(function_id: str, wiring, splices) -> dict:
    """Beregn fysisk terminalbelastning med vilkårligt antal Wago'er.

    Hver Wago med ``connects_to_outlet=True`` bruger én fysisk klemmeplads via
    sin bro. En ren sløjfe-Wago bruger ingen plads på lampeudtaget. Ledere som
    ikke er medlem af en Wago går direkte til klemmen og tæller én hver.
    """
    fid=str(function_id or "")
    assigned=[pl_box_conductor_key(x) for x in normalize_pl_box_wiring(wiring) if str(x.get("function","") or "")==fid]
    assigned_set=set(assigned)
    matches=[x for x in normalize_pl_box_splices(splices) if str(x.get("function","") or "")==fid]
    outlet_splices=[x for x in matches if bool(x.get("connects_to_outlet",True))]
    loop_splices=[x for x in matches if not bool(x.get("connects_to_outlet",True))]
    outlet_members=[]; loop_members=[]
    for splice in outlet_splices:
        for key in pl_splice_member_keys(splice):
            if key in assigned_set and key not in outlet_members:outlet_members.append(key)
    for splice in loop_splices:
        for key in pl_splice_member_keys(splice):
            if key in assigned_set and key not in outlet_members and key not in loop_members:loop_members.append(key)
    grouped=set(outlet_members)|set(loop_members)
    direct=[k for k in assigned if k not in grouped]
    terminal_count=len(direct)+len(outlet_splices)
    exclusive=(len(outlet_splices)==1 and not direct and set(outlet_members)==assigned_set and not loop_members)
    return {
        "assigned":assigned,"direct":direct,"splice_count":len(outlet_splices),"loop_splice_count":len(loop_splices),
        "terminal_count":terminal_count,"members":outlet_members,"loop_members":loop_members,
        "unspliced":direct,"exclusive_wago":exclusive,
    }


def pl_outlet_capacity_issues(outlet_type, associations, wiring, splices) -> list[dict]:
    profile=pl_outlet_profile(outlet_type,associations)
    out=[]
    for terminal in profile.get("terminals",[]):
        fid=str(terminal.get("function_id","") or "")
        cap=terminal.get("capacity")
        if not fid or not cap:continue
        occ=pl_terminal_occupancy(fid,wiring,splices)
        if occ["terminal_count"]>int(cap):
            out.append({"function_id":fid,"label":str(terminal.get("label") or fid),"capacity":int(cap),**occ})
    return out


def pl_montage_status(outlet_type, associations, wiring, splices, requirements=None, cable_legs=None) -> dict:
    """Kompakt montagekontrol for PL-dåsen."""
    profile=pl_outlet_profile(outlet_type,associations)
    rows=[]; errors=[]; warnings=[]
    normalized_splices=normalize_pl_box_splices(splices)
    splices_by_fid={}
    for splice in normalized_splices:
        splices_by_fid.setdefault(str(splice.get("function","") or ""),[]).append(splice)
    for terminal in profile.get("terminals",[]):
        fid=str(terminal.get("function_id","") or "")
        if not fid:continue
        cap=int(terminal.get("capacity") or 0) or None
        occ=pl_terminal_occupancy(fid,wiring,normalized_splices)
        count=int(occ.get("terminal_count",0) or 0)
        assigned=len(occ.get("assigned",[]) or [])
        function_splices=splices_by_fid.get(fid,[])
        outlet_wagos=[x for x in function_splices if bool(x.get("connects_to_outlet",True))]
        loop_wagos=[x for x in function_splices if not bool(x.get("connects_to_outlet",True))]
        has_wago=bool(outlet_wagos)
        has_loop_wago=bool(loop_wagos)
        state="ok"
        if cap and count>cap:
            state="error"; errors.append(f"{terminal.get('label') or fid} {count}/{cap}")
        elif has_wago and assigned==0:
            state="planned"
        elif assigned==0:
            state="empty"
        rows.append({
            "function_id":fid,"label":str(terminal.get("label") or fid),
            "capacity":cap,"terminal_count":count,"assigned_count":assigned,
            "has_wago":has_wago,"has_loop_wago":has_loop_wago,
            "wago_count":len(outlet_wagos),"loop_wago_count":len(loop_wagos),"state":state,
        })

    wago_rows=[]
    for splice in normalized_splices:
        fid=str(splice.get("function","") or "")
        members=pl_splice_member_keys(splice)
        article_no=str(splice.get("article_no","") or "").strip()
        connects=bool(splice.get("connects_to_outlet",True))
        role=normalize_pl_passthrough_role(splice.get("conductor_role"),fid)
        destination_uid=str(splice.get("destination_light_uid","") or "")
        destination_missing=not connects and role in {"switch","traveller_1","traveller_2"} and not destination_uid
        needed=pl_wago_required_ports(len(members),connects)
        article_cap=pl_wago_article_capacity(article_no)
        if not article_no:
            state="warning"; warnings.append(f"Wago {pl_wiring_function_caption(fid,associations)} mangler artikel")
        elif article_cap and article_cap<needed:
            state="error"; errors.append(f"Wago {article_no} {needed}/{article_cap}")
        elif not members:
            state="planned"
        else:
            state="ok"
        if destination_missing:
            warnings.append(f"{pl_wiring_function_caption(fid,associations)} mangler tilhørende lampested")
            if state in {"ok","planned"}:state="warning"
        wago_rows.append({
            "id":str(splice.get("id","") or ""),"function_id":fid,
            "article_no":article_no,"member_count":len(members),"needed_ports":needed,
            "article_capacity":article_cap,"connects_to_outlet":connects,"state":state,
            "destination_light_uid":destination_uid,"destination_missing":destination_missing,
        })

    live_unassigned=0
    if cable_legs is not None:
        wiring_status=pl_box_wiring_status(wiring,cable_legs)
        live_unassigned=int(wiring_status.get("live_unassigned",0) or 0)
        if live_unassigned:warnings.append(f"{live_unassigned} aktive ledere uden funktion")

    req_summary=pl_wiring_requirement_summary(requirements or [],wiring,normalized_splices)
    if req_summary.get("missing"):errors.append(f"{req_summary['missing']} tænding(er) mangler leder")
    if req_summary.get("wrong_cable"):errors.append(f"{req_summary['wrong_cable']} tænding(er) på forkert kabel")
    if req_summary.get("duplicate"):errors.append(f"{req_summary['duplicate']} dublettildeling(er)")
    if req_summary.get("manual"):warnings.append(f"{req_summary['manual']} korrespondance/krydsning kræver kontrol")
    unsupported=list(profile.get("unsupported_switches") or [])
    if unsupported:warnings.append("udtaget mangler fysisk klemme til "+", ".join(x.split(":",1)[-1] for x in unsupported))

    state="error" if errors else ("warning" if warnings else "ready")
    return {
        "state":state,"terminals":rows,"wago":wago_rows,
        "errors":errors,"warnings":warnings,"live_unassigned":live_unassigned,
        "requirements":req_summary,
    }


def pl_wiring_workflow_issues(cable_legs, wiring, requirements=None, splices=None,
                              outlet_type="generic", associations=None,
                              external_allocations=None) -> list[dict]:
    """Returnér en handlingsorienteret liste over uløste PL-opgaver.

    Hvert punkt har om muligt en fysisk ``conductor_key`` eller en elektrisk
    ``function_id``. GUI'en kan derfor springe direkte til problemet i stedet
    for kun at vise en lang statuslinje. Funktionen ændrer aldrig lederplanen.
    """
    legs=[dict(x) for x in (cable_legs or []) if isinstance(x,dict)]
    rows=reconcile_pl_box_wiring(wiring,legs)
    normalized_splices=reconcile_pl_box_splices(splices or [],rows,legs)
    conductors=pl_box_conductors(legs)
    meta_by_key={pl_box_conductor_key(x):x for x in conductors}
    function_by_key={pl_box_conductor_key(x):str(x.get("function","") or "") for x in rows}
    external={tuple(k):dict(v) for k,v in (external_allocations or {}).items()
              if isinstance(k,(tuple,list)) and len(tuple(k))==4 and isinstance(v,dict)}
    issues=[]; used_ids=set(); covered_keys=set()

    def add(issue_id, severity, title, *, detail="", key=None, function_id="", kind=""):
        issue_id=str(issue_id or "")
        if not issue_id or issue_id in used_ids:return
        used_ids.add(issue_id)
        conductor_key=tuple(key) if isinstance(key,(tuple,list)) and len(tuple(key))==4 else None
        if conductor_key is not None:covered_keys.add(conductor_key)
        issues.append({
            "id":issue_id,"severity":str(severity or "warning"),"title":str(title or "Kontrollér lederplan"),
            "detail":str(detail or ""),"conductor_key":conductor_key,
            "function_id":str(function_id or ""),"kind":str(kind or ""),
        })

    # Konflikter langs samme fysiske kabel er vigtigst: de kan ikke løses ved
    # at gætte lokalt, men den konkrete leder kan stadig fokuseres grafisk.
    for key,allocation in external.items():
        functions=[str(x) for x in allocation.get("functions",[]) if str(x or "")]
        if not allocation.get("conflict") and len(functions)<=1:continue
        meta=meta_by_key.get(key,{})
        cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel")
        color=str(meta.get("color_name") or meta.get("display") or key[3])
        labels=" / ".join(pl_wiring_function_caption(fid,associations).split(" → ",1)[0] for fid in functions)
        add("external:"+"|".join(map(str,key)),"error",f"{cable} · {color} bruges forskelligt i kabelruten",
            detail=(labels or "Flere funktioner fundet")+". Vælg den korrekte elektriske identitet manuelt.",
            key=key,kind="external_conflict")

    req_statuses=pl_switch_requirement_status(requirements or [],rows,normalized_splices)
    for index,req in enumerate(req_statuses):
        state=str(req.get("state") or "")
        if state in {"ok","related"}:continue
        fid=str(req.get("function_id") or "")
        association=str(req.get("association") or "")
        cable=str(req.get("cable_display") or "kabelvejen")
        leg_identity=(str(req.get("cable_uid") or ""),int(req.get("point_index",0) or 0),str(req.get("leg") or ""))
        local_keys=[key for key,value in function_by_key.items() if key[:3]==leg_identity and value==fid]
        all_keys=[key for key,value in function_by_key.items() if value==fid]
        candidate_keys=[key for key,value in function_by_key.items() if key[:3]==leg_identity and not value]
        preferred={core_id:i for i,core_id in enumerate(SWITCH_CONDUCTOR_PREFERRED_ORDER+("brown",))}
        candidate_keys.sort(key=lambda key:preferred.get(str(key[3]),99))
        key=(local_keys or all_keys or candidate_keys or [None])[0]
        label=f"Tænding {association}" if association else pl_wiring_function_caption(fid,associations).split(" → ",1)[0]
        if state=="missing":
            title=f"{label} mangler en leder på {cable}"
            severity="error"
        elif state=="wrong_cable":
            title=f"{label} er placeret på et andet kabelben"
            severity="error"
        elif state=="duplicate":
            title=f"{label} er tildelt flere ledere på samme kabelben"
            severity="error"
        else:
            title=f"{label} kræver manuel terminalkontrol"
            severity="review"
        add(f"requirement:{index}:{state}:{fid}",severity,title,detail=str(req.get("detail") or ""),
            key=key,function_id=fid,kind="requirement_"+state)

    for capacity in pl_outlet_capacity_issues(outlet_type,associations or [],rows,normalized_splices):
        fid=str(capacity.get("function_id") or "")
        add(f"capacity:{fid}","error",
            f"{capacity.get('label') or fid} er overfyldt: {capacity.get('terminal_count')}/{capacity.get('capacity')}",
            detail="Tilføj eller redigér en Wago-samling.",function_id=fid,kind="capacity")

    for splice in normalized_splices:
        if bool(splice.get("connects_to_outlet",True)):continue
        fid=str(splice.get("function") or "")
        role=normalize_pl_passthrough_role(splice.get("conductor_role"),fid)
        if role not in {"switch","traveller_1","traveller_2"} or str(splice.get("destination_light_uid") or ""):continue
        members=pl_splice_member_keys(splice)
        label=pl_wiring_function_caption(fid,associations).split(" → ",1)[0]
        add(f"destination:{splice.get('id')}","error",f"{label} mangler tilhørende lampested",
            detail="Vælg hvilket andet lampeudtag gennemsløjfningen fortsætter til.",
            key=members[0] if members else None,function_id=fid,kind="missing_destination")

    # Én opgave pr. aktiv, helt lokal løs leder. PE og blå håndteres af de
    # sikre forslag, men tæller ikke som aktive tænd-/faseledere i statuslisten.
    for key,meta in meta_by_key.items():
        if function_by_key.get(key) or key in covered_keys:continue
        if meta.get("protective") or meta.get("neutral"):continue
        allocation=external.get(key,{})
        if allocation.get("functions"):
            # En entydig fjernallokering vises allerede med kædeled i grafikken
            # og kan overtages via forslag; det er ikke en ukendt leder.
            continue
        cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel")
        side=str(meta.get("leg_caption") or "")
        color=str(meta.get("color_name") or meta.get("display") or key[3])
        add("unassigned:"+"|".join(map(str,key)),"warning",f"{cable} · {color} mangler funktion",
            detail="Vælg en klemme, reserve eller ikke tilsluttet.",key=key,kind="unassigned")

    for index,leg in enumerate(legs):
        if cable_conductor_preset(str(leg.get("cable_spec") or "")):continue
        cable=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel")
        add(f"unknown:{index}:{cable}","review",f"{cable} har ukendt lederopbygning",
            detail=f"Kabeltypen {leg.get('cable_spec') or '—'} kan ikke fordeles automatisk.",kind="unknown_profile")

    priority={"error":0,"warning":1,"review":2}
    issues.sort(key=lambda row:(priority.get(str(row.get("severity")),3),str(row.get("title") or "").casefold()))
    return issues
