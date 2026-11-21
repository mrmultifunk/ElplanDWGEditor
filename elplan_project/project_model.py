from __future__ import annotations

import json
import math
import uuid
from copy import deepcopy
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

import core_logic as core
from elplan_shared.storage_utils import atomic_write_text

APP_VERSION = "0.59.85"


def _finite_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} skal være et tal.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} skal være et endeligt tal.")
    return number


def _validate_uid(uid: Any, field_name: str) -> str:
    value = str(uid or "").strip()
    if not value:
        raise ValueError(f"{field_name} mangler et gyldigt id.")
    return value


def _dataclass_kwargs(cls, raw: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(defaults or {})
    data.update(raw or {})
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


def placement_from_raw(raw: dict[str, Any]) -> core.Placement:
    item = _dataclass_kwargs(
        core.Placement,
        raw,
        {
            "line_width": 0.25,
            "color": core.DEFAULT_SYMBOL_COLOR,
            "associations": [],
            "association_channels": [],
            "light_outputs": [],
            "locked": False,
            "mounting_zone": "",
            "mounting_height_mm": None,
            "material_color": "",
            "already_purchased": False,
            "spot_group_id": "",
            "spot_group_name": "",
            "parent_light_uid": "",
            "parent_light_output_id": "",
            "pl_box_entries": {},
            "pl_box_wiring": [],
            "pl_box_splices": [],
            "pl_box_orientation": 0,
            "lamp_outlet_type": "generic",
            "pl_field_record": {},
            "label_mode": "Fælles",
            "switch_label": "",
            "switch_group": "",
            "socket_label": "",
            "socket_group": "",
        },
    )
    item["uid"] = _validate_uid(item.get("uid") or uuid.uuid4().hex, "Symbol-id")
    item["x"] = _finite_float(item.get("x"), "Symbol X")
    item["y"] = _finite_float(item.get("y"), "Symbol Y")
    item["rotation"] = _finite_float(item.get("rotation", 0.0), "Symbolrotation") % 360.0
    item["size"] = _finite_float(item.get("size", 500.0), "Symbolstørrelse")
    item["line_width"] = _finite_float(item.get("line_width", 0.25), "Symbollinjetykkelse")
    if item["size"] <= 0:
        raise ValueError("Symbolstørrelse skal være større end 0.")
    if item["line_width"] <= 0:
        raise ValueError("Symbollinjetykkelse skal være større end 0.")
    item["color"] = core.normalize_hex_color(item.get("color", core.DEFAULT_SYMBOL_COLOR))
    item["mounting_zone"] = core.normalize_mounting_zone(item.get("mounting_zone", ""))
    item["mounting_height_mm"] = core.normalize_mounting_height_mm(item.get("mounting_height_mm"))
    item["material_color"] = core.normalize_material_color(item.get("material_color", ""))
    item["already_purchased"] = core.normalize_already_purchased(item.get("already_purchased", False))
    role=core.association_role(str(item.get("symbol", "")))
    legacy_associations=core.normalize_associations(item.get("associations",[]))
    if str(item.get("symbol", ""))=="light_connection":
        item["light_outputs"]=core.normalize_light_outputs(
            item.get("light_outputs",[]),legacy_associations
        )
        item["associations"]=core.normalize_light_associations([
            item["light_outputs"][0].get("association","")
        ])
    else:
        item["light_outputs"]=[]
        item["associations"] = (
            core.normalize_light_associations(legacy_associations)
            if role=="light" else legacy_associations
        )
    if role == "switch":
        item["association_channels"] = core.normalize_association_channels(
            str(item.get("symbol", "")),
            item.get("association_channels", []),
            item.get("associations", []),
        )
        item["associations"] = core.normalize_associations([x for x in item["association_channels"] if x])
    else:
        item["association_channels"] = []
    item["label_mode"] = core.normalize_combo_label_mode(item.get("label_mode", "Fælles"))
    item["pl_box_entries"] = core.normalize_pl_box_entries(item.get("pl_box_entries", {}))
    item["pl_box_wiring"] = core.normalize_pl_box_wiring(item.get("pl_box_wiring", []))
    item["pl_box_splices"] = core.normalize_pl_box_splices(item.get("pl_box_splices", []))
    item["pl_box_orientation"] = core.normalize_pl_box_orientation(item.get("pl_box_orientation", 0))
    item["lamp_outlet_type"] = core.normalize_pl_outlet_type(item.get("lamp_outlet_type", "generic"))
    item["pl_field_record"] = core.normalize_pl_field_record(item.get("pl_field_record", {}))
    if str(item.get("symbol", "")) != "light_connection":
        item["pl_box_entries"] = {}
        item["pl_box_wiring"] = []
        item["pl_box_splices"] = []
        item["pl_box_orientation"] = 0
        item["lamp_outlet_type"] = "generic"
        item["pl_field_record"] = {}
    return core.Placement(**item)


def cable_from_raw(raw: dict[str, Any]) -> core.CablePlacement:
    item = _dataclass_kwargs(
        core.CablePlacement,
        raw,
        {
            "label": "",
            "color": core.DEFAULT_CABLE_COLOR,
            "line_style": core.DEFAULT_CABLE_LINE_STYLE,
            "cable_category": core.DEFAULT_CABLE_CATEGORY,
            "cable_spec": "",
            "cable_id": "",
            "circuit_id": "",
            "route_chain_uid": "",
            "auto_label": False,
            "start_symbol_uid": "",
            "end_symbol_uid": "",
            "start_symbol_port": 0,
            "end_symbol_port": 0,
            "orthogonal": False,
            "route_section_modes": [],
            "spec_section_overrides": [],
            "symbol_connections": [],
        },
    )
    points = []
    for index, point in enumerate(item.get("points", []) or [], start=1):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(f"Kabelpunkt {index} er ugyldigt.")
        points.append((_finite_float(point[0], f"Kabelpunkt {index} X"), _finite_float(point[1], f"Kabelpunkt {index} Y")))
    item["points"] = points
    item["line_width"] = _finite_float(item.get("line_width", 0.35), "Kabellinjetykkelse")
    if item["line_width"] <= 0:
        raise ValueError("Kabellinjetykkelse skal være større end 0.")
    item["color"] = core.normalize_hex_color(item.get("color", core.DEFAULT_CABLE_COLOR), core.DEFAULT_CABLE_COLOR)
    item["line_style"] = core.normalize_cable_line_style(item.get("line_style", core.DEFAULT_CABLE_LINE_STYLE))
    item["cable_category"] = core.normalize_cable_category_id(item.get("cable_category", core.DEFAULT_CABLE_CATEGORY))
    try:
        item["start_symbol_port"] = max(0, int(item.get("start_symbol_port", 0)))
        item["end_symbol_port"] = max(0, int(item.get("end_symbol_port", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Kabelport skal være et heltal.") from exc
    # Legacy 0.43-0.54 projects may contain several symbol connections on one
    # route. They are first normalised here and split into physical cables by load().
    connections=core.normalize_cable_symbol_connections(item.get("symbol_connections",[]),len(points))
    if not connections and points:
        if str(item.get("start_symbol_uid","") or "").strip():
            connections.append({"point_index":0,"symbol_uid":str(item["start_symbol_uid"]),"symbol_port":item["start_symbol_port"]})
        if str(item.get("end_symbol_uid","") or "").strip():
            connections.append({"point_index":len(points)-1,"symbol_uid":str(item["end_symbol_uid"]),"symbol_port":item["end_symbol_port"]})
    item["symbol_connections"]=core.normalize_cable_symbol_connections(connections,len(points))
    item["route_section_modes"]=core.normalize_cable_route_section_modes(item.get("route_section_modes",[]))
    item["spec_section_overrides"]=core.normalize_cable_spec_section_overrides(
        item.get("spec_section_overrides",[]),item.get("cable_spec","")
    )
    item["uid"] = _validate_uid(item.get("uid") or uuid.uuid4().hex, "Kabel-id")
    cable=core.CablePlacement(**item)
    core.set_cable_symbol_connections(cable,item["symbol_connections"])
    return cable


def _remap_legacy_pl_ref(record: dict, leg_map: dict) -> dict:
    """Map one pre-0.55 PL cable-leg reference onto a physical cable endpoint."""
    if not isinstance(record, dict):
        return dict(record or {})
    uid=str(record.get("cable_uid","") or "")
    try: idx=max(0,int(record.get("point_index",0) or 0))
    except (TypeError,ValueError): idx=0
    leg=str(record.get("leg","") or "").strip().lower()
    target=leg_map.get((uid,idx,leg))
    if target is None:
        # Older PL data may contain a stale point index after route edits. Use a
        # loose uid+side match only when it is unambiguous.
        candidates=[value for (old_uid,_old_idx,old_leg),value in leg_map.items() if old_uid==uid and old_leg==leg]
        if len(candidates)==1:
            target=candidates[0]
    if target is None:
        return dict(record)
    out=dict(record); out.update(target); return out


def _remap_legacy_pl_box_data(placement: core.Placement, leg_map: dict) -> None:
    if str(getattr(placement,"symbol","") or "") != "light_connection" or not leg_map:
        return
    entries={}
    for port,row in core.normalize_pl_box_entries(getattr(placement,"pl_box_entries",{})).items():
        entries[port]=_remap_legacy_pl_ref(row,leg_map)
    placement.pl_box_entries=core.normalize_pl_box_entries(entries)

    wiring=[]
    for row in core.normalize_pl_box_wiring(getattr(placement,"pl_box_wiring",[])):
        wiring.append(_remap_legacy_pl_ref(row,leg_map))
    placement.pl_box_wiring=core.normalize_pl_box_wiring(wiring)

    splices=[]
    for splice in core.normalize_pl_box_splices(getattr(placement,"pl_box_splices",[])):
        item=dict(splice)
        item["members"]=[_remap_legacy_pl_ref(member,leg_map) for member in splice.get("members",[]) or []]
        splices.append(item)
    placement.pl_box_splices=core.normalize_pl_box_splices(splices)



def room_from_raw(raw: dict[str, Any]) -> core.RoomPlacement:
    item = _dataclass_kwargs(
        core.RoomPlacement,
        raw,
        {"name":"Rum","code":"","label_x":0.0,"label_y":0.0,"color":"#0f766e"},
    )
    pts=[]
    for index, point in enumerate(item.get("points",[]) or [], start=1):
        if not isinstance(point,(list,tuple)) or len(point)<2:
            raise ValueError(f"Rumpunkt {index} er ugyldigt.")
        pts.append((_finite_float(point[0],f"Rumpunkt {index} X"),_finite_float(point[1],f"Rumpunkt {index} Y")))
    if len(pts)<3:
        raise ValueError("Et rum skal have mindst tre punkter.")
    item["points"]=pts
    item["uid"]=_validate_uid(item.get("uid") or uuid.uuid4().hex,"Rum-id")
    item["name"]=str(item.get("name") or "Rum").strip() or "Rum"
    item["code"]=str(item.get("code") or "").strip()
    cx,cy=core.room_polygon_centroid(pts)
    try:item["label_x"]=_finite_float(item.get("label_x",cx),"Rumtekst X")
    except ValueError:item["label_x"]=cx
    try:item["label_y"]=_finite_float(item.get("label_y",cy),"Rumtekst Y")
    except ValueError:item["label_y"]=cy
    # Legacy/handwritten room records commonly omit label coordinates. 0/0 is
    # not treated as a sentinel when the room actually surrounds the origin.
    if "label_x" not in raw or "label_y" not in raw:
        item["label_x"],item["label_y"]=cx,cy
    item["color"]=core.normalize_hex_color(item.get("color","#0f766e"),"#0f766e")
    return core.RoomPlacement(**item)

def text_from_raw(raw: dict[str, Any]) -> core.TextPlacement:
    item = _dataclass_kwargs(
        core.TextPlacement,
        raw,
        {"height": 250.0, "rotation": 0.0, "color": "#202020"},
    )
    item["uid"] = _validate_uid(item.get("uid") or uuid.uuid4().hex, "Tekst-id")
    item["x"] = _finite_float(item.get("x"), "Tekst X")
    item["y"] = _finite_float(item.get("y"), "Tekst Y")
    item["height"] = _finite_float(item.get("height", 250.0), "Teksthøjde")
    item["rotation"] = _finite_float(item.get("rotation", 0.0), "Tekstrotation") % 360.0
    if item["height"] <= 0:
        raise ValueError("Teksthøjde skal være større end 0.")
    item["color"] = core.normalize_hex_color(item.get("color", "#202020"))
    return core.TextPlacement(**item)


class ProjectDocument:
    """Small Qt-side project model that preserves the 0.24.x JSON format."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.source_file: str = ""
        self.raw: dict[str, Any] = {}
        self.placements: list[core.Placement] = []
        self.cables: list[core.CablePlacement] = []
        self.texts: list[core.TextPlacement] = []
        self.rooms: list[core.RoomPlacement] = []
        self.layer_visibility: dict[str, bool] = {}
        self.dirty = False
        self._saved_data: dict[str, Any] | None = None

    @classmethod
    def load(cls, path: str | Path) -> "ProjectDocument":
        obj = cls()
        obj.path = Path(path)
        data = json.loads(obj.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Projektfilen indeholder ikke et gyldigt objekt.")
        obj.raw = data
        obj.source_file = str(data.get("source_file", "") or "")
        categories = core.normalize_cable_category_records(data.get("cable_categories", []))
        # 0.50.19 introduced Mellemkabel/Tændkabel. Kun projekter fra før
        # 0.50.19 får dem automatisk, så en bruger som senere sletter en af
        # kategorierne ikke får den genoprettet ved hver programopgradering.
        def _version_tuple(value: str) -> tuple[int, int, int]:
            parts=[]
            for token in str(value or "").split(".")[:3]:
                try: parts.append(int(token))
                except Exception: parts.append(0)
            while len(parts)<3: parts.append(0)
            return tuple(parts[:3])
        if _version_tuple(data.get("version", "")) < (0, 50, 19):
            existing_ids = {str(row.get("id", "")) for row in categories}
            for default in core.DEFAULT_CABLE_CATEGORIES:
                if default.get("id") in {"interconnect", "switch_cable"} and default.get("id") not in existing_ids:
                    categories.append(dict(default))
                    existing_ids.add(str(default.get("id")))
        # 0.59.57 gør Spots til en egentlig standard-kabelkategori. Kategorien
        # fandtes allerede i standardlisten i de seneste builds, men ældre
        # projekter gemmer deres egen kategoriliste og fik den derfor ikke med.
        # Migrér den én gang for projekter fra før 0.59.57. Projekter gemt i
        # 0.59.57+ må fortsat kunne slette kategorien manuelt uden at den
        # genoprettes ved hver åbning.
        if _version_tuple(data.get("version", "")) < (0, 59, 40):
            existing_ids = {str(row.get("id", "")) for row in categories}
            if "spots" not in existing_ids:
                default = next((row for row in core.DEFAULT_CABLE_CATEGORIES if row.get("id") == "spots"), None)
                if default is not None:
                    categories.append(dict(default))
        # 0.59.74 tilføjer separate standardkategorier til jord/udligning og
        # stik-/hovedledninger. De indsættes kun én gang i ældre projekter, så
        # en bruger efterfølgende fortsat kan slette eller tilpasse dem.
        if _version_tuple(data.get("version", "")) < (0, 59, 74):
            existing_ids = {str(row.get("id", "")) for row in categories}
            for default in core.DEFAULT_CABLE_CATEGORIES:
                category_id = str(default.get("id", ""))
                if category_id in {"earthing_bonding", "service_main"} and category_id not in existing_ids:
                    categories.append(dict(default))
                    existing_ids.add(category_id)
        obj.raw["cable_categories"] = core.normalize_cable_category_records(categories)
        # Valider hele projektet før brugerdefinerede symboler registreres globalt.
        # Ellers kunne en korrupt/afvist projektfil efterlade symbolpaletten ændret,
        # selv om det aktive projekt aldrig blev åbnet.
        custom_records = data.get("custom_symbols", []) or []
        custom_codes_from_placements: set[str] = set()
        placement_uids: set[str] = set()
        for row_no, raw in enumerate(data.get("placements", []) or [], start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Symbolpost {row_no} er ugyldig.")
            code = str(raw.get("symbol", "") or "")
            if core.is_custom_combo_symbol(code):
                custom_codes_from_placements.add(code)
            placement = placement_from_raw(raw)
            if placement.uid in placement_uids:
                raise ValueError(f"Projektet indeholder dubleret symbol-id: {placement.uid}")
            placement_uids.add(placement.uid)
            obj.placements.append(placement)

        obj.cables = []
        cable_uids: set[str] = set()
        legacy_leg_map: dict = {}
        split_uid_map: dict[str,list[str]] = {}
        split_mixed_spec: dict[str,bool] = {}
        cable_model_migrated=False
        raw_cable_rows=[row for row in (data.get("cables",[]) or []) if isinstance(row,dict)]
        reserved_original_ids={str(row.get("cable_id","") or "").strip() for row in raw_cable_rows if str(row.get("cable_id","") or "").strip()}
        generated_ids:set[str]=set()

        def _migration_ids(base_id: str, count: int) -> list[str]:
            count=max(0,int(count or 0)); base=str(base_id or "").strip()
            if count<=0:return []
            out=[base] if base else [""]
            generated_ids.update(x for x in out if x)
            import re as _re
            match=_re.match(r"^(.*?)(\d+)$",base) if base else None
            prefix=match.group(1) if match else (base + "-" if base else "K")
            number=int(match.group(2)) if match else 1
            width=len(match.group(2)) if match else 2
            suffix=2
            while len(out)<count:
                if match:
                    number+=1; candidate=f"{prefix}{number:0{width}d}"
                else:
                    candidate=f"{prefix}{suffix}"; suffix+=1
                if candidate in reserved_original_ids or candidate in generated_ids:
                    continue
                out.append(candidate); generated_ids.add(candidate)
            return out

        for row_no, raw in enumerate(data.get("cables", []) or [], start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Kabelpost {row_no} er ugyldig.")
            cable = cable_from_raw(raw)
            category=core.cable_category_record(obj.raw["cable_categories"],getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))
            cable.cable_category=str(category["id"])
            old_uid=str(cable.uid)
            had_section_metadata=bool(core.normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[]))) or bool(
                core.normalize_cable_spec_section_overrides(getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec",""))
            )
            split_mixed_spec[old_uid]=bool(core.normalize_cable_spec_section_overrides(
                getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
            ))
            segments,local_leg_map=core.split_cable_into_physical_segments(cable,return_legacy_map=True)
            if len(segments)>1:
                for segment,new_id in zip(segments,_migration_ids(getattr(cable,"cable_id",""),len(segments))):
                    segment.cable_id=new_id
            elif str(getattr(cable,"cable_id","") or "").strip():
                generated_ids.add(str(getattr(cable,"cable_id","") or "").strip())
            if len(segments)>1 or had_section_metadata:
                cable_model_migrated=True
                legacy_leg_map.update(local_leg_map)
            split_uid_map[old_uid]=[str(seg.uid) for seg in segments]
            for segment in segments:
                # Farve/linjetype gemmes fortsat på kablet, så gamle projekter og
                # roundtrip aldrig ændrer udseende ved blot at blive åbnet.
                if segment.uid in cable_uids:
                    raise ValueError(f"Projektet indeholder dubleret kabel-id: {segment.uid}")
                cable_uids.add(segment.uid)
                obj.cables.append(segment)

        if legacy_leg_map:
            for placement in obj.placements:
                _remap_legacy_pl_box_data(placement,legacy_leg_map)

        # Infer missing group/circuit once per drawn/migrated string. This keeps
        # all physical segments in the same logical circuit instead of guessing
        # potentially different values on neighbouring segments.
        placement_by_uid={str(p.uid):p for p in obj.placements}
        for placement in obj.placements:
            parent_uid=str(getattr(placement,"parent_light_uid","") or "")
            if placement.symbol!="spot" or not parent_uid:continue
            parent=placement_by_uid.get(parent_uid)
            if parent is None or parent.symbol!="light_connection":continue
            output=core.light_output_by_id(parent,getattr(placement,"parent_light_output_id","") or "")
            placement.parent_light_output_id=str(output.get("id","") or "")
            placement.associations=core.normalize_light_associations([output.get("association","")])
        chains:dict[str,list[core.CablePlacement]]={}
        for cable in obj.cables:
            key=str(getattr(cable,"route_chain_uid","") or getattr(cable,"uid","") or "")
            chains.setdefault(key,[]).append(cable)
        for chain in chains.values():
            explicit=[]
            for cable in chain:
                value=str(getattr(cable,"circuit_id","") or "").strip()
                if value and value not in explicit:explicit.append(value)
            inferred=[]
            for cable in chain:
                for conn in core.cable_symbol_connections(cable):
                    placement=placement_by_uid.get(str(conn.get("symbol_uid","") or ""))
                    group=str(getattr(placement,"group","") or "").strip() if placement is not None else ""
                    if group and group not in inferred:inferred.append(group)
            common=(explicit[0] if len(explicit)==1 else (inferred[0] if not explicit and len(inferred)==1 else ""))
            if common:
                for cable in chain:
                    if not str(getattr(cable,"circuit_id","") or "").strip():cable.circuit_id=common

        room_uids: set[str] = set()
        obj.rooms = []
        for row_no, raw in enumerate(data.get("rooms", []) or [], start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Rumpost {row_no} er ugyldig.")
            room=room_from_raw(raw)
            if room.uid in room_uids:
                raise ValueError(f"Projektet indeholder dubleret rum-id: {room.uid}")
            room_uids.add(room.uid); obj.rooms.append(room)

        additions=core.normalize_placement_bom_room_additions(data.get("placement_bom_room_additions",{}))
        valid_placement_uids={str(p.uid) for p in obj.placements}
        valid_room_uids={str(r.uid) for r in obj.rooms}
        obj.raw["placement_bom_room_additions"]={
            uid:[room_uid for room_uid in room_uids if room_uid in valid_room_uids]
            for uid,room_uids in additions.items() if uid in valid_placement_uids and any(room_uid in valid_room_uids for room_uid in room_uids)
        }

        text_uids: set[str] = set()
        obj.texts = []
        for row_no, raw in enumerate(data.get("texts", []) or [], start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Tekstpost {row_no} er ugyldig.")
            text = text_from_raw(raw)
            if text.uid in text_uids:
                raise ValueError(f"Projektet indeholder dubleret tekst-id: {text.uid}")
            text_uids.add(text.uid)
            obj.texts.append(text)
        vis = data.get("layer_visibility", {})
        obj.layer_visibility = dict(vis) if isinstance(vis, dict) else {}
        # 0.45.0: artikelbasen og globale styklister er kernedata og gemmes ikke
        # længere i nye projektfiler. Ældre indlejrede data bevares midlertidigt
        # i raw, så MainWindow kan migrere dem sikkert til brugerens kernedata.
        obj.raw["article_catalog"] = core.normalize_article_catalog(data.get("article_catalog", []))
        obj.raw["bom_assemblies"] = core.normalize_bom_assemblies(data.get("bom_assemblies", []))
        # Ældre typebaserede felter bevares kun som legacy-data. Fra 0.42.3
        # bruger BOM eksplicitte instanstilknytninger, så én forekomst aldrig
        # automatisk tildeler artikler til alle andre af samme type.
        obj.raw["symbol_articles"] = core.normalize_symbol_article_bindings(data.get("symbol_articles", {}))
        obj.raw["symbol_assemblies"] = core.normalize_symbol_assembly_bindings(data.get("symbol_assemblies", {}))
        obj.raw["cable_articles"] = core.normalize_cable_article_bindings(data.get("cable_articles", {}))
        obj.raw["placement_articles"] = core.normalize_symbol_article_bindings(data.get("placement_articles", {}))
        obj.raw["placement_assemblies"] = core.normalize_symbol_assembly_bindings(data.get("placement_assemblies", {}))
        original_cable_bindings=core.normalize_cable_article_bindings(data.get("cable_instance_articles", {}))
        migrated_cable_bindings={}
        for old_uid,article_no in original_cable_bindings.items():
            new_uids=split_uid_map.get(old_uid,[old_uid])
            # A legacy mixed-spec cable deliberately ignored its one article in
            # BOM. Do not guess when converting it into real cables; those
            # physical segments must be assigned explicitly afterwards.
            if len(new_uids)>1 and split_mixed_spec.get(old_uid,False):
                continue
            for new_uid in new_uids:
                migrated_cable_bindings[new_uid]=article_no
        obj.raw["cable_instance_articles"] = core.normalize_cable_article_bindings(migrated_cable_bindings)

        # Først nu er projektet valideret. Registrering påvirker globale symboltabeller
        # og må derfor ikke ske før alle poster er godkendt.
        core.register_custom_symbol_records(custom_records)
        for code in sorted(custom_codes_from_placements):
            core.register_custom_symbol(code, None)

        # Multi-stop cables from <=0.54 are upgraded in memory to one physical
        # cable per installation-point span. Mark the document dirty so the new
        # model is persisted explicitly on the next save instead of silently
        # depending on migration every time it is opened.
        obj.dirty = bool(cable_model_migrated)
        obj.raw["version"]=APP_VERSION
        obj._saved_data = deepcopy(data if cable_model_migrated else obj.to_dict())
        return obj

    @classmethod
    def from_cad(cls, source_file: str | Path) -> "ProjectDocument":
        obj = cls()
        obj.source_file = str(source_file)
        obj.raw = {"version": APP_VERSION, "source_file": obj.source_file, "cable_categories": core.default_cable_category_records()}
        return obj

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.raw)
        data["version"] = APP_VERSION
        data["source_file"] = self.source_file
        # 0.45.0: custom-symbolbiblioteket er kernedata. Projektet gemmer kun
        # symbolkoden i placeringerne.
        data.pop("custom_symbols", None)
        placement_rows=[]
        for placement in self.placements:
            row=asdict(placement)
            role=core.association_role(placement.symbol)
            if placement.symbol=="light_connection":
                outputs=core.normalize_light_outputs(
                    getattr(placement,"light_outputs",[]),getattr(placement,"associations",[])
                )
                row["light_outputs"]=outputs
                row["associations"]=core.normalize_light_associations([outputs[0].get("association","")])
                row["association_channels"]=[]
            elif role=="light":
                row["associations"]=core.normalize_light_associations(getattr(placement,"associations",[]))
                row["association_channels"]=[]
                row["light_outputs"]=[]
            elif role=="switch":
                channels=core.association_channel_letters(placement)
                row["association_channels"]=channels
                row["associations"]=core.normalize_associations([x for x in channels if x])
                row["light_outputs"]=[]
            else:
                row["light_outputs"]=[]
            if placement.symbol == "light_connection":
                legs=core.cable_legs_at_symbol(self.cables,placement.uid)
                row["pl_box_entries"]=core.reconcile_pl_box_entries(getattr(placement,"pl_box_entries",{}),legs)
                existing_wiring=getattr(placement,"pl_box_wiring",[])
                row["pl_box_wiring"]=core.reconcile_pl_box_wiring(existing_wiring,legs) if existing_wiring else []
                row["pl_box_splices"]=core.reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),row["pl_box_wiring"],legs)
                row["pl_box_orientation"]=core.normalize_pl_box_orientation(getattr(placement,"pl_box_orientation",0))
                row["pl_field_record"]=core.normalize_pl_field_record(getattr(placement,"pl_field_record",{}))
            else:
                row["pl_box_entries"]={}
                row["pl_box_wiring"]=[]
                row["pl_box_splices"]=[]
                row["pl_box_orientation"]=0
                row["pl_field_record"]={}
            placement_rows.append(row)
        data["placements"] = placement_rows
        data["cable_categories"] = core.normalize_cable_category_records(data.get("cable_categories", []))
        invalid=[str(getattr(c,"cable_id","") or getattr(c,"uid","") or "Kabel") for c in self.cables if not core.cable_is_physical_segment(c)]
        if invalid:
            raise ValueError(
                "Projektet indeholder kabelobjekter med flere fysiske tilslutningssteder: "
                + ", ".join(invalid[:5])
                + (" …" if len(invalid)>5 else "")
                + ". 0.55.x kræver ét fysisk kabel pr. objekt."
            )
        data["cables"] = [asdict(x) for x in self.cables]
        data["texts"] = [asdict(x) for x in self.texts]
        data["rooms"] = [asdict(x) for x in self.rooms]
        data["layer_visibility"] = dict(self.layer_visibility)
        # Globale biblioteker må ikke snige sig tilbage ind i projektformatet.
        data.pop("article_catalog", None)
        data.pop("bom_assemblies", None)
        data["symbol_articles"] = core.normalize_symbol_article_bindings(data.get("symbol_articles", {}))
        data["symbol_assemblies"] = core.normalize_symbol_assembly_bindings(data.get("symbol_assemblies", {}))
        data["cable_articles"] = core.normalize_cable_article_bindings(data.get("cable_articles", {}))
        data["placement_articles"] = core.normalize_symbol_article_bindings(data.get("placement_articles", {}))
        data["placement_assemblies"] = core.normalize_symbol_assembly_bindings(data.get("placement_assemblies", {}))
        data["cable_instance_articles"] = core.normalize_cable_article_bindings(data.get("cable_instance_articles", {}))
        valid_placement_uids={str(p.uid) for p in self.placements}
        valid_room_uids={str(r.uid) for r in self.rooms}
        additions=core.normalize_placement_bom_room_additions(data.get("placement_bom_room_additions",{}))
        data["placement_bom_room_additions"]={
            uid:[room_uid for room_uid in room_uids if room_uid in valid_room_uids]
            for uid,room_uids in additions.items() if uid in valid_placement_uids and any(room_uid in valid_room_uids for room_uid in room_uids)
        }
        return data

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("Der er ikke valgt en projektfil.")
        data = self.to_dict()
        payload = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
        atomic_write_text(target, payload)
        self.path = target
        self.raw = data
        self._saved_data = deepcopy(data)
        self.dirty = False
        return target

    def matches_saved_state(self) -> bool:
        """True when the current serialisable document matches the last load/save."""
        return self._saved_data is not None and self.to_dict() == self._saved_data
