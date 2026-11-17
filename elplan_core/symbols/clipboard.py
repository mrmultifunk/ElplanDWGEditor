"""Symbolmærkning og sikker serialisering til udklipsholderen."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict

from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import normalize_associations, normalize_light_outputs
from elplan_core.constants import (
    APPLIANCE_LAYER,
    BOARD_LAYER,
    COMBO_LAYER,
    DATA_LAYER,
    DEFAULT_ANNOTATION_STYLE,
    DEFAULT_SYMBOL_COLOR,
    DETECTOR_LAYER,
    EARTHING_LAYER,
    LIGHTING_LAYER,
    LIGHT_OUTLET_LAYER,
    MISC_LAYER,
    SOCKET_LAYER,
    SOLAR_LAYER,
    SWITCH_LAYER,
    SYMBOL_CLIPBOARD_PREFIX,
    SYMBOLS,
    SYMBOLS_CLIPBOARD_PREFIX,
)
from elplan_core.models import Placement
from elplan_core.pl_box.model import normalize_pl_box_orientation, normalize_pl_outlet_type
from elplan_core.symbols.registry import (
    _split_csv_parts,
    combo_modules,
    combo_socket_kind,
    is_combo_row_symbol,
    is_combo_symbol,
    normalize_combo_label_mode,
)


def symbol_layer(symbol: str) -> str:
    """Returnér det dedikerede CAD-lag for et symbol."""
    if is_combo_symbol(symbol):
        return COMBO_LAYER
    if symbol.startswith("switch_") or symbol.startswith("pushbutton"):
        return SWITCH_LAYER
    if symbol in {"socket_tele", "patch_panel"}:
        return DATA_LAYER
    if symbol == "socket" or symbol.startswith("socket_"):
        return SOCKET_LAYER
    if symbol in {"light_connection","wall_light_outlet"}:
        return LIGHT_OUTLET_LAYER
    if symbol in {"light_fixture", "fluorescent", "fluorescent_fixed", "emergency_light", "spot"}:
        return LIGHTING_LAYER
    if symbol in {"water_heater", "heater", "fan", "ev_charger"}:
        return APPLIANCE_LAYER
    if symbol in {"solar_panel","solar_inverter","solar_battery"}:
        return SOLAR_LAYER
    if symbol in {"distribution_board", "group_board", "meter_board"}:
        return BOARD_LAYER
    if symbol == "main_earthing_connection":
        return EARTHING_LAYER
    if symbol in {"pir", "smoke"}:
        return DETECTOR_LAYER
    return MISC_LAYER


def symbol_annotation_lines(placement: Placement, style: str = DEFAULT_ANNOTATION_STYLE) -> list[str]:
    """Returnér den tekst der vises ved et symbol."""
    detailed = str(style) == "Detaljeret"
    if is_combo_symbol(placement.symbol) and normalize_combo_label_mode(getattr(placement, "label_mode", "Fælles")) == "Opdelt":
        ol=str(getattr(placement,"socket_label","") or "").strip()
        og=str(getattr(placement,"socket_group","") or "").strip()
        def part(prefix,label,group):
            if detailed:
                bits=[]
                if group: bits.append(f"Gruppe: {group}")
                if label: bits.append(label)
                return f"{prefix}: " + " · ".join(bits) if bits else ""
            bits=[x for x in (group,label) if x]
            return f"{prefix}: " + " · ".join(bits) if bits else ""
        if is_combo_row_symbol(placement.symbol):
            mods=combo_modules(placement.symbol)
            sls=_split_csv_parts(getattr(placement,'switch_label',''), len(mods))
            sgs=_split_csv_parts(getattr(placement,'switch_group',''), len(mods))
            rows=[]
            switch_parts=[]
            for idx,(label,group) in enumerate(zip(sls,sgs), start=1):
                prefix=f"Afbryder {idx}" if detailed else f"A{idx}"
                val=part(prefix,label,group)
                if val: switch_parts.append(val)
            if switch_parts:
                if detailed:
                    rows.extend(switch_parts)
                else:
                    rows.append("  ".join(switch_parts))
            socket_kind=combo_socket_kind(placement.symbol)
            if socket_kind != 'none':
                sval=part("Stik",ol,og)
                if sval: rows.append(sval)
            return rows
        sl=str(getattr(placement,"switch_label","") or "").strip()
        sg=str(getattr(placement,"switch_group","") or "").strip()
        return [x for x in (part("Afbryder" if detailed else "A",sl,sg), part("Stik" if detailed else "S",ol,og)) if x]
    label=str(getattr(placement, "label", "") or "").strip()
    group=str(getattr(placement, "group", "") or "").strip()
    if detailed:
        out=[]
        if group: out.append(f"Gruppe: {group}")
        if label: out.append(label)
        return out
    parts=[]
    if group: parts.append(group)
    if label: parts.append(label)
    return [" · ".join(parts)] if parts else []


def symbol_clipboard_payload(placement: Placement) -> str:
    data=asdict(placement); data.pop("uid", None)
    # Tilhørsforhold er logiske relationer og kopieres ikke automatisk til et nyt symbol.
    data["associations"] = []
    data["association_channels"] = []
    data["light_outputs"]=[dict(row,association="") for row in normalize_light_outputs(data.get("light_outputs",[]),[],ensure_one=data.get("symbol")=="light_connection")] if data.get("symbol")=="light_connection" else []
    data["locked"] = False
    data["parent_light_uid"] = ""
    data["parent_light_output_id"] = ""
    data["spot_group_id"] = ""
    data["spot_group_name"] = ""
    data["pl_box_entries"] = {}
    data["pl_box_wiring"] = []
    data["pl_box_splices"] = []
    data["pl_field_record"] = {}
    data["lamp_outlet_type"] = normalize_pl_outlet_type(data.get("lamp_outlet_type","generic"))
    return SYMBOL_CLIPBOARD_PREFIX + json.dumps({"type":"elplan_symbol","version":1,"placement":data},ensure_ascii=False)


def placement_from_clipboard_payload(text: str) -> Placement | None:
    try:
        if not isinstance(text,str) or not text.startswith(SYMBOL_CLIPBOARD_PREFIX): return None
        raw=json.loads(text[len(SYMBOL_CLIPBOARD_PREFIX):])
        if raw.get("type")!="elplan_symbol": return None
        item=dict(raw.get("placement") or {}); item.pop("uid",None)
        if item.get("symbol") not in SYMBOLS.values(): return None
        item.setdefault("line_width",0.25); item.setdefault("color",DEFAULT_SYMBOL_COLOR); item.setdefault("associations",[]); item.setdefault("association_channels",[]); item.setdefault("light_outputs",[]); item.setdefault("locked",False); item.setdefault("parent_light_uid",""); item.setdefault("parent_light_output_id",""); item.setdefault("spot_group_id",""); item.setdefault("spot_group_name",""); item.setdefault("pl_box_entries",{}); item.setdefault("pl_box_wiring",[]); item.setdefault("pl_box_splices",[]); item.setdefault("pl_box_orientation",0); item.setdefault("lamp_outlet_type","generic"); item.setdefault("pl_field_record",{})
        item["pl_field_record"]={}
        item.setdefault("label_mode","Fælles"); item.setdefault("switch_label",""); item.setdefault("switch_group",""); item.setdefault("socket_label",""); item.setdefault("socket_group","")
        item["label_mode"]=normalize_combo_label_mode(item.get("label_mode")); item["color"]=normalize_hex_color(item["color"]); item["associations"]=normalize_associations(item.get("associations",[])); item["pl_box_orientation"]=normalize_pl_box_orientation(item.get("pl_box_orientation",0)); item["lamp_outlet_type"]=normalize_pl_outlet_type(item.get("lamp_outlet_type","generic"))
        return Placement(**item)
    except Exception:
        return None


def symbols_clipboard_payload(placements) -> str:
    """Seriér flere symboler som én kopiér/indsæt-gruppe.

    Relationer til lys/kabler kopieres bevidst ikke. Den geometriske placering
    bevares, så gruppen kan indsættes med samme indbyrdes afstand.
    """
    items=[]
    for placement in placements:
        data=asdict(placement); data.pop("uid",None); data["associations"]=[]; data["association_channels"]=[]; data["light_outputs"]=[dict(row,association="") for row in normalize_light_outputs(data.get("light_outputs",[]),[],ensure_one=data.get("symbol")=="light_connection")] if data.get("symbol")=="light_connection" else []; data["locked"]=False; data["parent_light_uid"]=""; data["parent_light_output_id"]=""; data["pl_box_entries"]={}; data["pl_box_wiring"]=[]; data["pl_box_splices"]=[]; data["pl_field_record"]={}; data["lamp_outlet_type"]=normalize_pl_outlet_type(data.get("lamp_outlet_type","generic"))
        items.append(data)
    return SYMBOLS_CLIPBOARD_PREFIX + json.dumps({"type":"elplan_symbols","version":1,"placements":items},ensure_ascii=False)


def placements_from_clipboard_payload(text: str) -> list[Placement]:
    try:
        if not isinstance(text,str) or not text.startswith(SYMBOLS_CLIPBOARD_PREFIX):return []
        raw=json.loads(text[len(SYMBOLS_CLIPBOARD_PREFIX):])
        if raw.get("type")!="elplan_symbols":return []
        out=[]
        sources=[dict(source or {}) for source in (raw.get("placements") or [])]
        group_counts={}
        for source in sources:
            gid=str(source.get("spot_group_id","") or "")
            if gid: group_counts[gid]=group_counts.get(gid,0)+1
        group_remap={}
        for source in sources:
            item=dict(source or {}); item.pop("uid",None)
            if item.get("symbol") not in SYMBOLS.values():continue
            item.setdefault("line_width",0.25); item.setdefault("color",DEFAULT_SYMBOL_COLOR); item.setdefault("associations",[]); item.setdefault("association_channels",[]); item.setdefault("light_outputs",[]); item.setdefault("locked",False); item.setdefault("parent_light_uid",""); item.setdefault("parent_light_output_id",""); item.setdefault("spot_group_id",""); item.setdefault("spot_group_name",""); item.setdefault("pl_box_entries",{}); item.setdefault("pl_box_wiring",[]); item.setdefault("pl_box_splices",[]); item.setdefault("pl_box_orientation",0); item.setdefault("lamp_outlet_type","generic"); item.setdefault("pl_field_record",{})
            item["pl_box_entries"]={}; item["pl_box_wiring"]=[]; item["pl_box_splices"]=[]; item["pl_field_record"]={}; item["pl_box_orientation"]=normalize_pl_box_orientation(item.get("pl_box_orientation",0)); item["lamp_outlet_type"]=normalize_pl_outlet_type(item.get("lamp_outlet_type","generic")); item["parent_light_uid"]=""; item["parent_light_output_id"]=""; item["color"]=normalize_hex_color(item["color"]); item["associations"]=[]; item["association_channels"]=[]; item["light_outputs"]=[dict(row,association="") for row in normalize_light_outputs(item.get("light_outputs",[]),[],ensure_one=item.get("symbol")=="light_connection")] if item.get("symbol")=="light_connection" else []
            old_gid=str(item.get("spot_group_id","") or "")
            if old_gid and item.get("symbol")=="spot" and group_counts.get(old_gid,0)>=2:
                item["spot_group_id"]=group_remap.setdefault(old_gid,uuid.uuid4().hex)
            else:
                item["spot_group_id"]=""; item["spot_group_name"]=""
            out.append(Placement(**item))
        return out
    except Exception:
        return []
