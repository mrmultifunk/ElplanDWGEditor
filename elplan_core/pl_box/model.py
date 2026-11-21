"""PL-dåsens datamodel, normalisering og stabile referencer."""

from __future__ import annotations

import math
import re
import uuid

from elplan_core.associations import normalize_associations

PL_BOX_ORIENTATIONS = {
    0: "0° · 1-2-3 mod plantegningens top",
    90: "90° · 1-2-3 mod højre",
    180: "180° · 1-2-3 mod bunden",
    270: "270° · 1-2-3 mod venstre",
}


PL_OUTLET_TYPES = {
    "generic": "Generisk PL / samleklemmer",
    "lk_classic": "LK klassisk lampeudtag",
    "wiser_dimmer": "LK Wiser / dæmpbar",
    "nordtronic_zigbee": "Nordtronic lampeudtag m. Zigbee dimmer",
}

PL_BOX_ENTRY_COUNT = 6


PL_BOX_LEG_CAPTIONS = {"endpoint": "Ende", "before": "Side A", "after": "Side B"}


PL_PASSTHROUGH_ROLES = {
    "switch": "Tændleder",
    "traveller_1": "Mellemleder 1",
    "traveller_2": "Mellemleder 2",
    "pe": "Beskyttelsesleder PE",
    "n": "Nul N",
    "l": "Fast fase L",
    "reserve": "Reserve",
    "unused": "Ikke tilsluttet",
}

def normalize_pl_box_orientation(value) -> int:
    """Normalisér PL-dåsens fysiske orientering til 0/90/180/270 grader."""
    try:
        angle=int(round(float(value))) % 360
    except (TypeError,ValueError):
        angle=0
    return min(PL_BOX_ORIENTATIONS, key=lambda candidate: min((angle-candidate)%360,(candidate-angle)%360))


def normalize_pl_outlet_type(value) -> str:
    key=str(value or "").strip().lower()
    aliases={
        "": "generic", "pl": "generic", "generic_pl": "generic",
        "lk": "lk_classic", "classic": "lk_classic", "lk_original": "lk_classic",
        "wiser": "wiser_dimmer", "dimmer": "wiser_dimmer", "smart": "wiser_dimmer",
        "nordtronic": "nordtronic_zigbee", "nordtronic_zigbee_dimmer": "nordtronic_zigbee",
        "98425033": "nordtronic_zigbee", "ceiling_outlet_zigbee": "nordtronic_zigbee",
    }
    key=aliases.get(key,key)
    return key if key in PL_OUTLET_TYPES else "generic"

def pl_box_port_layout(orientation=0) -> dict[int,tuple[str,int]]:
    """Returnér fysisk side + rækkeposition for indføring 1..6.

    Orienteringen er relativ til plantegningens top. Position 0 er venstre-til-højre
    på top/bund og top-til-bund på venstre/højre side.
    """
    angle=normalize_pl_box_orientation(orientation)
    layouts={
        0: {1:("top",0),2:("top",1),3:("top",2),4:("bottom",0),5:("bottom",1),6:("bottom",2)},
        90:{1:("right",0),2:("right",1),3:("right",2),4:("left",0),5:("left",1),6:("left",2)},
        180:{1:("bottom",2),2:("bottom",1),3:("bottom",0),4:("top",2),5:("top",1),6:("top",0)},
        270:{1:("left",2),2:("left",1),3:("left",0),4:("right",2),5:("right",1),6:("right",0)},
    }
    return dict(layouts[angle])


def pl_outlet_profile(outlet_type, associations=None) -> dict:
    """Returnér terminalrækken til den grafiske lampeudtagseditor.

    Funktions-id'erne er de samme som i ``pl_box_wiring``. Derfor er profilen
    alene en fysisk/visuel fortolkning og ændrer ikke elektriske data.
    """
    kind=normalize_pl_outlet_type(outlet_type)
    letters=normalize_associations(associations or [])
    switch_ids=[f"switch:{x}" for x in letters] if letters else ["switch:lamp"]
    if kind=="lk_classic":
        # Klassisk LK-lampeudtag som på den gængse N/L/PE/M1/M2 klemrække.
        mapped=switch_ids[:2]
        terminals=[
            {"function_id":"n","label":"N","subtitle":"Nul","capacity":4},
            {"function_id":"l","label":"L","subtitle":"Fast fase","capacity":4},
            {"function_id":"pe","label":"PE","subtitle":"Beskyttelsesleder","capacity":4},
        ]
        for index,fid in enumerate(mapped,1):
            letter=fid.split(":",1)[1]
            terminals.append({"function_id":fid,"label":f"M{index}","subtitle":f"Tænding {letter}" if letter!="lamp" else "Tændt udgang","capacity":4})
        # Vis tom fysisk M-klemme også når der endnu ikke er et tilhørsforhold.
        while len(terminals)<5:
            index=len(terminals)-2
            terminals.append({"function_id":"", "label":f"M{index}", "subtitle":"Ikke tildelt", "capacity":4})
        return {
            "id":kind,"caption":PL_OUTLET_TYPES[kind],"short":"LK klassisk",
            "terminals":terminals,"unsupported_switches":switch_ids[2:],
            "compact_hint":"N · L · PE · M1 · M2",
            "hint":"Klemrække N · L · PE · M1 · M2. M1/M2 følger lampestedets tilhørsforhold i rækkefølge. Maks 4 ledere pr. terminal.",
        }
    if kind=="wiser_dimmer":
        fid=switch_ids[0] if switch_ids else "switch:lamp"
        letter=fid.split(":",1)[1] if ":" in fid else "lamp"
        terminals=[
            {"function_id":"pe","label":"PE","subtitle":"Beskyttelsesleder","capacity":2},
            {"function_id":"n","label":"N","subtitle":"Nul","capacity":2},
            {"function_id":fid,"label":"~","subtitle":f"Styret udgang · {letter}" if letter!="lamp" else "Styret/dæmpet udgang","capacity":2},
            {"function_id":"l","label":"L","subtitle":"Fast forsyning","capacity":2},
        ]
        return {
            "id":kind,"caption":PL_OUTLET_TYPES[kind],"short":"Wiser / dæmpbar",
            "terminals":terminals,"unsupported_switches":switch_ids[1:],
            "compact_hint":"PE · N · ~ · L",
            "hint":"Klemrække PE · N · styret/dæmpet udgang · L. Maks 2 ledere pr. terminal og én fysisk styret udgang.",
        }
    if kind=="nordtronic_zigbee":
        # Nordtronic 98425033 har en dedikeret trykindgang. Den logiske
        # tændingsfunktion beholdes som switch:<tilhørsforhold>, men vises og
        # termineres fysisk på P. Dermed virker den eksisterende kontrol af
        # afbryder -> lampested stadig, uden at P forveksles med dimmerudgangen.
        fid=switch_ids[0] if switch_ids else "switch:lamp"
        letter=fid.split(":",1)[1] if ":" in fid else "lamp"
        terminals=[
            {"function_id":fid,"label":"P","subtitle":f"Trykindgang · {letter}" if letter!="lamp" else "Trykindgang / fjedertryk","capacity":3},
            {"function_id":"com","label":"COM","subtitle":"Fælles til lavspændingstryk","capacity":3},
            {"function_id":"pe","label":"PE","subtitle":"Beskyttelsesleder","capacity":4},
            {"function_id":"n","label":"N","subtitle":"Nul / forsyning","capacity":4},
            {"function_id":"dimmed_out","label":"~","subtitle":"Dæmpet udgang · 5–200 W LED","capacity":2},
            {"function_id":"l","label":"L","subtitle":"Fast forsyning · 100–240 Vac","capacity":4},
        ]
        return {
            "id":kind,"caption":PL_OUTLET_TYPES[kind],"short":"Nordtronic Zigbee",
            "article_no":"98425033","ean":"5704629006065",
            "terminals":terminals,"unsupported_switches":switch_ids[1:],
            "compact_hint":"P = tryk · COM = fælles · ~ = dæmpet udgang",
            "hint":"Nordtronic 98425033 · P = trykindgang · COM = fælles til lavspændingstryk · ~ = dæmpet udgang. L, N og PE er separate terminaler. Ingen forbindelser oprettes automatisk.",
        }
    terminals=[
        {"function_id":"pe","label":"PE","subtitle":"Lampested PE"},
        {"function_id":"n","label":"N","subtitle":"Lampested N"},
        {"function_id":"l","label":"L","subtitle":"Fast fase"},
    ]
    for fid in switch_ids:
        letter=fid.split(":",1)[1]
        terminals.append({"function_id":fid,"label":f"T {letter}" if letter!="lamp" else "T",
                          "subtitle":f"Tænding {letter}" if letter!="lamp" else "Tændt lampe"})
    return {
        "id":"generic","caption":PL_OUTLET_TYPES["generic"],"short":"Generisk PL",
        "terminals":terminals,"unsupported_switches":[],
        "compact_hint":"PE · N · L · tændinger",
        "hint":"Generisk klemrække med PE, N, fast L og én klemme pr. tænding.",
    }


def normalize_pl_box_entries(records) -> dict[str, dict]:
    """Normalisér PL-dåsens seks kabelindføringer.

    Referencen gemmer kabel-UID og benets logiske side. ``point_index`` gemmes
    kun som ekstra sporbarhed; ved senere kabelredigering kan et ændret indeks
    genfindes ud fra kabel-UID + side.
    """
    out: dict[str, dict] = {}
    source = records if isinstance(records, dict) else {}
    for raw_port, raw in source.items():
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            continue
        if not (1 <= port <= PL_BOX_ENTRY_COUNT) or not isinstance(raw, dict):
            continue
        cable_uid = str(raw.get("cable_uid", "") or "").strip()
        leg = str(raw.get("leg", "") or "").strip().lower()
        if not cable_uid or leg not in PL_BOX_LEG_CAPTIONS:
            continue
        try:
            point_index = max(0, int(raw.get("point_index", 0) or 0))
        except (TypeError, ValueError):
            point_index = 0
        out[str(port)] = {
            "cable_uid": cable_uid,
            "point_index": point_index,
            "leg": leg,
            "note": str(raw.get("note", "") or "").strip(),
        }
    return out


def normalize_pl_field_record(record) -> dict:
    """Normalisér read-only feltdokumentation fra PL-dåse-PWA'en.

    Posten må bevidst ikke indeholde eller påvirke lederfunktioner, terminaler
    eller Wago-samlinger. Den beskriver alene de seks fysiske indføringer.
    """
    if not isinstance(record, dict):
        return {}
    box_id=str(record.get("box_id",record.get("id","")) or "").strip()[:80]
    if not box_id:
        return {}

    entries_by_position={}
    for raw in record.get("entries",[]) or []:
        if not isinstance(raw,dict):continue
        try:position=int(raw.get("position",0) or 0)
        except (TypeError,ValueError):continue
        if not 1<=position<=PL_BOX_ENTRY_COUNT:continue
        marker=raw.get("marker"); normalized_marker=None
        if isinstance(marker,dict):
            try:
                x=float(marker.get("x")); y=float(marker.get("y"))
                if math.isfinite(x) and math.isfinite(y):
                    normalized_marker={"x":max(0.0,min(1.0,x)),"y":max(0.0,min(1.0,y))}
            except (TypeError,ValueError):pass
        entries_by_position[position]={
            "position":position,
            "function":str(raw.get("function",raw.get("fn","")) or "").strip()[:80],
            "cable":str(raw.get("cable","") or "").strip()[:160],
            "note":str(raw.get("note","") or "").strip()[:500],
            "marker":normalized_marker,
        }
    entries=[entries_by_position.get(position,{"position":position,"function":"","cable":"","note":"","marker":None}) for position in range(1,PL_BOX_ENTRY_COUNT+1)]

    photos=[]; seen_photo_ids=set()
    for raw in record.get("photos",[]) or []:
        if not isinstance(raw,dict):continue
        photo_id=str(raw.get("id","") or "").strip()[:80]
        url=str(raw.get("url","") or "").strip()[:2000]
        if not photo_id or photo_id in seen_photo_ids or not url:continue
        seen_photo_ids.add(photo_id); markers=[]
        for marker in raw.get("markers",[]) or []:
            if not isinstance(marker,dict):continue
            try:
                position=int(marker.get("position",0) or 0); x=float(marker.get("x")); y=float(marker.get("y"))
            except (TypeError,ValueError):continue
            if 1<=position<=PL_BOX_ENTRY_COUNT and math.isfinite(x) and math.isfinite(y):
                markers.append({"position":position,"x":max(0.0,min(1.0,x)),"y":max(0.0,min(1.0,y))})
        photos.append({"id":photo_id,"url":url,"markers":markers})
        if len(photos)>=10:break

    return {
        "source":"pl-daase",
        "source_url":str(record.get("source_url","") or "").strip()[:2000],
        "box_id":box_id,
        "name":str(record.get("name","") or "").strip()[:160],
        "ref":str(record.get("ref","") or "").strip()[:160],
        "note":str(record.get("note","") or "").strip()[:2000],
        "exported":str(record.get("exported","") or "").strip()[:80],
        "imported_at":str(record.get("imported_at","") or "").strip()[:80],
        "entries":entries,
        "photos":photos,
    }


def pl_field_cable_spec_key(value: str) -> str:
    """Udled sammenlignelig kabelopbygning fra fx ``NOMP 3G1,5``."""
    text=str(value or "").upper().replace(" ","").replace("²","2")
    match=re.search(r"(?<!\d)(\d{1,2}[GX]\d+(?:[,.]\d+)?)",text)
    if not match:return ""
    return match.group(1).replace(".",",")


def pl_field_entry_state(entry) -> str:
    """Returnér ``unregistered``, ``empty`` eller ``cable`` for en PWA-post."""
    raw=entry if isinstance(entry,dict) else {}
    function=str(raw.get("function",raw.get("fn","")) or "").strip()
    cable=str(raw.get("cable","") or "").strip()
    note=str(raw.get("note","") or "").strip()
    if function.casefold()=="tom / ikke tilsluttet".casefold():return "empty"
    return "cable" if function or cable or note else "unregistered"


def pl_field_suggested_leg(entry, cable_legs, used_keys=None) -> dict | None:
    """Foreslå kun et kabelben når kabeltypen giver ét entydigt match."""
    if pl_field_entry_state(entry)!="cable":return None
    wanted=pl_field_cable_spec_key(str((entry or {}).get("cable","") or ""))
    if not wanted:return None
    used=set(used_keys or set()); matches=[]
    for leg in cable_legs or []:
        if not isinstance(leg,dict):continue
        key=(str(leg.get("cable_uid","") or ""),int(leg.get("point_index",0) or 0),str(leg.get("leg","") or ""))
        if key in used:continue
        if pl_field_cable_spec_key(str(leg.get("cable_spec","") or ""))==wanted:matches.append(dict(leg))
    return matches[0] if len(matches)==1 else None


def pl_box_leg_key(record: dict) -> tuple[str, str]:
    return (str(record.get("cable_uid", "") or ""), str(record.get("leg", "") or ""))


def reconcile_pl_box_entries(entries, cable_legs) -> dict[str, dict]:
    """Fjern døde PL-referencer og opdatér pointindeks efter kabelredigering."""
    current = normalize_pl_box_entries(entries)
    legs = [dict(x) for x in (cable_legs or []) if isinstance(x, dict)]
    exact = {(str(x.get("cable_uid","")), int(x.get("point_index",0) or 0), str(x.get("leg",""))): x for x in legs}
    by_key: dict[tuple[str,str], list[dict]] = {}
    for leg in legs:
        by_key.setdefault(pl_box_leg_key(leg), []).append(leg)
    out: dict[str, dict] = {}
    used_keys: set[tuple[str,int,str]] = set()
    for port in sorted(current, key=int):
        row = current[port]
        key3 = (row["cable_uid"], int(row.get("point_index",0)), row["leg"])
        match = exact.get(key3)
        if match is None:
            candidates = by_key.get((row["cable_uid"], row["leg"]), [])
            if len(candidates) == 1:
                match = candidates[0]
        if match is None:
            continue
        match_key = (str(match.get("cable_uid","")), int(match.get("point_index",0) or 0), str(match.get("leg","")))
        if match_key in used_keys:
            continue
        used_keys.add(match_key)
        out[port] = {
            "cable_uid": str(match.get("cable_uid", "")),
            "point_index": int(match.get("point_index", 0) or 0),
            "leg": str(match.get("leg", "")),
            "note": str(row.get("note", "") or "").strip(),
        }
    return out


def pl_box_unplaced_legs(entries, cable_legs) -> list[dict]:
    normalized = reconcile_pl_box_entries(entries, cable_legs)
    placed = {(r["cable_uid"], int(r["point_index"]), r["leg"]) for r in normalized.values()}
    return [dict(x) for x in cable_legs or [] if (str(x.get("cable_uid","")), int(x.get("point_index",0) or 0), str(x.get("leg",""))) not in placed]


def auto_assign_pl_box_entries(cable_legs, existing=None) -> dict[str, dict]:
    """Fordel kabelben på de seks PL-indføringer ud fra udgående retning."""
    legs = [dict(x) for x in (cable_legs or [])]
    result = reconcile_pl_box_entries(existing or {}, legs)
    occupied = {int(p) for p in result}
    placed = {(r["cable_uid"], int(r["point_index"]), r["leg"]) for r in result.values()}

    def preferred_ports(leg):
        dx, dy = leg.get("vector", (0.0, 0.0))
        dx, dy = float(dx), float(dy)
        row = [1,2,3] if dy >= 0 else [4,5,6]
        if abs(dx) <= max(abs(dy)*0.35, 1e-9):
            order = [row[1], row[0], row[2]]
        elif dx < 0:
            order = [row[0], row[1], row[2]]
        else:
            order = [row[2], row[1], row[0]]
        other = [4,5,6] if row[0] == 1 else [1,2,3]
        return order + other

    for leg in legs:
        key=(str(leg.get("cable_uid","")), int(leg.get("point_index",0) or 0), str(leg.get("leg","")))
        if key in placed:
            continue
        port = next((p for p in preferred_ports(leg) if p not in occupied), None)
        if port is None:
            break
        result[str(port)] = {
            "cable_uid": key[0], "point_index": key[1], "leg": key[2], "note": ""
        }
        occupied.add(port); placed.add(key)
    return normalize_pl_box_entries(result)


def pl_box_status(entries, cable_legs) -> dict:
    reconciled = reconcile_pl_box_entries(entries, cable_legs)
    required = len(list(cable_legs or []))
    used = len(reconciled)
    return {
        "used": used,
        "capacity": PL_BOX_ENTRY_COUNT,
        "required": required,
        "unplaced": max(0, required-used),
        "overflow": max(0, required-PL_BOX_ENTRY_COUNT),
        "entries": reconciled,
    }


def pl_box_conductor_key(record: dict) -> tuple[str,int,str,str]:
    return (
        str(record.get("cable_uid","") or ""), int(record.get("point_index",0) or 0),
        str(record.get("leg","") or ""), str(record.get("core_id","") or ""),
    )


def pl_box_conductor_ref(key) -> dict:
    key=tuple(key or ())
    if len(key)!=4:return {}
    return {"cable_uid":str(key[0] or ""),"point_index":int(key[1] or 0),"leg":str(key[2] or ""),"core_id":str(key[3] or "")}


def normalize_pl_splice_position(value):
    """Normalisér en manuel Wago-position som relative koordinater i PL-dåsen."""
    if not isinstance(value,dict):return None
    try:
        x=float(value.get("x")); y=float(value.get("y"))
    except (TypeError,ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):return None
    return {"x":max(0.0,min(1.0,x)),"y":max(0.0,min(1.0,y))}


def _normalize_bool(value, default=True) -> bool:
    if value is None:return bool(default)
    if isinstance(value,bool):return value
    if isinstance(value,(int,float)):return bool(value)
    text=str(value).strip().lower()
    if text in {"0","false","nej","no","off"}:return False
    if text in {"1","true","ja","yes","on"}:return True
    return bool(default)


def normalize_pl_passthrough_role(value, function_id: str = "") -> str:
    """Normalisér den elektriske rolle for en samlemuffe uden udtagsbro."""
    role=str(value or "").strip().lower().replace("-","_").replace(" ","_")
    aliases={
        "tændleder":"switch","taendleder":"switch","switched":"switch",
        "mellemleder_1":"traveller_1","traveler_1":"traveller_1","traveller1":"traveller_1",
        "mellemleder_2":"traveller_2","traveler_2":"traveller_2","traveller2":"traveller_2",
        "fase":"l","fast_fase":"l","nul":"n","jord":"pe",
    }
    role=aliases.get(role,role)
    if role in PL_PASSTHROUGH_ROLES:return role
    fid=str(function_id or "").strip().lower()
    if fid.startswith("switch:"):return "switch"
    if fid.startswith("traveller:"):
        tail=fid.split(":")[-1]
        return "traveller_2" if tail=="2" else "traveller_1"
    if fid in {"pe","n","l","reserve","unused"}:return fid
    return ""


def pl_passthrough_function(role: str, association: str = "") -> str:
    """Byg et stabilt funktions-id til en gennemsløjfet leder.

    De to mellemledere får forskellige net-id'er. Dermed kan de ikke ved en
    fejl blive samlet i samme muffe, selv om de tilhører samme tændingskreds.
    """
    normalized=normalize_pl_passthrough_role(role)
    letters=normalize_associations([association])
    letter=letters[0] if letters else ""
    if normalized=="switch":return f"switch:{letter}" if letter else ""
    if normalized in {"traveller_1","traveller_2"}:
        index="1" if normalized.endswith("1") else "2"
        return f"traveller:{letter}:{index}" if letter else ""
    return normalized if normalized in {"pe","n","l","reserve","unused"} else ""


def pl_passthrough_function_parts(function_id: str) -> dict:
    """Udled rolle og tilhørsbogstav fra et gemt PL-funktions-id."""
    fid=str(function_id or "").strip()
    role=normalize_pl_passthrough_role("",fid)
    association=""
    if fid.startswith("switch:"):
        association=str(fid.split(":",1)[1] or "")
    elif fid.startswith("traveller:"):
        bits=fid.split(":")
        association=str(bits[1] or "") if len(bits)>1 else ""
    association=(normalize_associations([association]) or [""])[0]
    return {"function":fid,"role":role,"association":association}


def normalize_pl_box_splices(records) -> list[dict]:
    """Normalisér manuelle Wago-samlinger.

    Flere Wago'er må gerne have samme elektriske funktion. Det afspejler den
    fysiske montage, hvor installatøren fx kan bruge flere N-, PE- eller
    tændingsmuffer i samme PL-dåse. En fysisk leder kan fortsat kun være medlem
    af én Wago-samling ad gangen.

    ``connects_to_outlet`` skelner mellem to montageformer:
    - ``True``: Wago'en har én fysisk bro videre til lampeudtagets klemme.
    - ``False``: Wago'en er kun en intern sløjfe/samling i PL-dåsen.

    Medlemmer er altid eksplicitte. Det gør flere Wago'er på samme funktion
    entydige og forhindrer, at én Wago automatisk opsluger alle ledere på
    funktionen.
    """
    out=[]; used=set(); used_ids=set()
    for raw in records or []:
        if not isinstance(raw,dict):continue
        fid=str(raw.get("function","") or "").strip()
        if not fid:continue
        sid=str(raw.get("id","") or "").strip() or uuid.uuid4().hex
        if sid in used_ids:sid=uuid.uuid4().hex
        members=[]
        for item in raw.get("members",[]) or []:
            if not isinstance(item,dict):continue
            key=pl_box_conductor_key(item)
            if not all([key[0],key[2],key[3]]) or key in used:continue
            used.add(key); members.append(pl_box_conductor_ref(key))
        used_ids.add(sid)
        connects=_normalize_bool(raw.get("connects_to_outlet"),True)
        role=normalize_pl_passthrough_role(raw.get("conductor_role"),fid)
        assoc_values=normalize_associations([raw.get("destination_association","")])
        destination_association=assoc_values[0] if assoc_values else ""
        if not destination_association:
            destination_association=pl_passthrough_function_parts(fid).get("association","")
        item={
            "id":sid,"function":fid,"members":members,
            "article_no":str(raw.get("article_no","") or "").strip(),
            "note":str(raw.get("note","") or "").strip(),
            "connects_to_outlet":connects,
        }
        if not connects:
            item["conductor_role"]=role
            item["destination_light_uid"]=str(raw.get("destination_light_uid","") or "").strip()
            item["destination_association"]=destination_association
        position=normalize_pl_splice_position(raw.get("position"))
        if position is not None:item["position"]=position
        out.append(item)
    return out


def pl_splice_member_keys(splice: dict) -> list[tuple[str,int,str,str]]:
    return [pl_box_conductor_key(x) for x in (splice or {}).get("members",[]) if isinstance(x,dict)]
