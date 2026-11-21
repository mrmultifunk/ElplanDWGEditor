"""Rumafgrænsning og ekstra BOM-rum for symbolforekomster."""

from __future__ import annotations

from elplan_core.rooms import room_for_point


def normalize_placement_bom_room_additions(data) -> dict[str, list[str]]:
    """Normalisér manuelle *ekstra* BOM-rum pr. symbolforekomst.

    Det fysiske rum ændres aldrig. En placering kan derfor godt bidrage til
    eksempelvis både Gang (fysisk) og Køkken (manuelt ekstra BOM-rum), mens
    den samlede ``Alle rum``-BOM fortsat kun tæller selve artiklen én gang.
    """
    if not isinstance(data,dict):
        return {}
    out={}
    for raw_uid,raw_rooms in data.items():
        uid=str(raw_uid or "").strip()
        if not uid:continue
        values=raw_rooms if isinstance(raw_rooms,(list,tuple,set)) else [raw_rooms]
        clean=[]
        for raw_room in values:
            room_uid=str(raw_room or "").strip()
            if room_uid and room_uid not in clean:clean.append(room_uid)
        if clean:out[uid]=clean
    return out


def placement_bom_room_uids(placement, rooms=None, additions=None, include_physical=True) -> list[str]:
    """Rum som en symbolforekomst bidrager til i rum-BOM.

    Første rum er altid det fysiske rum, når ``include_physical`` er sandt.
    Derefter følger brugerens ekstra BOM-rum. Dubletter fjernes.
    """
    room_list=list(rooms or [])
    valid={str(getattr(r,"uid","") or "") for r in room_list}
    out=[]
    if include_physical and placement is not None and room_list:
        room=room_for_point(room_list,float(getattr(placement,"x",0.0)),float(getattr(placement,"y",0.0)))
        uid=str(getattr(room,"uid","") or "") if room is not None else ""
        if uid:out.append(uid)
    mapping=normalize_placement_bom_room_additions(additions or {})
    puid=str(getattr(placement,"uid","") or "") if placement is not None else ""
    for uid in mapping.get(puid,[]):
        if uid and (not valid or uid in valid) and uid not in out:out.append(uid)
    return out


def placement_matches_bom_room(placement, rooms, additions, room_filter_uid: str) -> bool:
    """Test ét symbol mod et rumfilter uden at ændre dets fysiske placering."""
    selected=str(room_filter_uid or "").strip()
    if not selected:return True
    room_list=list(rooms or [])
    physical=room_for_point(room_list,float(getattr(placement,"x",0.0)),float(getattr(placement,"y",0.0))) if room_list else None
    physical_uid=str(getattr(physical,"uid","") or "") if physical is not None else ""
    if selected=="__outside__":
        # Ekstra BOM-rum er additive: et fysisk objekt uden for rum forbliver
        # derfor også synligt under "Uden rum".
        return not physical_uid
    return selected in placement_bom_room_uids(placement,room_list,additions,include_physical=True)
