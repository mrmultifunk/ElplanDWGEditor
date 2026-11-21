from __future__ import annotations

"""GUI-uafhængig domæne-, CAD-, artikel- og eksportlogik.

Udskilt fra det historiske Tkinter-program, så Qt-applikationen ikke behøver
at importere eller parse den gamle GUI ved opstart. ``legacy_core.py`` beholdes
midlertidigt som kompatibilitetslag for ældre tests/værktøjer.
"""

import json
import math
import os
import re
from datetime import datetime
from functools import lru_cache
from collections import defaultdict
import uuid
from dataclasses import asdict
from pathlib import Path

from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import (
    _association_index_to_text,
    _association_text_to_index,
    association_capacity,
    association_channel_base,
    association_channel_bases,
    association_channel_caption,
    association_channel_letters,
    association_channel_module,
    association_channel_prefers_existing,
    association_channel_records,
    association_channel_source_mark,
    association_channel_stable_id,
    association_display,
    association_module_layout,
    association_role,
    association_world_point,
    light_can_share_switch_group,
    light_output_associations,
    light_output_by_id,
    light_output_records,
    next_association_letter,
    normalize_association_channels,
    normalize_associations,
    normalize_light_associations,
    normalize_light_outputs,
    set_association_channel,
    set_light_output_association,
    set_lights_shared_association,
    sync_association_channels,
    sync_light_outputs,
)
from elplan_core.cables.categories import (
    _cable_category_id,
    cable_category_layer_label,
    cable_category_layer_name,
    cable_category_record,
    cable_category_style,
    cable_effective_layer,
    cable_visible_in_layers,
    default_cable_category_records,
    normalize_cable_category_id,
    normalize_cable_category_records,
    normalize_cable_line_style,
)
from elplan_core.cables.connections import (
    cable_connection_at,
    cable_is_physical_segment,
    cable_symbol_connections,
    normalize_cable_symbol_connections,
    replace_cable_connection,
    set_cable_symbol_connections,
    shift_cable_connection_indices,
)
from elplan_core.cables.geometry import (
    _axis_aligned,
    _clean_polyline_points,
    cable_label_point,
    cable_route_points_to,
    constrain_polyline_target_to_locked_neighbors,
    convert_cable_route_mode_geometry,
    move_polyline_endpoint,
    move_polyline_endpoint_flexible,
    move_polyline_endpoint_stable,
    move_polyline_vertex,
    move_polyline_vertex_flexible,
    move_polyline_vertex_stable,
    polyline_label_point,
    polyline_length,
    rotate_point,
)
from elplan_core.cables.lengths import (
    cable_estimated_length_metres,
    cable_length_by_spec_metres,
    cable_length_metres,
    cable_route_chain_estimated_length_metres,
    cable_route_chain_key,
    cable_route_chain_length_metres,
    cable_route_chain_members,
    cable_route_length,
)
from elplan_core.cables.sections import (
    _cable_route_section_key,
    _cable_spec_section_key,
    attach_symbol_to_existing_cable,
    cable_connection_sections,
    cable_effective_specs,
    cable_route_mode_for_point_index,
    cable_route_section_at_segment,
    cable_route_section_mode,
    cable_section_spec_labels,
    cable_spec_for_leg,
    cable_spec_for_section,
    cable_spec_section_at_segment,
    convert_cable_route_section_geometry,
    nearest_cable_segment,
    normalize_cable_route_section_modes,
    normalize_cable_spec_section_overrides,
    set_cable_route_section_mode,
    set_cable_spec_for_section,
    split_cable_into_physical_segments,
)
from elplan_core.constants import *  # noqa: F403 - kompatibilitetsfacade
from elplan_core.models import (
    CADPrimitive,
    CablePlacement,
    Placement,
    RoomPlacement,
    TextPlacement,
)
from elplan_core.platform.oda import detect_oda_exec_path, set_oda_exec_path
from elplan_core.pl_box.model import (
    PL_BOX_ENTRY_COUNT,
    PL_BOX_LEG_CAPTIONS,
    PL_BOX_ORIENTATIONS,
    PL_OUTLET_TYPES,
    PL_PASSTHROUGH_ROLES,
    _normalize_bool,
    auto_assign_pl_box_entries,
    normalize_pl_box_entries,
    normalize_pl_box_orientation,
    normalize_pl_box_splices,
    normalize_pl_field_record,
    normalize_pl_outlet_type,
    normalize_pl_passthrough_role,
    normalize_pl_splice_position,
    pl_box_conductor_key,
    pl_box_conductor_ref,
    pl_box_leg_key,
    pl_box_port_layout,
    pl_box_status,
    pl_box_unplaced_legs,
    pl_field_cable_spec_key,
    pl_field_entry_state,
    pl_field_suggested_leg,
    pl_outlet_profile,
    pl_passthrough_function,
    pl_passthrough_function_parts,
    pl_splice_member_keys,
    reconcile_pl_box_entries,
)
from elplan_core.pl_box.wiring import (
    PL_CONDUCTOR_VISUALS,
    SWITCH_CONDUCTOR_PREFERRED_ORDER,
    SWITCH_CONDUCTOR_TYPICAL_SUPPLY_IDS,
    assign_pl_conductor_function,
    cable_conductor_external_allocations,
    cable_conductor_preset,
    cable_legs_at_symbol,
    cable_neighbor_connection,
    cable_pl_display,
    cable_switch_conductor_assignment_advice,
    cable_switch_conductor_usage,
    normalize_pl_box_wiring,
    pl_box_conductors,
    pl_box_wiring_status,
    pl_expected_switch_connections,
    pl_switch_requirement_status,
    pl_wiring_function_caption,
    pl_wiring_function_options,
    pl_wiring_lamp_terminal,
    pl_wiring_requirement_summary,
    pl_wiring_suggestions,
    placement_identification_caption,
    reconcile_pl_box_wiring,
)
from elplan_core.pl_box.wago import (
    PL_WAGO_ARTICLE_PORTS,
    pl_montage_status,
    pl_outlet_capacity_issues,
    pl_outlet_terminal_capacity,
    pl_recommended_wago_article,
    pl_terminal_occupancy,
    pl_wago_article_capacity,
    pl_wago_required_ports,
    pl_wiring_workflow_issues,
    reconcile_pl_box_splices,
)
from elplan_core.export.pl_report import (
    _draw_pl_report_box,
    _pdf_fit_text,
    _pdf_wrap_lines,
    export_pl_box_report_pdf,
    pl_report_wiring_rows,
)
from elplan_core.rooms import (
    _segment_edge_intersection_t,
    cable_length_by_spec_room_metres,
    cable_light_endpoint_marking,
    cable_room_length_metres,
    cable_room_marking,
    cable_rooms,
    polyline_room_lengths,
    room_contains_point,
    room_display_text,
    room_for_point,
    room_output_label,
    room_polygon_centroid,
    rooms_along_polyline,
)
from elplan_core.settings import (
    _recovery_file,
    _settings_file,
    load_app_settings,
    normalize_appearance_mode,
    normalize_cable_visual_settings,
    normalize_dark_canvas,
    normalize_recent_project_paths,
    save_app_settings,
)
from elplan_core.symbols.clipboard import (
    placement_from_clipboard_payload,
    placements_from_clipboard_payload,
    symbol_annotation_lines,
    symbol_clipboard_payload,
    symbol_layer,
    symbols_clipboard_payload,
)
from elplan_core.symbols.geometry import (
    EXTENDED_SOCKET_MOUNT_FACTOR,
    SOCKET_3FN_BODY_OFFSET_FACTOR,
    SOCKET_STEM_FACTOR,
    _angular_distance_deg,
    _is_wall_device,
    placement_connection_points,
    placement_connection_ports,
    placement_mating_sites,
    placement_mount_points,
    symbol_connection_points,
    symbol_local_bbox,
    symbol_mating_sites,
    symbol_mount_points,
    symbol_primitives,
    wall_device_rotation_for_wall,
    wall_device_snap_origins,
)
from elplan_core.symbols.registry import (
    COMBO_LABEL_MODES,
    COMBO_ROW_PARTS,
    COMBO_SYMBOLS,
    CUSTOM_SYMBOL_NAMES,
    _split_csv_parts,
    _unique_custom_name,
    combo_modules,
    combo_socket_kind,
    combo_switch_symbol,
    custom_combo_auto_name,
    custom_symbol_records,
    is_combo_row_symbol,
    is_combo_symbol,
    is_custom_combo_symbol,
    make_custom_combo_code,
    normalize_combo_label_mode,
    normalize_combo_template_records,
    parse_custom_combo_symbol,
    register_custom_symbol,
    register_custom_symbol_records,
    symbol_display_name,
)

import article_intelligence
from annotation_layout import choose_label_origin, expand_rect

import ezdxf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from ezdxf import bbox, disassemble, path as ezpath
from ezdxf.addons import odafc











def output_equivalent_view_scale(page_scale: float) -> float:
    """Returnér PDF-sidens skala som ca. Qt-skærmpixels pr. CAD-enhed."""
    try:
        return max(0.0, float(page_scale)) * OUTPUT_SCREEN_DPI / 72.0
    except Exception:
        return 0.0

def output_free_text_font_size(height: float) -> float:
    """Samme fritekststørrelse (pt) som FreeTextItem i Qt-editoren."""
    try:
        return max(1.0, min(96.0, float(height) * 0.065))
    except Exception:
        return 6.5

def output_cad_text_font_size(height: float, page_scale: float) -> float:
    """CAD-tekst: match Qt's 0.65-faktor uden den gamle 3-24 pt clamp."""
    try:
        return max(0.6, min(144.0, abs(float(height)) * float(page_scale) * 0.65))
    except Exception:
        return 6.0

def output_symbol_text_font_size(height: float, page_scale: float) -> float:
    """Intern symboltekst (fx 3N): samme 0.60-faktor som Qt-symbolrenderer."""
    try:
        return max(0.6, min(144.0, abs(float(height)) * float(page_scale) * 0.60))
    except Exception:
        return 6.0

def annotation_visual_profile(mode: str, view_scale: float, selected: bool = False) -> dict:
    """Fælles størrelsesprofil for editor og PDF-output. Alle fonttal er pt."""
    mode = str(mode or "Auto")
    try:
        scale = max(float(view_scale), 1e-9)
    except Exception:
        scale = 1.0
    if mode == "Tydelig" or selected:
        return {
            "primary":8.4,"secondary":6.6,"assoc":7.4,"spot":6.8,
            "pad_primary":(4.6,1.7),"pad_small":(4.1,1.5),
            "gap":3.2,"row_gap":2.4,"alpha":240,
        }
    if mode == "Auto" and scale < 0.10:
        return {
            "primary":5.5,"secondary":5.2,"assoc":5.3,"spot":5.2,
            "pad_primary":(2.2,0.4),"pad_small":(2.0,0.3),
            "gap":1.7,"row_gap":1.2,"alpha":175,
        }
    if mode == "Auto" and scale < 0.145:
        return {
            "primary":5.9,"secondary":5.4,"assoc":5.6,"spot":5.4,
            "pad_primary":(2.5,0.5),"pad_small":(2.2,0.4),
            "gap":1.9,"row_gap":1.4,"alpha":188,
        }
    if mode == "Auto" and scale < 0.19:
        return {
            "primary":6.7,"secondary":5.8,"assoc":6.0,"spot":5.8,
            "pad_primary":(3.2,0.8),"pad_small":(2.8,0.7),
            "gap":2.3,"row_gap":1.7,"alpha":210,
        }
    if mode == "Minimal":
        return {
            "primary":6.1,"secondary":5.4,"assoc":5.6,"spot":5.4,
            "pad_primary":(2.5,0.5),"pad_small":(2.2,0.4),
            "gap":1.9,"row_gap":1.4,"alpha":190,
        }
    return {
        "primary":7.5,"secondary":6.2,"assoc":6.8,"spot":6.2,
        "pad_primary":(3.9,1.2),"pad_small":(3.5,1.0),
        "gap":2.8,"row_gap":2.0,"alpha":225,
    }
def output_switch_association_tag_profile(overview: bool = False) -> dict:
    """Compact print/PDF style for switch-to-light relation tags.

    The editor deliberately keeps the on-screen chips a little more prominent for
    interaction. On paper the same a/b/c relation is supporting information, so
    the tag must stay legible without competing with the electrical symbol or its
    group marking. Values are in PDF points and are intentionally independent of
    CAD/world scale.
    """
    if overview:
        return {
            "font_size": 5.2, "pad_x": 1.5, "pad_y": 0.10,
            "min_width": 0.0, "offset_x": 4.6, "radius": 2.2,
            "line_width": 0.30, "fill_alpha": 0.42,
            "border_alpha": 0.36, "text_alpha": 0.82,
        }
    return {
        "font_size": 6.2, "pad_x": 1.9, "pad_y": 0.22,
        "min_width": 0.0, "offset_x": 4.9, "radius": 2.4,
        "line_width": 0.34, "fill_alpha": 0.54,
        "border_alpha": 0.45, "text_alpha": 0.90,
    }


def output_switch_association_tag_origin(anchor_x: float, anchor_y: float,
                                         symbol_bounds: tuple[float,float,float,float],
                                         tag_width: float, tag_height: float, *,
                                         overview: bool=False) -> tuple[float,float,str]:
    """Place print/PDF relation tags from the rendered symbol silhouette."""
    left,bottom,right,top=map(float,symbol_bounds)
    sw=max(0.0,right-left); sh=max(0.0,top-bottom); margin=3.8 if overview else 4.6
    if sw > sh*1.12:
        return float(anchor_x)-float(tag_width)*.5, bottom-margin-float(tag_height), "below"
    return right+margin, float(anchor_y)-float(tag_height)*.5, "right"






























































def first_unassigned_association_channel(placement: "Placement") -> int | None:
    channels = association_channel_letters(placement)
    for i, value in enumerate(channels):
        if not value:
            return i
    return None


def assigned_association_channel_count(placement: "Placement") -> int:
    return sum(1 for value in association_channel_letters(placement) if value)










APPEARANCE_MODES = {"light": "Lys", "dark": "Mørk", "system": "Følg Windows"}


MOUNTING_ZONE_OPTIONS = (
    ("", "Ikke angivet"),
    ("floor", "Gulv"),
    ("switch", "Afbryderhøjde"),
    ("ceiling", "Loft"),
    ("custom", "Anden højde"),
)
MOUNTING_ZONE_LABELS = dict(MOUNTING_ZONE_OPTIONS)
MATERIAL_COLOR_PRESETS = ("", "Hvid", "Koksgrå", "Lysegrå", "Sort")


def normalize_mounting_zone(value) -> str:
    raw=str(value or "").strip().casefold()
    aliases={
        "":"", "none":"", "unspecified":"", "ikke angivet":"",
        "floor":"floor", "gulv":"floor", "gulvhøjde":"floor",
        "switch":"switch", "afbryder":"switch", "afbryderhøjde":"switch",
        "ceiling":"ceiling", "loft":"ceiling", "lofthøjde":"ceiling",
        "custom":"custom", "anden":"custom", "anden højde":"custom",
    }
    return aliases.get(raw,raw if raw in MOUNTING_ZONE_LABELS else "custom")


def mounting_zone_label(value) -> str:
    return MOUNTING_ZONE_LABELS.get(normalize_mounting_zone(value),"Anden højde")


def normalize_mounting_height_mm(value):
    if value is None or str(value).strip()=="":return None
    try:number=float(value)
    except (TypeError,ValueError):return None
    if not math.isfinite(number) or number<=0:return None
    return round(min(number,10000.0),1)


def normalize_material_color(value) -> str:
    return " ".join(str(value or "").strip().split())[:80]


def normalize_already_purchased(value) -> bool:
    if isinstance(value,str):return value.strip().casefold() in {"1","true","yes","ja","købt","koebt"}
    return bool(value)


def placement_procurement_context(placement) -> dict:
    zone=normalize_mounting_zone(getattr(placement,"mounting_zone","") if placement is not None else "")
    height=normalize_mounting_height_mm(getattr(placement,"mounting_height_mm",None) if placement is not None else None)
    color=normalize_material_color(getattr(placement,"material_color","") if placement is not None else "")
    purchased=normalize_already_purchased(getattr(placement,"already_purchased",False) if placement is not None else False)
    height_text=(f"{height:g} mm" if height is not None else "Ikke angivet")
    parts=[mounting_zone_label(zone)]
    if height is not None:parts.append(height_text)
    if color:parts.append(color)
    return {
        "mounting_zone":zone,
        "mounting_zone_label":mounting_zone_label(zone),
        "mounting_height_mm":height,
        "mounting_height_display":height_text,
        "material_color":color,
        "already_purchased":purchased,
        "purchase_status":"Allerede købt" if purchased else "Mangler at købe",
        "mounting_summary":" · ".join(parts),
    }


def bom_purchase_segment_key(article_no, context=None) -> str:
    row=dict(context or {})
    height=normalize_mounting_height_mm(row.get("mounting_height_mm"))
    return "\x1f".join((
        str(article_no or "").strip(),
        normalize_mounting_zone(row.get("mounting_zone")),
        "" if height is None else f"{height:.1f}",
        normalize_material_color(row.get("material_color")).casefold(),
        "1" if normalize_already_purchased(row.get("already_purchased",False)) else "0",
    ))





















































# ---------------------------------------------------------------------------
# Artikel-/BOM-model
# ---------------------------------------------------------------------------

ARTICLE_METADATA_FIELDS = (
    "category", "series", "el_no", "ean", "status", "kind",
    "cable_spec", "source", "source_checked",
    "product_type", "design_family", "design_family_raw", "module_size", "module_size_raw", "color", "color_raw", "mounting_type",
    "brand", "category_normalized", "category_group", "subcategory", "function", "taxonomy_version",
    "product_family", "product_variant", "product_family_manual", "product_variant_manual", "semantic_model_version",
    "variant_group_manual", "variant_group_id", "variant_group_label",
    "product_page", "supplier_page", "image_url", "image_local_path", "datasheet_url", "manual_url", "image_source",
    "diameter_mm", "cutout_mm", "cct", "power_w", "voltage", "dimming_type", "switch_input", "ip_rating", "shape", "environment",
    "price_currency", "price_unit", "price_kind", "price_status", "price_source", "price_checked", "price_note",
    "consumption_unit", "sales_unit", "package_label", "catalog_price_revision",
    "estimated_price_source", "estimated_price_checked", "estimated_price_confidence", "estimated_price_method",
    "manual_price_source", "manual_price_checked",
)

ARTICLE_STRUCTURED_FIELDS = (
    "technical_specs_manual", "technical_specs", "relations", "variant_attributes", "variant_axes",
    "compatibility", "semantic_evidence", "price_observations",
)


_ARTICLE_UNIT_ALIASES = {
    "styk":"stk", "stykke":"stk", "pieces":"stk", "piece":"stk", "each":"stk",
    "meter":"m", "metre":"m", "metres":"m", "meters":"m",
    "roll":"rulle", "coil":"rulle", "pack":"pakke", "package":"pakke",
    "set":"sæt", "saet":"sæt",
}


def normalize_article_unit(value, default="stk") -> str:
    """Normalisér almindelige enhedsnavne uden at afvise frie specialenheder."""
    text=str(value or "").strip().casefold().rstrip(".")
    if not text:
        text=str(default or "stk").strip().casefold() or "stk"
    return _ARTICLE_UNIT_ALIASES.get(text,text)


def _positive_article_number(value, default=1.0) -> float:
    try:number=float(value)
    except (TypeError,ValueError):number=float(default)
    return number if math.isfinite(number) and number > 0 else float(default)


def article_packaging(record) -> dict:
    """Returnér ét bagudkompatibelt forbrugs-/salgsgrundlag for en artikel.

    ``unit`` bevares som den eksisterende BOM-/leveringsenhed. De nye felter
    beskriver eksplicit hvad projektet forbruger, og hvordan varen købes. For
    ældre kabelruller udledes modellen fortsat af ``package_length_m``.
    """
    row=dict(record or {})
    legacy_unit=normalize_article_unit(row.get("unit","stk"))
    try:package_length=float(row.get("package_length_m",0) or 0)
    except (TypeError,ValueError):package_length=0.0
    packaged_cable=(str(row.get("kind","") or "").casefold()=="cable" and package_length > 0)
    package_qty=_positive_article_number(
        row.get("sales_package_quantity"),package_length if packaged_cable else 1.0)
    consumption=normalize_article_unit(row.get("consumption_unit"),"m" if packaged_cable else legacy_unit)
    default_sales=("rulle" if packaged_cable else ("pakke" if package_qty > 1.0000001 else legacy_unit))
    sales=normalize_article_unit(row.get("sales_unit"),default_sales)
    minimum=_positive_article_number(row.get("minimum_order_quantity"),1.0)
    label=str(row.get("package_label","") or "").strip()
    if not label and package_qty > 1.0000001:
        label=f"{sales} á {package_qty:g} {consumption}"
    return {
        "legacy_unit":legacy_unit,
        "consumption_unit":consumption,
        "sales_unit":sales,
        "sales_package_quantity":package_qty,
        "minimum_order_quantity":minimum,
        "package_label":label,
    }


def article_purchase_requirement(record, required_quantity) -> dict:
    """Beregn indkøbsmængde og overskud ud fra artiklens salgsforpakning."""
    pack=article_packaging(record)
    try:required=max(0.0,float(required_quantity or 0))
    except (TypeError,ValueError):required=0.0
    per_package=pack["sales_package_quantity"]
    packages=float(math.ceil(required/per_package-1e-12)) if required > 0 else 0.0
    packages=max(packages,pack["minimum_order_quantity"] if required > 0 else 0.0)
    purchased=packages*per_package
    surplus=max(0.0,purchased-required)
    summary=(
        f"{required:g} {pack['consumption_unit']} behov → {packages:g} {pack['sales_unit']}"
        if required > 0 else f"0 {pack['consumption_unit']}"
    )
    if per_package > 1.0000001:
        summary+=f" á {per_package:g} {pack['consumption_unit']}"
    if surplus > 1e-9:
        summary+=f" · {surplus:g} {pack['consumption_unit']} i overskud"
    return {**pack,"required_quantity":required,"purchase_quantity":packages,
            "purchased_consumption_quantity":purchased,"surplus_quantity":surplus,
            "summary":summary}


def article_price_basis_quantity(record, required_quantity) -> float:
    """Mængden en artikelpris skal multipliceres med for det givne behov."""
    pack=article_packaging(record); purchase=article_purchase_requirement(record,required_quantity)
    price_unit=normalize_article_unit(record.get("price_unit"),pack["consumption_unit"])
    if price_unit==pack["sales_unit"] and price_unit!=pack["consumption_unit"]:
        return float(purchase["purchase_quantity"])
    return float(purchase["required_quantity"])


def bom_article_category(record, roles=None, source_types=None) -> str:
    """Returnér en kort, brugerrettet BOM-type for filtrering og indkøb.

    Styklistens rolle har højeste prioritet, fordi samme produktfamilie fx kan
    indeholde både en indsats og dens tangent. Derefter bruges artikelgrunddata
    og beskrivelse. Formuleringer som ``uden tangent`` må ikke fejlkategorisere
    selve afbryderindsatsen som en tangent.
    """
    row=dict(record or {})
    role_text=" ".join(str(x or "") for x in (roles or [])).casefold()
    source_set={str(x or "").casefold() for x in (source_types or [])}
    if not row and not role_text:
        return "Ukendt artikel"
    if "cable" in source_set or str(row.get("kind","") or "").casefold()=="cable":
        return "Kabler"
    if "wago" in source_set:
        return "Samlemuffer og klemmer"

    role_rules=(
        ("afdæk","Afdækninger"),("tangent","Tangenter"),("indsats","Indsatser"),
        ("dåse","Dåser"),("montageramme","Rammer"),("ramme","Rammer"),
        ("muffe","Samlemuffer og klemmer"),("klemme","Samlemuffer og klemmer"),
        ("front","Fronter og tilbehør"),
    )
    for token,label in role_rules:
        if token in role_text:return label

    description=str(row.get("description","") or "").casefold()
    product_type=str(row.get("product_type","") or "").casefold()
    function=str(row.get("function","") or "").casefold()
    category=" ".join((str(row.get("category_normalized","") or ""),str(row.get("category","") or ""))).casefold()
    hay=" ".join((description,product_type,function,category))

    if ("afdækning" in description and "uden afdækning" not in description) or "dækbjælke" in description:
        return "Afdækninger"
    if "tangent" in description and "uden tangent" not in description and "uden tangenter" not in description:
        return "Tangenter"
    if "indsats" in description:return "Indsatser"
    if "dåse" in product_type or function=="dåse" or "· dåser" in category:return "Dåser"
    if "ramme" in product_type or function=="ramme" or "· rammer" in category:return "Rammer"
    if "samlemuffe" in hay or "klemmer og samlemateriel" in category:return "Samlemuffer og klemmer"
    if "kabel" in product_type or "kabel" in category:return "Kabler"
    if "lampeudtag" in hay:return "Lampeudtag"
    if "downlight" in hay or "armatur" in hay:return "Downlights og armaturer"
    if "front" in product_type or function=="front":return "Fronter og tilbehør"
    if "sensor" in hay or "pir" in hay:return "Sensorer"
    if "data og netværk" in category or "datakabel" in function:return "Data og netværk"
    if "stikkontakt" in hay or "udtag" in product_type:return "Stikkontakter og udtag"
    if "afbryder" in hay or "betjening" in product_type:return "Afbrydere og betjening"
    if "wiser" in hay or "lysstyring" in hay or "lysdæmper" in function:return "Lysstyring og smart home"
    if "tangent / afdækning" in product_type:return "Tangenter og afdækninger"
    return str(row.get("product_type","") or row.get("category_normalized","") or row.get("category","") or "Andet")


def _format_module_number(value: float) -> str:
    """Formatér valideret modulmål med dansk ½-notation."""
    value=float(value)
    if value.is_integer():
        return str(int(value))
    if abs((value % 1.0)-0.5) < 1e-9:
        whole=int(value)
        return (str(whole) if whole else "")+"½"
    return ""


def normalize_article_module(value) -> str:
    """Normalisér en *eksplicit* modulbetegnelse konservativt.

    Moduldata bruges som filter/taksonomi og må derfor ikke opfindes ud fra
    produkt-/varenummer-lignende tal. Vi accepterer kun halve moduler i et
    realistisk interval samt dokumenterede flerfeltsformer. Producentens rå
    værdi bliver ikke ændret i artikelposten; dette er alene UI-facetten.
    """
    text=str(value or "").strip().replace("×","x").replace(",",".").replace("½",".5")
    text=re.sub(r"\s+","",text)
    m=re.fullmatch(r"(\d+)x(\d+(?:\.5)?)M",text,re.I)
    if m:
        count=int(m.group(1)); size=float(m.group(2))
        # FUGA-lignende modulfelter i databasen ligger langt under dette.
        # Grænsen er bevidst konservativ, så fx 451200M aldrig bliver en facet.
        if 1 <= count <= 6 and 0.5 <= size <= 6.0 and abs(size*2-round(size*2)) < 1e-9 and count*size <= 12.0:
            size_txt=_format_module_number(size)
            return f"{count}×{size_txt}M" if size_txt else ""
        # Schneider Resi9 cabinet covers/rows use explicit Nx13M / Nx18M.
        if 1 <= count <= 4 and size in (13.0,18.0):
            return f"{count}×{int(size)}M"
        return ""
    m=re.fullmatch(r"((?:\d+(?:\.5)?|\.5))M",text,re.I)
    if not m:
        return ""
    size=float(m.group(1))
    if not (0.5 <= size <= 12.0 and abs(size*2-round(size*2)) < 1e-9):
        return ""
    size_txt=_format_module_number(size)
    return f"{size_txt}M" if size_txt else ""


def _module_label(value):
    """Find kun plausible modulbetegnelser i fri producenttekst.

    Det tidligere generiske ``\\d+M``-match kunne tolke fx et produkt-/mål-tal
    som ``451200M``. Vi finder nu kandidater og accepterer dem kun gennem den
    konservative modulvalidator ovenfor.
    """
    text=str(value or "").replace("×","x").replace(",",".").replace("½",".5")
    patterns=(
        r"(?<![\w])([1-6]\s*x\s*(?:[0-9](?:\.5)?|\.5)\s*M)(?![\w])",
        r"(?<![\w])((?:[0-9](?:\.5)?|\.5)\s*M)(?![\w])",
    )
    for pattern in patterns:
        for match in re.finditer(pattern,text,re.I):
            normalized=normalize_article_module(match.group(1))
            if normalized:
                return normalized
    return ""


def _module_group_label(module):
    normalized=normalize_article_module(module)
    if not normalized:
        return ""
    text=normalized.replace('×','x').replace('½','.5')
    m=re.fullmatch(r'(\d+)x(\d+(?:\.5)?)M',text,re.I)
    if m:
        total=int(m.group(1))*float(m.group(2))
    else:
        m=re.fullmatch(r'(\d+(?:\.5)?)M',text,re.I)
        if not m:return ''
        total=float(m.group(1))
    total_txt=_format_module_number(total)
    return f"{total_txt}M" if total_txt else ""


_ARTICLE_COLOR_CANONICAL = {
    "hvid":"Hvid", "lysegrå":"Lysegrå", "koksgrå":"Koksgrå",
    "sort":"Sort", "stål":"Stål", "staal":"Stål", "rød":"Rød",
    "roed":"Rød", "grøn":"Grøn", "groen":"Grøn", "blå":"Blå",
    "blaa":"Blå", "kobber":"Kobber", "krom":"Krom",
    "børstet alu":"Børstet alu", "boerstet alu":"Børstet alu",
    "uden afdækning":"Uden afdækning",
    "transparent / orange":"Transparent / orange",
    "transparent / hvid":"Transparent / hvid",
    "transparent / rød":"Transparent / rød",
    "transparent / gul":"Transparent / gul",
    "transparent / lysegrå":"Transparent / lysegrå",
    "grå":"Grå", "graa":"Grå", "gul":"Gul", "mørkegrå":"Mørkegrå",
    "moerkegraa":"Mørkegrå", "stålmetallic":"Stålmetallic", "staalmetallic":"Stålmetallic",
    "børstet aluminium":"Børstet aluminium", "antracitgrå":"Antracitgrå",
    "transparent":"Transparent", "klar":"Klar", "sort/hvid":"Sort / hvid",
    "hvid/hvid":"Hvid / hvid", "sort/sort":"Sort / sort", "frosted":"Frosted",
    "lys mellemgrå":"Lys mellemgrå", "orange":"Orange", "grå/mørkegrå":"Grå / mørkegrå",
    "naturel":"Naturel", "hvid/lysegrå":"Hvid / lysegrå", "rød/grøn":"Rød / grøn",
    "hvid/blå":"Hvid / blå", "ral 7035":"RAL 7035", "sort/orange":"Sort / orange",
    "hvid/sort":"Hvid / sort", "hvid/rød":"Hvid / rød", "sølvgrå":"Sølvgrå",
    "aqua":"Aqua", "grøn/hvid":"Grøn / hvid", "mørkebrun":"Mørkebrun",
    "polar hvid":"Polar hvid", "sort/rød":"Sort / rød", "hvid/gul":"Hvid / gul",
    "gul/grøn":"Gul / grøn", "beige":"Beige",
}


def normalize_article_color(value) -> str:
    """Saml kun trivielle stave-/spacingvarianter uden at ændre producentfarven."""
    raw=str(value or "").strip()
    if not raw:
        return ""
    compact=re.sub(r"\s*/\s*"," / ",re.sub(r"\s+"," ",raw)).strip()
    key=compact.casefold()
    return _ARTICLE_COLOR_CANONICAL.get(key,compact)



def article_filter_facets(record):
    """Returnér ensartede, brugerrettede facetter til artikelbrowseren.

    De indbyggede poster kan have eksplicitte facetter. For ældre poster og
    brugerartikler udledes de så vidt muligt fra serie/kategori/beskrivelse.
    """
    r=dict(record or {})
    desc=str(r.get("description","") or "")
    cat=str(r.get("category","") or "")
    series=str(r.get("series","") or "")
    hay=f"{desc} {cat} {series}".casefold()

    product_type=str(r.get("product_type","") or "").strip()
    if not product_type:
        if str(r.get("kind","")).casefold()=="cable": product_type="Kabel"
        elif "teknisk" in hay and "ramme" in hay: product_type="Teknisk monteringsramme"
        elif "forfradåse" in hay or "forfra dåse" in hay: product_type="Forfradåse"
        elif "indmur" in hay and "dåse" in hay: product_type="Indmuringsdåse"
        elif "indstøb" in hay and "dåse" in hay: product_type="Indstøbningsdåse"
        elif "dåse" in hay: product_type="Dåse"
        elif "ramme" in hay: product_type="Ramme"
        elif "stikkontakt" in hay or "udtag" in hay: product_type="Stikkontakt / udtag"
        elif "tangent" in hay or "afdæk" in hay or "dækplade" in hay: product_type="Tangent / afdækning"
        elif "afbryder" in hay or "tryk" in hay or "lysdæmper" in hay: product_type="Afbryder / betjening"
        elif "wiser" in hay: product_type="Wiser"
        else: product_type="Øvrigt"

    design=str(r.get("design_family","") or "").strip()
    if not design:
        if "slim" in hay: design="SLIM"
        elif "baseline 63" in hay: design="BASELINE 63"
        elif "base 63" in hay: design="BASE 63"
        elif "softline 63" in hay: design="SOFTLINE 63"
        elif "choice" in hay: design="CHOICE"
        elif "pure" in hay: design="PURE"
        elif re.search(r"\bsoft\b",hay): design="SOFT"
        elif "wiser" in hay: design="Wiser"
        elif "air" in hay: design="AIR"
        elif "wask" in str(r.get("manufacturer","")).casefold(): design="Installationskabel"
        elif "fuga" in hay: design="FUGA"
        else: design=""

    raw_module=str(r.get("module_size","") or "").strip()
    module=normalize_article_module(raw_module) if raw_module else ""
    if not module and not raw_module and str(r.get("kind","") or "").casefold()!="cable":
        module=_module_label(desc)

    color=normalize_article_color(r.get("color",""))
    if not color:
        # Fallback fra tekst er konservativ og bevarer producentens farvebegreb.
        # Fx er "Antracit" ikke automatisk det samme som LK's "Koksgrå".
        for needle,label in (
            ("koksgrå","Koksgrå"),("lysegrå","Lysegrå"),("hvid","Hvid"),
            ("stålmetallic","Stålmetallic"),("antracit","Antracit"),("stål","Stål"),
            ("sort","Sort"),("petroleum","Petroleum"),("rød","Rød"),
        ):
            if needle in hay:
                color=label; break

    mounting=str(r.get("mounting_type","") or "").strip()
    if not mounting:
        if product_type in ("Forfradåse","Indmuringsdåse","Indstøbningsdåse","Dåse"):
            mounting=product_type
        elif product_type=="Teknisk monteringsramme": mounting="Teknisk ramme"
        elif product_type=="Ramme": mounting="Design-/dækramme"
        else: mounting=""

    semantic_input=dict(r)
    semantic_input["product_type"]=product_type
    semantics=article_intelligence.derive_product_semantics(semantic_input)
    product_family=str(semantics.get("product_family","") or "").strip()
    product_variant=str(semantics.get("product_variant","") or "").strip()
    # The old Design field is retained only as a compatibility/backward-facing
    # facet. Boxes now use Family + Variant; their compatible frame designs must
    # never appear as the box's own design.
    if "dåse" in product_type.casefold():
        design=""
    return {"product_type":product_type,"design_family":design,"product_family":product_family,"product_variant":product_variant,"module_size":module,"module_group":_module_group_label(module),"color":color,"mounting_type":mounting}


def normalize_article_catalog(records):
    """Normalisér et artikelbibliotek uden at miste producentmetadata.

    Artikelnummeret er den stabile nøgle.  Ud over de oprindelige felter
    bevares metadata fra det indbyggede standardbibliotek (serie, kategori,
    EL-nummer, EAN, status og kabeldata), så en artikel kan kopieres ind i et
    projekt og fortsat være fuldt selvbeskrivende.
    """
    out=[]; seen=set()
    for raw in records or []:
        if not isinstance(raw,dict):
            continue
        article_no=str(raw.get("article_no", "") or "").strip()
        key=article_no.casefold()
        if not article_no or key in seen:
            continue
        seen.add(key)
        unit=str(raw.get("unit", "stk") or "stk").strip() or "stk"
        item={
            "article_no":article_no,
            "description":str(raw.get("description", "") or "").strip(),
            "manufacturer":str(raw.get("manufacturer", "") or "").strip(),
            "unit":unit,
            "note":str(raw.get("note", "") or "").strip(),
        }
        facets=article_filter_facets(raw)
        for field_name in ARTICLE_METADATA_FIELDS:
            value=str(raw.get(field_name, "") or "").strip()
            if not value and field_name in facets:
                value=str(facets.get(field_name,"") or "").strip()
            if value:
                item[field_name]=value
        # Structured metadata is deliberately kept outside the legacy string
        # field loop.  It is JSON-safe and lets the article model grow without
        # flattening relation/specification data into opaque prose.
        for field_name in ARTICLE_STRUCTURED_FIELDS:
            value=raw.get(field_name)
            if isinstance(value,dict) and value:
                if field_name in {"compatibility","semantic_evidence"}:
                    # Semantic structures contain nested lists/dicts (e.g.
                    # compatible design series plus provenance per dimension).
                    # Preserve their shape instead of flattening them to repr strings.
                    item[field_name]=json.loads(json.dumps(value,ensure_ascii=False))
                else:
                    item[field_name]={str(k):str(v) for k,v in value.items() if str(k).strip() and str(v).strip()}
            elif isinstance(value,(list,tuple)) and value:
                item[field_name]=json.loads(json.dumps(value,ensure_ascii=False))
        # LK's eget katalog har produktfotos på en stabil varenummerbaseret URL.
        # Brug den direkte kilde som lazy preview (med eksisterende disk-cache),
        # så artikelvælgeren ikke skal hente og parse en hel produktside først.
        lk_hay=" ".join(str(raw.get(k,"") or "") for k in ("description","manufacturer","series","category","source","product_page")).casefold()
        lk_article=bool(re.fullmatch(r"[0-9a-z_-]+",article_no,re.I)) and ("lk fuga" in lk_hay or "lk.dk" in lk_hay or "lauritz knudsen" in lk_hay)
        if lk_article and not str(item.get("image_url","") or "").strip():
            item["image_url"]=f"https://www1.lk.dk/katalog/foto/jpg/{article_no}.jpg"
            item.setdefault("image_source","LK / Schneider Electric")
        if lk_article and not str(item.get("product_page","") or "").strip():
            item["product_page"]=f"https://www.lk.dk/produkter/{article_no}"
        if "package_length_m" in raw:
            try:
                package_length=float(raw.get("package_length_m",0.0) or 0.0)
            except (TypeError,ValueError):
                package_length=0.0
            if math.isfinite(package_length) and package_length >= 0:
                item["package_length_m"]=package_length
        packaging=article_packaging(raw)
        item["consumption_unit"]=packaging["consumption_unit"]
        item["sales_unit"]=packaging["sales_unit"]
        item["sales_package_quantity"]=packaging["sales_package_quantity"]
        item["minimum_order_quantity"]=packaging["minimum_order_quantity"]
        if packaging["package_label"]:
            item["package_label"]=packaging["package_label"]
        # Prisdata fra producent-/importkilder behandles som metadata.  Den
        # separate brugerprisbog lægges ovenpå i UI/BOM, så manuelle priser
        # aldrig kan blive overskrevet af en katalogsynkronisering.
        for price_field in ("estimated_price", "manual_price", "effective_price", "unit_price", "estimated_price_min", "estimated_price_max"):
            if price_field not in raw or str(raw.get(price_field, "")).strip() == "":
                continue
            try:
                price_value=float(raw.get(price_field))
            except (TypeError,ValueError):
                price_value=None
            if price_value is not None and math.isfinite(price_value) and price_value >= 0:
                item[price_field]=price_value
                item.setdefault("price_currency", str(raw.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK")
        if str(raw.get("estimated_price_sources", "") or "").strip():
            try:
                source_count=int(raw.get("estimated_price_sources"))
            except (TypeError,ValueError):
                source_count=0
            if source_count > 0:
                item["estimated_price_sources"]=source_count
        out.append(item)
    # Controlled taxonomy, technical properties, variants and normalised
    # relation data are derived with whole-catalogue context. Source category,
    # description and manufacturer wording remain untouched.
    return article_intelligence.enrich_catalog(out)


@lru_cache(maxsize=1)
def _predefined_article_catalog_cached():
    """Læs programmets indbyggede standardbibliotek én gang.

    Der ligger både en JSON-fil til manuel inspektion/opdatering og en Python-
    fallback, så biblioteket også virker i en pakket Windows-build hvor en
    separat datafil ikke nødvendigvis følger automatisk med.
    """
    records=[]
    try:
        data_path=Path(__file__).with_name("predefined_articles.json")
        payload=json.loads(data_path.read_text(encoding="utf-8"))
        records=payload.get("articles",[]) if isinstance(payload,dict) else []
    except Exception:
        try:
            from predefined_articles_data import ARTICLES as records
        except Exception:
            records=[]
    return tuple(tuple(sorted(item.items())) for item in normalize_article_catalog(records))


def load_predefined_article_catalog():
    """Returnér en mutérbar kopi af LK FUGA/Wiser/Waskönig+Walter-biblioteket."""
    return [dict(items) for items in _predefined_article_catalog_cached()]


def normalize_cable_article_bindings(data):
    """Normalisér kabeltype/specifikation -> artikelnummer."""
    if not isinstance(data,dict):
        return {}
    out={}
    for raw_key,raw_article in data.items():
        key=str(raw_key or "").strip()
        article_no=str(raw_article or "").strip()
        if key and article_no:
            out[key]=article_no
    return out


def cable_article_key(layer: str, cable_spec: str) -> str:
    return f"{str(layer or CABLE_LAYER).strip()}|{str(cable_spec or '').strip()}"


def cable_article_key_parts(key: str) -> tuple[str,str]:
    text=str(key or "")
    if "|" in text:
        layer,spec=text.split("|",1)
        return layer or CABLE_LAYER,spec
    return CABLE_LAYER,text


def cable_type_display(layer: str) -> str:
    reverse={value:name for name,value in CABLE_TYPES.items()}
    return reverse.get(str(layer or ""),str(layer or "Kabel"))


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






def _nearest_dxf_lineweight(width_mm: float) -> int:
    """Konvertér mm til nærmeste gyldige DXF lineweight (1/100 mm)."""
    valid = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211)
    target = max(0.0, float(width_mm)) * 100.0
    return min(valid, key=lambda value: abs(value - target))












def _screen_line_width(width_mm: float, selected: bool = False) -> int:
    # CAD-lineweight vises som en omtrent fysisk skærmtykkelse og skaleres ikke
    # med zoom, ligesom lineweight normalt gør i en CAD-viewer.
    px = max(1, int(round(max(float(width_mm), 0.01) * 96.0 / 25.4)))
    return px + (1 if selected else 0)






def _true_color_int(hex_color: str) -> int:
    c = normalize_hex_color(hex_color)
    return int(c[1:], 16)


# Common AutoCAD $INSUNITS values. The length estimator deliberately only
# treats units with an unambiguous linear SI conversion as automatic.
INSUNITS_METERS = {
    1: ("in", 0.0254),
    2: ("ft", 0.3048),
    3: ("mi", 1609.344),
    4: ("mm", 0.001),
    5: ("cm", 0.01),
    6: ("m", 1.0),
    7: ("km", 1000.0),
    10: ("yd", 0.9144),
    14: ("dm", 0.1),
    15: ("dam", 10.0),
    16: ("hm", 100.0),
    21: ("US survey ft", 1200.0 / 3937.0),
}


def drawing_unit_info(doc) -> tuple[int, str, float | None]:
    """Return ($INSUNITS code, friendly unit, metres per drawing unit)."""
    try:
        code = int(doc.header.get("$INSUNITS", 0) or 0)
    except Exception:
        code = 0
    label, factor = INSUNITS_METERS.get(code, ("enhedsløs/ukendt", None))
    return code, label, factor

























def cable_display_label(cable: CablePlacement) -> str:
    """Byg den tekst, der vises/eksporteres ved et kabel eller en ledning."""
    parts=[]
    if getattr(cable, "auto_label", False):
        if getattr(cable, "cable_id", ""): parts.append(str(cable.cable_id).strip())
        # Ved blandede kabeltyper vises kabel-ID'et som fælles hovedlabel,
        # mens de faktiske typer mærkes pr. fysisk afsnit. Ellers kunne en
        # global 3G-label ved et lokalt 5G-afsnit være direkte misvisende.
        if not normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        ) and getattr(cable, "cable_spec", ""):
            parts.append(str(cable.cable_spec).strip())
    if getattr(cable, "label", ""): parts.append(str(cable.label).strip())
    return " · ".join(x for x in parts if x)


def cable_plan_label(cable: CablePlacement) -> str:
    """Kompakt kabelmærkning til selve plantegningen.

    Den brugerdefinerede ekstra mærkning er bevidst udeladt fra canvas/print;
    den er stadig projektdata og vises i hover/inspector/ruteoversigter.
    """
    parts=[]
    if getattr(cable, "auto_label", False):
        if getattr(cable, "cable_id", ""): parts.append(str(cable.cable_id).strip())
        if not normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        ) and getattr(cable, "cable_spec", ""):
            parts.append(str(cable.cable_spec).strip())
    return " · ".join(x for x in parts if x)






















@lru_cache(maxsize=1024)
def _arc_points(cx, cy, r, a1, a2, steps=24):
    return [
        (cx + r * math.cos(math.radians(a1 + (a2 - a1) * i / steps)),
         cy + r * math.sin(math.radians(a1 + (a2 - a1) * i / steps)))
        for i in range(steps + 1)
    ]





























def _visual_segment_info(a, b):
    ax,ay=float(a[0]),float(a[1]); bx,by=float(b[0]),float(b[1])
    dx=bx-ax; dy=by-ay; length=math.hypot(dx,dy)
    if length<=1e-12:return None
    ux=dx/length; uy=dy/length
    # Fælles kanonisk retning gør, at kabler tegnet i modsat retning stadig
    # får den samme fysiske side af centerlinjen for samme lane-indeks.
    cux,cuy=ux,uy
    if cux < -1e-12 or (abs(cux)<=1e-12 and cuy < 0.0):
        cux,cuy=-cux,-cuy
    nx,ny=-cuy,cux
    return {
        "a":(ax,ay),"b":(bx,by),"u":(ux,uy),"cu":(cux,cuy),
        "n":(nx,ny),"length":length,
    }


def _visual_segments_overlap(sa, sb, tolerance: float, min_overlap: float) -> bool:
    """Return True when two cable segments are visually the same route.

    Parallel cable detection is intentionally screen-tolerant rather than CAD-
    exact.  Real projects often contain tiny coordinate/angle differences from
    snapping, imported drawings or later edits.  If those differences are only
    a few screen pixels the user sees one merged line, so they must still be
    treated as a shared route and separated into lanes.
    """
    if sa is None or sb is None:return False
    u1=sa["cu"]; u2=sb["cu"]

    # Up to ~2 degrees is accepted, but only if the two lines also stay within
    # the screen-derived distance tolerance over the actual overlap below.
    if abs(u1[0]*u2[1]-u1[1]*u2[0]) > math.sin(math.radians(2.0)):
        return False

    ux,uy=u1
    nx,ny=sa["n"]
    def proj(pt):return float(pt[0])*ux+float(pt[1])*uy
    a0,a1=sorted((proj(sa["a"]),proj(sa["b"])))
    b0,b1=sorted((proj(sb["a"]),proj(sb["b"])))
    lo=max(a0,b0); hi=min(a1,b1)
    if hi-lo <= min_overlap:return False

    # Compare the two infinite lines at both ends of the common projected
    # interval.  This catches tiny non-collinearity while rejecting nearby
    # routes that merely cross or diverge visibly.
    bax,bay=sb["a"]; bux,buy=sb["u"]
    denom=bux*ux+buy*uy
    if abs(denom)<=1e-9:return False
    aax,aay=sa["a"]
    base_proj=proj(sb["a"])
    for t in (lo,hi,(lo+hi)*0.5):
        s=(t-base_proj)/denom
        qx=bax+bux*s; qy=bay+buy*s
        # Point on A's line with the same canonical projection.
        pa_x=aax+ux*(t-proj(sa["a"]))
        pa_y=aay+uy*(t-proj(sa["a"]))
        dist=abs((qx-pa_x)*nx+(qy-pa_y)*ny)
        if dist > tolerance:return False
    return True


def _line_intersection(p1, d1, p2, d2):
    cross=d1[0]*d2[1]-d1[1]*d2[0]
    if abs(cross)<=1e-10:return None
    qx=float(p2[0])-float(p1[0]); qy=float(p2[1])-float(p1[1])
    t=(qx*d2[1]-qy*d2[0])/cross
    return (float(p1[0])+t*d1[0],float(p1[1])+t*d1[1])


def _cable_visual_sort_key(cable, fallback_index: int = 0):
    """Stable ordering for visual lanes independent of project/list ordering."""
    cid=str(getattr(cable,"cable_id","") or "").strip().casefold()
    uid=str(getattr(cable,"uid","") or "").strip().casefold()
    spec=str(getattr(cable,"cable_spec","") or "").strip().casefold()
    return (cid or "~", uid or "~", spec, int(fallback_index))


def cable_visual_layout(cables, lane_gap: float, *, tolerance: float | None=None, fan_length: float | None=None):
    """Return visual paths, per-cable lane metadata and shared-route groups.

    ``CablePlacement.points`` is never modified.  Cables sharing a logical
    centreline are placed on stable screen-space lanes.  The lane order uses
    cable id/uid rather than list order, so adding/removing another cable does
    not randomly swap the physical side of existing lanes.
    """
    cable_list=list(cables or [])
    gap=max(abs(float(lane_gap)),0.0)
    result={id(c):[(float(x),float(y)) for x,y in getattr(c,"points",[]) or []] for c in cable_list}
    metadata={id(c):{
        "lane_index":0,"lane_count":1,"lane_offset":0.0,"max_parallel":1,
        "peer_ids":[str(getattr(c,"cable_id","") or "")],"parallel_segments":0,
    } for c in cable_list}
    if gap<=1e-12 or len(cable_list)<2:
        return result, metadata, []
    # Match routes by what the user actually sees.  Roughly 3.5 px at the
    # default 10 px lane gap may look like one anti-aliased line at overview
    # zoom, even though the CAD centre lines are not numerically identical.
    tol=max(float(tolerance) if tolerance is not None else gap*0.35,1e-8)
    min_overlap=max(gap*1.15,tol*3.5,1e-7)
    fan=max(float(fan_length) if fan_length is not None else gap*2.35,gap)

    segments=[]
    per_cable=[]
    for ci,cable in enumerate(cable_list):
        pts=[(float(x),float(y)) for x,y in getattr(cable,"points",[]) or []]
        indices=[]
        for si,(a,b) in enumerate(zip(pts,pts[1:])):
            info=_visual_segment_info(a,b)
            if info is not None:
                info.update({"cable":ci,"segment":si})
                indices.append(len(segments)); segments.append(info)
            else:
                indices.append(None)
        per_cable.append((pts,indices))

    stable_keys={ci:_cable_visual_sort_key(cable_list[ci],ci) for ci in range(len(cable_list))}
    offsets_by_segment={}
    group_candidates={}

    # 0.59.58 performance: the old implementation compared every segment with
    # every other segment on every zoom-dependent lane rebuild (O(S²)).  First
    # use a conservative expanded bounding-box sweep to reject segment pairs
    # that cannot possibly share a route.  _visual_segments_overlap remains the
    # authoritative test, so visual behaviour and tolerance rules are unchanged.
    peer_cables=[{seg["cable"]} for seg in segments]
    if len(segments)>1:
        expanded=[]
        for idx,seg in enumerate(segments):
            ax,ay=seg["a"]; bx,by=seg["b"]
            expanded.append((min(ax,bx)-tol,max(ax,bx)+tol,min(ay,by)-tol,max(ay,by)+tol,idx))
        sweep=sorted(expanded,key=lambda row:row[0])
        sweep_count=len(sweep)
        for pos,left in enumerate(sweep):
            _xmin,xmax,ymin,ymax,idx=left
            seg=segments[idx]
            # Do not slice ``sweep[pos+1:]`` here.  Even when the first x
            # coordinate rejects the candidate immediately, that slice copies
            # the complete remaining list and quietly turns a sparse plan back
            # into quadratic work.
            next_pos=pos+1
            while next_pos<sweep_count:
                other_row=sweep[next_pos]
                next_pos+=1
                oxmin,_oxmax,oymin,oymax,j=other_row
                if oxmin>xmax:
                    break
                if oymin>ymax or oymax<ymin:
                    continue
                other=segments[j]
                if other["cable"]==seg["cable"]:
                    continue
                if _visual_segments_overlap(seg,other,tol,min_overlap):
                    peer_cables[idx].add(other["cable"])
                    peer_cables[j].add(seg["cable"])

    for idx,seg in enumerate(segments):
        peers=peer_cables[idx]
        if len(peers)>1:
            order=sorted(peers,key=lambda ci:stable_keys[ci])
            lane_index=order.index(seg["cable"])
            lane=lane_index-(len(order)-1)/2.0
            peer_ids=[str(getattr(cable_list[ci],"cable_id","") or "Kabel") for ci in order]
            offsets_by_segment[(seg["cable"],seg["segment"])]=(lane*gap,lane_index,len(order),peer_ids)
            meta=metadata[id(cable_list[seg["cable"]])]
            meta["parallel_segments"]+=1
            if len(order)>int(meta.get("max_parallel",1)) or (
                len(order)==int(meta.get("max_parallel",1)) and seg["length"]>float(meta.get("_best_length",-1.0))
            ):
                meta.update({
                    "lane_index":lane_index,"lane_count":len(order),"lane_offset":lane*gap,
                    "max_parallel":len(order),"peer_ids":peer_ids,"_best_length":float(seg["length"]),
                })

            # One compact badge per peer-set, positioned on its longest shared
            # segment.  Used by the Qt overview to show e.g. “×6”.
            group_key=tuple(order)
            mid=((seg["a"][0]+seg["b"][0])*.5,(seg["a"][1]+seg["b"][1])*.5)
            old=group_candidates.get(group_key)
            if old is None or seg["length"]>old["length"]:
                group_candidates[group_key]={
                    "count":len(order),"cable_indices":list(order),"cable_ids":peer_ids,
                    "point":mid,"length":float(seg["length"]),
                }

    # Fælles fysisk afgang fra samme symbol/terminal er autoritativ for fan-out.
    # Segmentmatching alene er ikke nok: i rigtige projekter kan to kabler være
    # opdelt i forskellige knækpunkter eller afvige en anelse, selv om de visuelt
    # forlader samme tavle/lampested i samme retning. Derfor tvinges de første
    # kollineære segmenter ud på stabile baner ud fra selve endepunktsankeret.
    endpoint_records=[]
    anchor_tol=max(tol,gap*0.35,1e-8)
    direction_cos=math.cos(math.radians(12.0))
    for ci,(pts,seg_indices) in enumerate(per_cable):
        if len(pts)<2:
            continue
        conn_by_index={int(r.get("point_index",-1)):r for r in cable_symbol_connections(cable_list[ci])}
        for at_start in (True,False):
            vi=0 if at_start else len(pts)-1
            si=0 if at_start else len(pts)-2
            idx=seg_indices[si] if 0 <= si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            if info is None:
                continue
            if at_start:
                outward=info["u"]
            else:
                outward=(-info["u"][0],-info["u"][1])
            conn=conn_by_index.get(vi)
            symbol_key=None
            if conn is not None and str(conn.get("symbol_uid","") or "").strip():
                symbol_key=(str(conn.get("symbol_uid","") or "").strip(),int(conn.get("symbol_port",0) or 0))
            endpoint_records.append({
                "cable":ci,"vertex":vi,"segment":si,"at_start":at_start,
                "point":pts[vi],"outward":outward,"symbol_key":symbol_key,
            })

    def same_endpoint_anchor(a,b):
        ka=a.get("symbol_key"); kb=b.get("symbol_key")
        if ka is not None and kb is not None:
            return ka==kb
        ax,ay=a["point"]; bx,by=b["point"]
        return math.hypot(ax-bx,ay-by) <= anchor_tol

    def same_departure(a,b):
        au=a["outward"]; bu=b["outward"]
        return au[0]*bu[0]+au[1]*bu[1] >= direction_cos

    # Candidate lookup for endpoint fan-out.  The previous all-pairs loop was
    # O(C²), even when the cable ends were spread across an entire building.
    # Exact symbol/port buckets preserve the authoritative terminal rule;
    # neighbouring spatial cells cover coordinate-based legacy endpoints.
    endpoint_symbol_buckets=defaultdict(list)
    endpoint_spatial_buckets=defaultdict(list)
    endpoint_cell=max(anchor_tol,1e-8)
    endpoint_cells=[]
    for record_index,rec in enumerate(endpoint_records):
        symbol_key=rec.get("symbol_key")
        if symbol_key is not None:
            endpoint_symbol_buckets[symbol_key].append(record_index)
        px,py=rec["point"]
        cell=(math.floor(float(px)/endpoint_cell),math.floor(float(py)/endpoint_cell))
        endpoint_cells.append(cell)
        endpoint_spatial_buckets[cell].append(record_index)

    forced_endpoint_offsets={}
    for record_index,rec in enumerate(endpoint_records):
        peers={rec["cable"]}
        candidates=set(endpoint_symbol_buckets.get(rec.get("symbol_key"),())) if rec.get("symbol_key") is not None else set()
        cell_x,cell_y=endpoint_cells[record_index]
        for grid_x in range(cell_x-1,cell_x+2):
            for grid_y in range(cell_y-1,cell_y+2):
                candidates.update(endpoint_spatial_buckets.get((grid_x,grid_y),()))
        for other_index in candidates:
            other=endpoint_records[other_index]
            if other is rec or other["cable"]==rec["cable"]:
                continue
            if same_endpoint_anchor(rec,other) and same_departure(rec,other):
                peers.add(other["cable"])
        if len(peers)<2:
            continue
        order=sorted(peers,key=lambda ci:stable_keys[ci])
        lane_index=order.index(rec["cable"])
        lane=lane_index-(len(order)-1)/2.0
        peer_ids=[str(getattr(cable_list[ci],"cable_id","") or "Kabel") for ci in order]
        forced_endpoint_offsets[(rec["cable"],bool(rec["at_start"]))]=(lane*gap,lane_index,len(order),peer_ids)
        meta=metadata[id(cable_list[rec["cable"]])]
        if len(order)>int(meta.get("max_parallel",1)):
            meta.update({
                "lane_index":lane_index,"lane_count":len(order),"lane_offset":lane*gap,
                "max_parallel":len(order),"peer_ids":peer_ids,
            })

    # Propagér den tvungne bane gennem den rette afgangs-/ankomststrækning.
    # Det gør fan-out robust selv hvis samme rute er opdelt i flere små,
    # kollineære segmenter hos det ene kabel. Ved første reelle drejning stopper
    # tvangen; derfra tager den almindelige overlapdetektion over.
    collinear_cos=math.cos(math.radians(3.0))
    for (ci,at_start),rec in forced_endpoint_offsets.items():
        offset,lane_index,count,peer_ids=rec
        pts,seg_indices=per_cable[ci]
        if len(pts)<2:
            continue
        ordered=range(0,len(pts)-1) if at_start else range(len(pts)-2,-1,-1)
        base_u=None
        for si in ordered:
            idx=seg_indices[si] if si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            if info is None:
                continue
            u=info["u"] if at_start else (-info["u"][0],-info["u"][1])
            if base_u is None:
                base_u=u
            elif u[0]*base_u[0]+u[1]*base_u[1] < collinear_cos:
                break
            current=offsets_by_segment.get((ci,si))
            # Et større allerede detekteret bundt bevares; ellers er det fysiske
            # endepunktsbundt mere autoritativt end fuzzy segmentmatching.
            if current is None or int(current[2]) <= int(count):
                offsets_by_segment[(ci,si)]=(offset,lane_index,count,peer_ids)

    for meta in metadata.values():
        meta.pop("_best_length",None)

    for ci,(pts,seg_indices) in enumerate(per_cable):
        if len(pts)<2:continue
        seg_infos=[]; seg_offsets=[]
        for si in range(len(pts)-1):
            idx=seg_indices[si] if si < len(seg_indices) else None
            info=segments[idx] if idx is not None else _visual_segment_info(pts[si],pts[si+1])
            seg_infos.append(info)
            rec=offsets_by_segment.get((ci,si))
            seg_offsets.append(float(rec[0]) if rec is not None else 0.0)
        if not any(abs(d)>1e-12 for d in seg_offsets):continue

        def shifted_on_segment(si, point):
            info=seg_infos[si]; d=seg_offsets[si]
            if info is None or abs(d)<=1e-12:return (float(point[0]),float(point[1]))
            nx,ny=info["n"]
            return (float(point[0])+nx*d,float(point[1])+ny*d)

        anchor_indices={int(r.get("point_index",-1)) for r in cable_symbol_connections(cable_list[ci])}
        interior=[]
        for vi in range(1,len(pts)-1):
            prev=seg_infos[vi-1]; nxt=seg_infos[vi]
            pa=shifted_on_segment(vi-1,pts[vi]); pb=shifted_on_segment(vi,pts[vi])
            dprev=seg_offsets[vi-1]; dnext=seg_offsets[vi]
            if vi in anchor_indices:
                # Fysiske mellemtilslutninger må aldrig flyttes kosmetisk væk
                # fra symbolet. Banen fletter derfor ind til det rigtige anker
                # og fanner ud igen efter symbolet.
                vx,vy=pts[vi]
                if prev is not None and abs(dprev)>1e-12:
                    f=min(fan,prev["length"]*.35)
                    interior.append((vx-prev["u"][0]*f+prev["n"][0]*dprev,
                                     vy-prev["u"][1]*f+prev["n"][1]*dprev))
                interior.append((vx,vy))
                if nxt is not None and abs(dnext)>1e-12:
                    f=min(fan,nxt["length"]*.35)
                    interior.append((vx+nxt["u"][0]*f+nxt["n"][0]*dnext,
                                     vy+nxt["u"][1]*f+nxt["n"][1]*dnext))
                continue
            hit=_line_intersection(pa,prev["u"],pb,nxt["u"]) if prev is not None and nxt is not None else None
            if hit is not None:
                interior.append(hit); continue
            if prev is not None and nxt is not None and abs(dprev-dnext)>1e-12:
                f=min(fan,prev["length"]*.25,nxt["length"]*.25)
                vx,vy=pts[vi]
                p1=(vx-prev["u"][0]*f+prev["n"][0]*dprev,
                    vy-prev["u"][1]*f+prev["n"][1]*dprev)
                p2=(vx+nxt["u"][0]*f+nxt["n"][0]*dnext,
                    vy+nxt["u"][1]*f+nxt["n"][1]*dnext)
                interior.extend((p1,p2))
            else:
                interior.append(((pa[0]+pb[0])*.5,(pa[1]+pb[1])*.5))

        out=[pts[0]]
        first=seg_infos[0]; d0=seg_offsets[0]
        if first is not None and abs(d0)>1e-12:
            f=min(fan,first["length"]*.35)
            ux,uy=first["u"]; nx,ny=first["n"]
            out.append((pts[0][0]+ux*f+nx*d0,pts[0][1]+uy*f+ny*d0))
        out.extend(interior)
        last=seg_infos[-1]; dn=seg_offsets[-1]
        if last is not None and abs(dn)>1e-12:
            f=min(fan,last["length"]*.35)
            ux,uy=last["u"]; nx,ny=last["n"]
            out.append((pts[-1][0]-ux*f+nx*dn,pts[-1][1]-uy*f+ny*dn))
        out.append(pts[-1])

        clean=[]
        for q in out:
            q=(float(q[0]),float(q[1]))
            if not clean or math.hypot(q[0]-clean[-1][0],q[1]-clean[-1][1])>1e-9:
                clean.append(q)
        result[id(cable_list[ci])]=clean

    groups=sorted(group_candidates.values(),key=lambda g:(-int(g["count"]),-float(g["length"]),tuple(g["cable_ids"])))
    return result, metadata, groups


def cable_visual_paths(cables, lane_gap: float, *, tolerance: float | None=None, fan_length: float | None=None):
    """Backward-compatible visual path helper."""
    return cable_visual_layout(cables,lane_gap,tolerance=tolerance,fan_length=fan_length)[0]


def ensure_layers(doc: ezdxf.document.Drawing) -> None:
    """Opret programmets dedikerede el-lag uden at ændre eksisterende lag."""
    for layer_name, color in GENERATED_LAYER_COLORS.items():
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=color)


def add_placement_to_dxf(msp, placement: Placement, annotation_style: str = DEFAULT_ANNOTATION_STYLE) -> None:
    layer = symbol_layer(placement.symbol)
    lineweight = _nearest_dxf_lineweight(placement.line_width)
    attrs = {"layer": layer, "color": 256, "true_color": _true_color_int(placement.color), "lineweight": lineweight}
    for prim in symbol_primitives(placement.symbol, placement.size):
        typ = prim[0]
        if typ == "line":
            _, x1,y1,x2,y2 = prim
            x1,y1=rotate_point(x1,y1,placement.rotation); x2,y2=rotate_point(x2,y2,placement.rotation)
            msp.add_line((placement.x+x1, placement.y+y1),(placement.x+x2,placement.y+y2),dxfattribs=attrs)
        elif typ == "circle":
            _,cx,cy,r=prim; cx,cy=rotate_point(cx,cy,placement.rotation)
            msp.add_circle((placement.x+cx,placement.y+cy),r,dxfattribs=attrs)
        elif typ == "arc":
            _,cx,cy,r,a1,a2=prim; cx,cy=rotate_point(cx,cy,placement.rotation)
            msp.add_arc((placement.x+cx,placement.y+cy),r,a1+placement.rotation,a2+placement.rotation,dxfattribs=attrs)
        elif typ == "polyline":
            pts=[]
            for x,y in prim[1]:
                x,y=rotate_point(x,y,placement.rotation); pts.append((placement.x+x,placement.y+y))
            msp.add_lwpolyline(pts,dxfattribs=attrs)
        elif typ in {"text", "upright_text"}:
            _,x,y,t,h=prim; x,y=rotate_point(x,y,placement.rotation)
            rotation=0.0 if typ=="upright_text" else placement.rotation
            ent=msp.add_text(t,height=h,dxfattribs={"layer":layer,"color":256,"true_color":_true_color_int(placement.color),"rotation":rotation,"lineweight":lineweight})
            ent.set_placement((placement.x+x,placement.y+y),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    assoc=association_display(placement)
    if assoc:
        ax,ay=association_world_point(placement)
        h=max(placement.size*.085,1.0)
        ent=msp.add_mtext(assoc,dxfattribs={"layer":META_LAYER,"color":5,"char_height":h})
        ent.set_location((ax,ay))
        try: ent.set_bg_color("canvas",scale=1.08)
        except Exception: pass
    meta_parts=symbol_annotation_lines(placement,annotation_style)
    if meta_parts:
        compact=(str(annotation_style)!="Detaljeret")
        h=max(placement.size*(.075 if compact else .10),1.0)
        ent=msp.add_mtext("\\P".join(meta_parts),dxfattribs={"layer":META_LAYER,"color":3,"char_height":h})
        ent.set_location((placement.x+placement.size*.22,placement.y+placement.size*.22))
        try: ent.set_bg_color("canvas",scale=1.10 if compact else 1.18)
        except Exception: pass


def add_cable_to_dxf(msp, cable: CablePlacement) -> None:
    if len(cable.points) < 2:
        return
    base_layer = cable.layer if cable.layer in (CABLE_LAYER, PATCH_CABLE_LAYER, WIRE_LAYER) else CABLE_LAYER
    layer = cable_category_layer_name(base_layer,getattr(cable,"cable_category",DEFAULT_CABLE_CATEGORY))
    try:
        if layer not in msp.doc.layers:
            msp.doc.layers.add(layer,color=7)
    except Exception:
        layer=base_layer
    lw = _nearest_dxf_lineweight(cable.line_width)
    attrs={"layer": layer, "color": 256, "lineweight": lw}
    style=normalize_cable_line_style(getattr(cable,"line_style",DEFAULT_CABLE_LINE_STYLE))
    lt_name={"dash":"DASHED","dot":"DOT","dashdot":"DASHDOT"}.get(style)
    if lt_name:
        try:
            table=msp.doc.linetypes
            if lt_name not in table:
                patterns={
                    "DASHED":[0.2,0.1,-0.1],
                    "DOT":[0.1,0.0,-0.1],
                    "DASHDOT":[0.3,0.15,-0.05,0.0,-0.05],
                }
                table.add(lt_name,pattern=patterns[lt_name],description=f"Elplan {lt_name.lower()}")
            attrs["linetype"]=lt_name
        except Exception:
            pass
    ent=msp.add_lwpolyline(cable.points, dxfattribs=attrs)
    try:
        rgb=normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR).lstrip("#")
        ent.rgb=tuple(int(rgb[i:i+2],16) for i in (0,2,4))
    except Exception:
        pass
    text=cable_plan_label(cable)
    if text:
        mid=cable_label_point(cable)
        # Fast CAD-tekststørrelse baseret på tegningsomfang er ikke annotativ, men
        # baggrundsmasken sikrer læsbarhed i DWG/DXF. Editor/PDF bruger screen/page-space.
        ent=msp.add_mtext(text,dxfattribs={"layer":META_LAYER,"color":3,"char_height":55.0})
        ent.set_location(tuple(mid))
        try: ent.set_bg_color("canvas",scale=1.10)
        except Exception: pass
    for rec in cable_section_spec_labels(cable):
        spec=str(rec.get("cable_spec") or "").strip()
        if not spec: continue
        ent=msp.add_mtext(spec,dxfattribs={"layer":META_LAYER,"color":30,"char_height":42.0})
        ent.set_location(tuple(rec.get("point",(0.0,0.0))))
        try: ent.set_bg_color("canvas",scale=1.08)
        except Exception: pass


def add_free_text_to_dxf(msp, item: TextPlacement) -> None:
    if not str(item.text).strip():
        return
    ent=msp.add_text(
        str(item.text),
        height=max(float(item.height),1e-9),
        dxfattribs={
            "layer": FREE_TEXT_LAYER,
            "color": 256,
            "true_color": _true_color_int(item.color),
            "rotation": float(item.rotation),
        },
    )
    ent.set_placement((float(item.x),float(item.y)),align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)



def _primitive_bbox(prim: CADPrimitive):
    """Conservative 2D bbox for a CAD primitive."""
    try:
        if prim.kind == "line":
            x1, y1, x2, y2 = prim.data
            return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        if prim.kind in ("circle", "arc"):
            cx, cy, r = prim.data[:3]
            return cx-r, cy-r, cx+r, cy+r
        if prim.kind == "polyline":
            pts = prim.data
            if not pts:
                return None
            xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
            return min(xs), min(ys), max(xs), max(ys)
        if prim.kind == "point":
            x, y = prim.data
            return x, y, x, y
        if prim.kind == "text":
            x, y, text, h, _rot = prim.data
            w = max(float(h) * 0.6 * len(str(text)), float(h))
            return x, y-float(h)*0.25, x+w, y+float(h)
    except Exception:
        return None
    return None


def print_extents(cad_primitives, placements, cables=None, layer_visibility=None, texts=None,
                  rooms=None, room_labels_visible=True, room_boundaries_visible=False):
    """Return bbox for synlig CAD, el, kabler, tekst og rumlag."""
    boxes = []
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
            continue
        b = _primitive_bbox(prim)
        if b:
            boxes.append(b)
    for pl in placements:
        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol), True):
            continue
        # Brug den faktiske vektorgeometri i stedet for en stor, konservativ
        # cirkel omkring symbolet. Den gamle +/- 1,9 * size-boks kunne give
        # meget store tomme margener i PDF/udskrift, især når et symbol lå
        # tæt ved tegningens yderkant.
        x1,y1,x2,y2=symbol_local_bbox(pl.symbol,float(pl.size))
        corners=[rotate_point(x1,y1,pl.rotation),rotate_point(x1,y2,pl.rotation),
                 rotate_point(x2,y1,pl.rotation),rotate_point(x2,y2,pl.rotation)]
        xs=[pl.x+q[0] for q in corners]; ys=[pl.y+q[1] for q in corners]
        boxes.append((min(xs),min(ys),max(xs),max(ys)))
    for cable in cables or []:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        if cable.points:
            xs=[float(q[0]) for q in cable.points]; ys=[float(q[1]) for q in cable.points]
            boxes.append((min(xs),min(ys),max(xs),max(ys)))
    for item in texts or []:
        if layer_visibility is not None and not layer_visibility.get(FREE_TEXT_LAYER, True):
            continue
        h=max(float(item.height),1.0); w=max(h*.6*len(str(item.text)),h)
        # konservativ bbox, også ved rotation
        r=.55*math.hypot(w,h)
        boxes.append((item.x-r,item.y-r,item.x+r,item.y+r))
    room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
    if room_layer_visible:
        for room in rooms or []:
            if room_boundaries_visible:
                pts=list(getattr(room,"points",[]) or [])
                if pts:
                    xs=[float(q[0]) for q in pts]; ys=[float(q[1]) for q in pts]
                    boxes.append((min(xs),min(ys),max(xs),max(ys)))
            if room_labels_visible:
                # Rumnavne er kosmetisk page-space tekst. Ankerpunktet er nok
                # til at få en eventuelt frit flyttet tekst med i helplansudsnittet.
                x=float(getattr(room,"label_x",0.0)); y=float(getattr(room,"label_y",0.0))
                boxes.append((x,y,x,y))
    if not boxes:
        return (0.0, 0.0, 1000.0, 1000.0)
    xmin=min(b[0] for b in boxes); ymin=min(b[1] for b in boxes)
    xmax=max(b[2] for b in boxes); ymax=max(b[3] for b in boxes)
    if xmax <= xmin: xmax = xmin + 1.0
    if ymax <= ymin: ymax = ymin + 1.0
    return xmin, ymin, xmax, ymax


def _quantile(values, q: float):
    vals=sorted(float(v) for v in values)
    if not vals:return 0.0
    if len(vals)==1:return vals[0]
    pos=max(0.0,min(1.0,float(q)))*(len(vals)-1)
    lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return vals[lo]
    t=pos-lo
    return vals[lo]*(1.0-t)+vals[hi]*t




def _robust_center_range(values, factor: float = 3.0):
    vals=sorted(float(v) for v in values)
    if not vals:
        return 0.0, 0.0
    if len(vals)==1:
        return vals[0], vals[0]
    q1=_quantile(vals,0.25); q3=_quantile(vals,0.75)
    iqr=max(q3-q1,1e-9)
    return q1-factor*iqr, q3+factor*iqr

def fit_view_extents(cad_primitives, placements=None, cables=None, layer_visibility=None, texts=None):
    """Robuste extents til skærmens 'Tilpas visning'.

    Find den dominerende tegningsklynge i stedet for blot at bruge modelspace-
    extents. DWG-filer kan indeholde title blocks, konstruktionselementer,
    referencegeometri eller tekst langt fra selve plantegningen. De elementer
    må ikke få huset til at blive mikroskopisk i editoren. PDF/DWG/DXF-eksport
    påvirkes ikke af denne filtrering.
    """
    geom=[]; text_boxes=[]
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer,True):
            continue
        if prim.kind=="point":
            continue
        b=_primitive_bbox(prim)
        if not b:
            continue
        if prim.kind=="text":
            text_boxes.append(b)
        else:
            geom.append(b)

    if not geom:
        base=print_extents(cad_primitives,placements or [],cables or [],layer_visibility,texts or [])
    else:
        centers=[((b[0]+b[2])*.5,(b[1]+b[3])*.5,b) for b in geom]
        xs=[q[0] for q in centers]; ys=[q[1] for q in centers]
        mx=_quantile(xs,.5); my=_quantile(ys,.5)
        madx=_quantile([abs(x-mx) for x in xs],.5)
        mady=_quantile([abs(y-my) for y in ys],.5)
        # 10-90 %-spændet er fallback for planer, hvor mange centre ligger på
        # samme X/Y. 6 robuste sigma bevarer normal plantegningsgeometri, men
        # fjerner typisk objekter mange rum-/bygningsbredder væk.
        sx=max(madx*1.4826,(_quantile(xs,.90)-_quantile(xs,.10))/2.6,1e-9)
        sy=max(mady*1.4826,(_quantile(ys,.90)-_quantile(ys,.10))/2.6,1e-9)
        dominant=[b for cx,cy,b in centers if abs(cx-mx)<=6.0*sx and abs(cy-my)<=6.0*sy]
        if len(dominant)<max(6,int(len(geom)*.25)):
            dominant=list(geom)

        # En stor tegningsramme kan have centrum midt i huset og derfor bestå
        # centerfilteret. Fjern kun meget ekstreme enkeltprimitiver ift. 90 %-
        # størrelsen; normale lange ydervægge bevares.
        widths=[max(0.0,b[2]-b[0]) for b in dominant]
        heights=[max(0.0,b[3]-b[1]) for b in dominant]
        w90=max(_quantile(widths,.90),1e-9); h90=max(_quantile(heights,.90),1e-9)
        filtered=[b for b in dominant if (b[2]-b[0])<=w90*6.0 and (b[3]-b[1])<=h90*6.0]
        if len(filtered)>=max(6,int(len(dominant)*.85)):
            dominant=filtered

        base=(min(b[0] for b in dominant),min(b[1] for b in dominant),
              max(b[2] for b in dominant),max(b[3] for b in dominant))

        # Geninddrag geometri tæt ved den fundne hovedtegning, så ydervægge,
        # vinduer og døre ikke bliver klippet af statistikken.
        bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-9); bh=max(by2-by1,1e-9)
        guard=(bx1-bw*.05,by1-bh*.05,bx2+bw*.05,by2+bh*.05)
        nearby=[]
        for b in geom:
            cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
            if guard[0]<=cx<=guard[2] and guard[1]<=cy<=guard[3]:
                nearby.append(b)
        if nearby:
            base=(min([base[0]]+[b[0] for b in nearby]),min([base[1]]+[b[1] for b in nearby]),
                  max([base[2]]+[b[2] for b in nearby]),max([base[3]]+[b[3] for b in nearby]))

        # Kun tekst, der faktisk hører til området omkring hovedtegningen,
        # må påvirke skærm-fit.
        bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-9); bh=max(by2-by1,1e-9)
        tguard=(bx1-bw*.035,by1-bh*.035,bx2+bw*.035,by2+bh*.035)
        nearby=[]
        for b in text_boxes:
            cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
            if tguard[0]<=cx<=tguard[2] and tguard[1]<=cy<=tguard[3]:
                nearby.append(b)
        if nearby:
            base=(min([base[0]]+[b[0] for b in nearby]),min([base[1]]+[b[1] for b in nearby]),
                  max([base[2]]+[b[2] for b in nearby]),max([base[3]]+[b[3] for b in nearby]))

    # Egne el-objekter medtages kun, når de ligger tæt ved hovedtegningen.
    bx1,by1,bx2,by2=base; bw=max(bx2-bx1,1e-12); bh=max(by2-by1,1e-12)
    guard=(bx1-bw*.10,by1-bh*.10,bx2+bw*.10,by2+bh*.10)
    extras=[]
    for pl in placements or []:
        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):
            continue
        r=max(float(pl.size),1.0)*1.25
        b=(pl.x-r,pl.y-r,pl.x+r,pl.y+r)
        if guard[0]<=pl.x<=guard[2] and guard[1]<=pl.y<=guard[3]:
            extras.append(b)
    for cable in cables or []:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        if not cable.points:
            continue
        xs=[float(q[0]) for q in cable.points]; ys=[float(q[1]) for q in cable.points]
        b=(min(xs),min(ys),max(xs),max(ys)); cx=(b[0]+b[2])*.5; cy=(b[1]+b[3])*.5
        if guard[0]<=cx<=guard[2] and guard[1]<=cy<=guard[3]:
            extras.append(b)
    for item in texts or []:
        if layer_visibility is not None and not layer_visibility.get(FREE_TEXT_LAYER,True):continue
        if guard[0]<=item.x<=guard[2] and guard[1]<=item.y<=guard[3]:
            h=max(float(item.height),1.0); w=max(h*.6*len(str(item.text)),h); r=.55*math.hypot(w,h)
            extras.append((item.x-r,item.y-r,item.x+r,item.y+r))
    if extras:
        base=(min([base[0]]+[b[0] for b in extras]),min([base[1]]+[b[1] for b in extras]),
              max([base[2]]+[b[2] for b in extras]),max([base[3]]+[b[3] for b in extras]))
    if base[2]<=base[0]: base=(base[0],base[1],base[0]+1.0,base[3])
    if base[3]<=base[1]: base=(base[0],base[1],base[2],base[1]+1.0)
    return base


def crop_extents_to_aspect(extents, target_ratio: float):
    """Center-crop et CAD-område til et bestemt bredde/højde-forhold.

    Bruges for *Aktuel visning*: papir og skærm har sjældent samme aspekt.
    Hvis hele skærmviewporten blot skaleres med ``min(sx, sy)``, opstår store
    hvide felter på PDF'en. Et lille symmetrisk crop bevarer centrum/zoom og
    lader den viste plan fylde det valgte papir uden geometrisk forvrængning.
    """
    xmin,ymin,xmax,ymax=(float(v) for v in extents)
    w=max(xmax-xmin,1e-12); h=max(ymax-ymin,1e-12)
    target=max(float(target_ratio),1e-12)
    ratio=w/h
    cx=(xmin+xmax)*.5; cy=(ymin+ymax)*.5
    if ratio>target:
        # Viewporten er bredere end papiret: beskær lige meget i venstre/højre.
        nw=h*target
        return (cx-nw*.5,ymin,cx+nw*.5,ymax)
    if ratio<target:
        # Viewporten er højere/smallere end papiret: beskær top/bund.
        nh=w/target
        return (xmin,cy-nh*.5,xmax,cy+nh*.5)
    return (xmin,ymin,xmax,ymax)


def page_layout(extents, paper="A4", orientation="Auto", margin_mm=PRINT_MARGIN_MM, fill_page=False):
    """Beregn fælles PDF-layout og det effektive CAD-udsnit.

    ``fill_page=True`` bruges til *Aktuel visning* og center-cropper kun det
    nødvendige for at matche papirets disponible aspekt. Hele tegningen bruger
    fortsat fit-inside, så intet af den valgte geometri beskæres.
    """
    page=resolve_page_size(paper,orientation,extents)
    pw,ph=page
    margin=float(margin_mm)/25.4*72.0
    avail_w=max(1e-9,pw-2*margin); avail_h=max(1e-9,ph-2*margin)
    effective=tuple(float(v) for v in extents)
    if fill_page:
        effective=crop_extents_to_aspect(effective,avail_w/avail_h)
    xmin,ymin,xmax,ymax=effective
    dw=max(xmax-xmin,1e-12); dh=max(ymax-ymin,1e-12)
    scale=min(avail_w/dw,avail_h/dh)
    draw_w=dw*scale; draw_h=dh*scale
    ox=(pw-draw_w)/2.0; oy=(ph-draw_h)/2.0
    return page,effective,scale,ox,oy,draw_w,draw_h,margin


def resolve_page_size(paper: str, orientation: str, extents):
    base = A3 if str(paper).upper() == "A3" else A4
    if orientation == "Landskab":
        return landscape(base)
    if orientation == "Portræt":
        return portrait(base)
    xmin, ymin, xmax, ymax = extents
    drawing_ratio = max((xmax-xmin) / max(ymax-ymin, 1e-12), 1e-12)
    portrait_ratio = portrait(base)[0] / portrait(base)[1]
    return landscape(base) if drawing_ratio > portrait_ratio else portrait(base)


def export_vector_pdf(path: str | Path, cad_primitives, placements, cables=None,
                      layer_visibility=None, paper="A4", orientation="Auto",
                      annotation_style=DEFAULT_ANNOTATION_STYLE, annotation_font_size=DEFAULT_ANNOTATION_FONT_SIZE,
                      extents_override=None, texts=None, fill_page=False, cad_opacity=1.0,
                      annotation_mode="Auto", rooms=None, room_labels_visible=True,
                      room_codes_visible=False, room_boundaries_visible=False) -> None:
    """Write the current plan as a one-page, vector PDF.

    PDF-output uses the same text scaling rules as the Qt editor.  Earlier
    versions mixed world-scaled text, fixed PDF-point text and hard clamps;
    that made room text, CAD text, cable labels and symbol-internal text look
    very different from the on-screen drawing.
    """
    cables = cables or []
    texts = texts or []
    rooms = list(rooms or [])
    placements = list(placements or [])
    ext = tuple(extents_override) if extents_override is not None else print_extents(
        cad_primitives,placements,cables,layer_visibility,texts,rooms,
        room_labels_visible,room_boundaries_visible
    )
    page,effective_ext,scale,ox,oy,draw_w,draw_h,margin = page_layout(
        ext,paper,orientation,PRINT_MARGIN_MM,fill_page=bool(fill_page)
    )
    pw,ph=page
    xmin,ymin,xmax,ymax=effective_ext
    view_scale=output_equivalent_view_scale(scale)
    mode=str(annotation_mode or "Auto")
    if mode not in ("Auto","Tydelig","Minimal","Skjult"):
        mode="Auto"

    def mappt(x, y):
        return ox+(float(x)-xmin)*scale, oy+(float(y)-ymin)*scale

    def alpha_color(hex_value: str, alpha: float=1.0):
        h=normalize_hex_color(hex_value).lstrip("#")
        a=max(0.0,min(1.0,float(alpha)))
        return colors.Color(int(h[0:2],16)/255.0,int(h[2:4],16)/255.0,int(h[4:6],16)/255.0,alpha=a)

    def pdf_text(value) -> str:
        # ReportLab's built-in Helvetica uses WinAnsi. Keep Danish characters,
        # but replace symbols outside that encoding deterministically.
        txt=str(value or "").replace("↳","->").replace("→","->")
        return txt.encode("cp1252","replace").decode("cp1252")

    try:
        cad_opacity=max(0.0,min(1.0,float(cad_opacity)))
    except Exception:
        cad_opacity=1.0
    cad_gray=int(round(255.0*(1.0-cad_opacity)))
    cad_hex=f"#{cad_gray:02x}{cad_gray:02x}{cad_gray:02x}"
    cad_pdf_color=colors.HexColor(cad_hex)

    placement_by_uid={str(getattr(pl,"uid","") or ""):pl for pl in placements}

    def compact_combo_group(pl):
        groups=_split_csv_parts(getattr(pl,"switch_group",""), len(combo_modules(pl.symbol)))
        parts=[]
        for i,group in enumerate(groups,1):
            if group: parts.append(f"A{i}:{group}")
        socket=str(getattr(pl,"socket_group","") or "").strip()
        if socket: parts.append(f"S:{socket}")
        return "  ".join(parts)

    def combo_detail_lines(pl):
        mods=combo_modules(pl.symbol)
        groups=_split_csv_parts(getattr(pl,"switch_group",""),len(mods))
        labels=_split_csv_parts(getattr(pl,"switch_label",""),len(mods))
        out=[]
        for i,(group,label) in enumerate(zip(groups,labels),1):
            bits=[x for x in (group,label) if x]
            if bits: out.append(f"A{i}: " + " · ".join(bits))
        sg=str(getattr(pl,"socket_group","") or "").strip()
        sl=str(getattr(pl,"socket_label","") or "").strip()
        bits=[x for x in (sg,sl) if x]
        if bits: out.append("S: " + " · ".join(bits))
        return out

    def spot_parent_text(pl):
        if getattr(pl,"symbol","")!="spot": return ""
        uid=str(getattr(pl,"parent_light_uid","") or "")
        if not uid: return ""
        parent=placement_by_uid.get(uid)
        if parent is None: return "↳ Lampested ?"
        ident=str(getattr(parent,"group","") or getattr(parent,"label","") or "Lampested").strip()
        output=light_output_by_id(parent,getattr(pl,"parent_light_output_id","") or "")
        suffix=f" / {output.get('name')}" if len(light_output_records(parent))>1 else ""
        return f"↳ {ident}{suffix}"

    def annotation_content(pl):
        if mode=="Skjult": return "","","",[],""
        if mode=="Auto" and view_scale<0.055:
            return "","","",[],""
        assoc=association_display(pl)
        if association_role(pl.symbol)=="switch":
            assoc=""
        group=str(getattr(pl,"group","") or "").strip()
        label=str(getattr(pl,"label","") or "").strip()
        primary=group or label
        secondary=label if group and label else ""
        if mode=="Minimal":
            secondary=""; assoc=""
        show_secondary=bool(secondary) and (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.145))
        show_assoc=bool(assoc) and (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.055))
        extra=[]
        if is_combo_symbol(pl.symbol) and normalize_combo_label_mode(getattr(pl,"label_mode","Fælles"))=="Opdelt":
            if mode=="Tydelig" or (mode=="Auto" and view_scale>=0.20):
                extra=combo_detail_lines(pl); primary=""; secondary=""
            else:
                primary=compact_combo_group(pl) or primary; secondary=""
        spot=spot_parent_text(pl)
        if not (mode=="Tydelig" or (mode=="Auto" and view_scale>=0.21)):
            spot=""
        if mode=="Minimal": spot=""
        return primary,(secondary if show_secondary else ""),(assoc if show_assoc else ""),extra,spot

    c = pdfcanvas.Canvas(str(path), pagesize=page, pageCompression=1)
    c.setTitle("Elplan")
    c.setLineCap(1); c.setLineJoin(1)
    c.saveState()
    if extents_override is not None or fill_page:
        clip = c.beginPath(); clip.rect(margin, margin, pw-2*margin, ph-2*margin)
        c.clipPath(clip, stroke=0, fill=0)

    # Architectural CAD.
    c.setStrokeColor(cad_pdf_color); c.setFillColor(cad_pdf_color); c.setLineWidth(0.45)
    for prim in cad_primitives:
        if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
            continue
        try:
            if prim.kind == "line":
                x1,y1,x2,y2=prim.data; c.line(*mappt(x1,y1),*mappt(x2,y2))
            elif prim.kind == "circle":
                cx,cy,r=prim.data; x,y=mappt(cx-r,cy-r); x2,y2=mappt(cx+r,cy+r); c.ellipse(x,y,x2,y2,stroke=1,fill=0)
            elif prim.kind == "arc":
                cx,cy,r,a1,a2=prim.data; x,y=mappt(cx-r,cy-r); x2,y2=mappt(cx+r,cy+r)
                delta=(a2-a1)%360 or 360; c.arc(x,y,x2,y2,startAng=a1,extent=delta)
            elif prim.kind == "polyline":
                pts=list(prim.data)
                if len(pts)>=2:
                    pp=c.beginPath(); pp.moveTo(*mappt(*pts[0]))
                    for q in pts[1:]: pp.lineTo(*mappt(*q))
                    c.drawPath(pp,stroke=1,fill=0)
            elif prim.kind == "point":
                x,y=mappt(*prim.data); c.circle(x,y,0.8,stroke=1,fill=1)
            elif prim.kind == "text":
                x,y,t,h,rot=prim.data; sx0,sy0=mappt(x,y)
                fs=output_cad_text_font_size(h,scale)
                c.saveState(); c.translate(sx0,sy0); c.rotate(float(rot)); c.setFont("Helvetica",fs)
                try: c.drawString(0,0,str(t))
                except Exception: c.drawString(0,0,str(t).encode("cp1252","replace").decode("cp1252"))
                c.restoreState()
        except Exception:
            continue

    # Rumafgrænsninger er et selvstændigt lag og følger deres eget Vis-valg.
    # De tegnes under installationen, ligesom i editoren.
    room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
    if room_layer_visible and room_boundaries_visible:
        for room in rooms:
            pts=list(getattr(room,"points",[]) or [])
            if len(pts)<2:continue
            color=normalize_hex_color(getattr(room,"color","#0f766e"),"#0f766e")
            c.setStrokeColor(alpha_color(color,.72)); c.setFillColor(alpha_color(color,.05)); c.setLineWidth(1.0); c.setDash(5,3)
            pp=c.beginPath(); pp.moveTo(*mappt(*pts[0]))
            for q in pts[1:]:pp.lineTo(*mappt(*q))
            if len(pts)>=3:pp.close()
            c.drawPath(pp,stroke=1,fill=1 if len(pts)>=3 else 0)
        c.setDash()

    # Electrical symbols. Internal symbol text follows Qt's 0.60 scale factor.
    def _placement_page_bounds(pl):
        pts=[]
        def add(lx,ly):
            rx,ry=rotate_point(float(lx),float(ly),pl.rotation); pts.append(mappt(pl.x+rx,pl.y+ry))
        for prim in symbol_primitives(pl.symbol,pl.size):
            typ=prim[0]
            if typ=="line": add(prim[1],prim[2]); add(prim[3],prim[4])
            elif typ in {"circle","arc"}:
                _t,cx,cy,r,*_=prim
                for dx in (-r,r):
                    for dy in (-r,r): add(cx+dx,cy+dy)
            elif typ=="polyline":
                for qx,qy in prim[1]: add(qx,qy)
            elif typ in {"text","upright_text"}: add(prim[1],prim[2])
        if not pts:
            q=mappt(pl.x,pl.y); return (q[0],q[1],q[0],q[1])
        xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
        return (min(xs),min(ys),max(xs),max(ys))
    placement_page_bounds={getattr(pl,"uid",id(pl)):_placement_page_bounds(pl) for pl in placements}
    for pl in placements:
        layer=symbol_layer(pl.symbol)
        if layer_visibility is not None and not layer_visibility.get(layer, True):
            continue
        symbol_color = colors.HexColor(normalize_hex_color(pl.color))
        c.setStrokeColor(symbol_color); c.setFillColor(symbol_color)
        c.setLineWidth(max(0.1, float(pl.line_width) / 25.4 * 72.0))
        def world(lx,ly):
            rx,ry=rotate_point(lx,ly,pl.rotation); return pl.x+rx, pl.y+ry
        for prim in symbol_primitives(pl.symbol,pl.size):
            typ=prim[0]
            try:
                if typ=="line":
                    c.line(*mappt(*world(prim[1],prim[2])),*mappt(*world(prim[3],prim[4])))
                elif typ=="circle":
                    _,cx,cy,r=prim; wc=world(cx,cy); x,y=mappt(wc[0]-r,wc[1]-r); x2,y2=mappt(wc[0]+r,wc[1]+r); c.ellipse(x,y,x2,y2,stroke=1,fill=0)
                elif typ=="arc":
                    _,cx,cy,r,a1,a2=prim; wc=world(cx,cy); x,y=mappt(wc[0]-r,wc[1]-r); x2,y2=mappt(wc[0]+r,wc[1]+r)
                    c.arc(x,y,x2,y2,startAng=a1+pl.rotation,extent=a2-a1)
                elif typ=="polyline":
                    pts=[mappt(*world(x,y)) for x,y in prim[1]]
                    if len(pts)>=2:
                        pp=c.beginPath(); pp.moveTo(*pts[0])
                        for q in pts[1:]: pp.lineTo(*q)
                        c.drawPath(pp,stroke=1,fill=0)
                elif typ in {"text","upright_text"}:
                    _,x,y,t,h=prim; wx,wy=world(x,y); px,py=mappt(wx,wy); fs=output_symbol_text_font_size(h,scale)
                    text_rotation=0.0 if typ=="upright_text" else pl.rotation
                    c.saveState(); c.translate(px,py); c.rotate(text_rotation); c.setFont("Helvetica-Bold",fs); c.drawCentredString(0,-fs*0.32,str(t)); c.restoreState()
            except Exception:
                continue

    # Free text is deliberately page-space text in the editor (ItemIgnoresTransformations).
    # Therefore its PDF font size must NOT be multiplied by the CAD/page scale.
    if layer_visibility is None or layer_visibility.get(FREE_TEXT_LAYER, True):
        for item in texts:
            if not str(item.text).strip(): continue
            px,py=mappt(float(item.x),float(item.y)); fs=output_free_text_font_size(item.height)
            c.saveState(); c.translate(px,py); c.rotate(float(item.rotation)); c.setFillColor(colors.HexColor(normalize_hex_color(item.color))); c.setFont("Helvetica",fs)
            try: c.drawString(0,-fs*0.88,str(item.text))
            except Exception: c.drawString(0,-fs*0.88,str(item.text).encode("cp1252","replace").decode("cp1252"))
            c.restoreState()

    # Cables and wires. Parallel routes are separated only visually; the saved
    # logical geometry and the cable-length calculation remain untouched.
    c.setFillColor(colors.HexColor("#08752c"))
    visible_cables=[cb for cb in cables if cable_visible_in_layers(cb,layer_visibility)]
    cable_visuals=cable_visual_paths(visible_cables,5.0/max(scale,1e-12),fan_length=12.0/max(scale,1e-12))
    for cable in cables:
        if not cable_visible_in_layers(cable,layer_visibility):
            continue
        display_points=cable_visuals.get(id(cable),cable.points)
        if len(display_points) < 2:
            continue
        c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))
        c.setLineWidth(max(0.1, float(cable.line_width) / 25.4 * 72.0))
        style=normalize_cable_line_style(getattr(cable,"line_style",DEFAULT_CABLE_LINE_STYLE))
        if style=="dash": c.setDash(6,4)
        elif style=="dot": c.setDash(1.2,3.0)
        elif style=="dashdot": c.setDash([6,3,1.2,3],0)
        else: c.setDash()
        pts=[mappt(float(x),float(y)) for x,y in display_points]
        pp=c.beginPath(); pp.moveTo(*pts[0])
        for q in pts[1:]: pp.lineTo(*q)
        c.drawPath(pp,stroke=1,fill=0)
        text=cable_plan_label(cable)
        if text and mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
            wx,wy=polyline_label_point(display_points); mx,my=mappt(wx,wy)
            fs=8.0; pad=1.4; dx=5.25; dy=12.75
            tw=stringWidth(text,"Helvetica-Bold",fs)
            c.setFillColor(colors.white); c.rect(mx+dx-pad,my+dy-fs*.25-pad,tw+2*pad,fs+2*pad+.5,stroke=0,fill=1)
            c.setFillColor(colors.HexColor("#0f6a3e")); c.setFont("Helvetica-Bold",fs); c.drawString(mx+dx,my+dy,text)
            c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))
        if mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
            for rec in cable_section_spec_labels(cable):
                spec=str(rec.get("cable_spec") or "").strip()
                if not spec: continue
                wx,wy=rec.get("point",(0.0,0.0)); mx,my=mappt(wx,wy)
                fs=7.0; pad=1.2; dx=5.0; dy=-3.0
                tw=stringWidth(spec,"Helvetica-Bold",fs)
                c.setFillColor(colors.white); c.rect(mx+dx-pad,my+dy-fs*.25-pad,tw+2*pad,fs+2*pad+.5,stroke=0,fill=1)
                c.setFillColor(colors.HexColor("#7c3f00")); c.setFont("Helvetica-Bold",fs); c.drawString(mx+dx,my+dy,spec)
                c.setStrokeColor(colors.HexColor(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR)))

    # Rumnavne er kosmetisk page-space tekst og skal derfor ikke skaleres med
    # CAD-tegningen. Rummærkning/ID er bevidst et separat valg.
    if room_layer_visible and room_labels_visible:
        fs=9.0
        for room in rooms:
            label=pdf_text(room_output_label(room,room_codes_visible))
            if not label:continue
            px,py=mappt(float(getattr(room,"label_x",0.0)),float(getattr(room,"label_y",0.0)))
            c.setFillColor(colors.HexColor(normalize_hex_color(getattr(room,"color","#0f766e"),"#0f766e")))
            c.setFont("Helvetica-Bold",fs); c.drawString(px,py-fs*.88,label)

    # Metadata/relations use the same semantic zoom and font profile as the Qt editor.
    if mode!="Skjult" and (layer_visibility is None or layer_visibility.get(META_LAYER, True)):
        profile=annotation_visual_profile(mode,view_scale,False)

        def draw_plain(text,x,y,font_name,font_size,color):
            text=pdf_text(text)
            c.setFillColor(alpha_color(color,0.90)); c.setFont(font_name,font_size); c.drawString(x,y,text)
            return stringWidth(text,font_name,font_size),font_size*1.18

        def draw_chip(text,x,y,font_name,font_size,fg,fill,border,pad):
            text=pdf_text(text)
            pxpad,pypad=pad
            tw=stringWidth(text,font_name,font_size)
            w=max(20.0,tw+2*pxpad); h=font_size*1.18+2*pypad
            c.setFillColor(alpha_color(fill,0.94)); c.setStrokeColor(alpha_color(border,0.88)); c.setLineWidth(0.55)
            c.roundRect(x,y,w,h,4,stroke=1,fill=1)
            c.setFillColor(alpha_color(fg,0.96)); c.setFont(font_name,font_size); c.drawString(x+pxpad,y+pypad+font_size*.14,text)
            return w,h

        def plain_size(text,font_name,font_size):
            return stringWidth(pdf_text(text),font_name,font_size),font_size*1.18

        def chip_size(text,font_name,font_size,pad):
            pxpad,pypad=pad
            return max(20.0,stringWidth(pdf_text(text),font_name,font_size)+2*pxpad),font_size*1.18+2*pypad

        def annotation_block_size(primary,secondary,assoc,extra,spot):
            width=0.0; height=0.0; row_h=0.0; row_w=0.0
            quiet_primary=(mode=="Minimal" or (mode=="Auto" and view_scale<0.145))
            if extra:
                fs=profile["primary"]*.90
                for line in extra:
                    w,h=chip_size(str(line),"Helvetica-Bold",fs,profile["pad_small"]); width=max(width,w); height+=h+profile["row_gap"]
                if extra: height=max(0.0,height-profile["row_gap"])
            else:
                if primary:
                    fs=profile["primary"]
                    w,h=plain_size(primary,"Helvetica-Bold",fs) if quiet_primary else chip_size(primary,"Helvetica-Bold",fs,profile["pad_primary"])
                    row_w+=w; row_h=max(row_h,h)
                if secondary:
                    fs=profile["secondary"]; w,h=chip_size(secondary,"Helvetica",fs,profile["pad_small"])
                    if row_w: row_w+=profile["gap"]
                    row_w+=w; row_h=max(row_h,h)
                if row_w: width=max(width,row_w); height+=row_h
            if assoc:
                if height: height+=profile["row_gap"]
                fs=max(4.8,profile["assoc"]*.90) if (mode=="Auto" and view_scale<0.145) else profile["assoc"]
                w,h=plain_size(assoc,"Helvetica-Bold",fs) if (mode=="Auto" and view_scale<0.145) else chip_size(assoc,"Helvetica-Bold",fs,profile["pad_small"])
                width=max(width,w); height+=h
            if spot:
                if height: height+=profile["row_gap"]
                fs=profile["spot"]; w,h=chip_size(spot,"Helvetica",fs,profile["pad_small"]); width=max(width,w); height+=h
            return max(1.0,width),max(1.0,height)

        symbol_blockers=[expand_rect(bounds,1.4) for bounds in placement_page_bounds.values()]
        metadata_occupied=[]
        page_container=(margin*.55,margin*.55,pw-margin*.55,ph-margin*.55)

        for pl in placements:
            if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):
                continue
            primary,secondary,assoc,extra,spot=annotation_content(pl)
            if not (primary or secondary or assoc or extra or spot):
                continue
            # All automatic metadata shares one collision map. Symbol silhouettes are
            # hard blockers; already placed group/marking/relation labels reserve space.
            bounds=placement_page_bounds.get(getattr(pl,"uid",id(pl)),mappt(pl.x,pl.y)*2)
            anchor=mappt(pl.x,pl.y); block_w,block_h=annotation_block_size(primary,secondary,assoc,extra,spot)
            tx,ty,_side,occupied_rect=choose_label_origin(
                anchor,bounds,block_w,block_h,blockers=symbol_blockers,occupied=metadata_occupied,
                preferred="right",gap=4.8,collision_padding=1.25,container=page_container
            )
            metadata_occupied.append(occupied_rect)
            x=tx; y=ty; row_h=0.0
            quiet_primary=(mode=="Minimal" or (mode=="Auto" and view_scale<0.145))
            if extra:
                font_size=profile["primary"]*.90
                for line in extra:
                    _w,h=draw_chip(str(line),tx,y,"Helvetica-Bold",font_size,"#35564a","#ffffff","#aebeb6",profile["pad_small"])
                    y+=h+profile["row_gap"]
            else:
                if primary:
                    fs=profile["primary"]
                    if quiet_primary:
                        w,h=draw_plain(primary,x,y,"Helvetica-Bold",fs,"#2d5242")
                    else:
                        w,h=draw_chip(primary,x,y,"Helvetica-Bold",fs,"#174e39","#ffffff","#a0b4a9",profile["pad_primary"])
                    x+=w+profile["gap"]; row_h=max(row_h,h)
                if secondary:
                    fs=profile["secondary"]
                    w,h=draw_chip(secondary,x,y,"Helvetica",fs,"#69736f","#f8f9f9","#cfd5d2",profile["pad_small"])
                    x+=w; row_h=max(row_h,h)
                if primary or secondary:
                    y+=row_h+profile["row_gap"]
            if assoc:
                fs=max(4.8,profile["assoc"]*.90) if (mode=="Auto" and view_scale<0.145) else profile["assoc"]
                if mode=="Auto" and view_scale<0.145:
                    _w,h=draw_plain(assoc,tx,y,"Helvetica-Bold",fs,"#31608b")
                else:
                    _w,h=draw_chip(assoc,tx,y,"Helvetica-Bold",fs,"#31608b","#edf5fc","#87abca",profile["pad_small"])
                y+=h+profile["row_gap"]
            if spot:
                fs=profile["spot"]
                _w,h=draw_chip(spot,tx,y,"Helvetica",fs,"#2b6b68","#edf8f7","#97c2bf",profile["pad_small"])
                y+=h

        # Switch a/b/c labels are anchored to the physical module instead of being
        # collapsed into one combined label at the whole combo symbol.
        if mode not in ("Minimal","Skjult") and not (mode=="Auto" and view_scale<0.055):
            overview=(mode=="Auto" and view_scale<0.145)
            tag=output_switch_association_tag_profile(overview)
            fs=float(tag["font_size"]); pad_x=float(tag["pad_x"]); pad_y=float(tag["pad_y"])
            for pl in placements:
                if association_role(pl.symbol)!="switch": continue
                if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True): continue
                channels=association_channel_letters(pl)
                for rec in association_module_layout(pl.symbol,pl.size):
                    _module_no,_base,lx,ly,_radius,indices=rec
                    letters=[channels[i] for i in indices if i < len(channels) and channels[i]]
                    if not letters: continue
                    text=pdf_text(" · ".join(letters))
                    wx,wy=rotate_point(lx,ly,pl.rotation); wx+=pl.x; wy+=pl.y
                    ax,ay=mappt(wx,wy)
                    tw=stringWidth(text,"Helvetica-Bold",fs); h=fs*1.18+2*pad_y; w=max(float(tag["min_width"]),tw+2*pad_x)
                    bounds=placement_page_bounds.get(getattr(pl,"uid",id(pl)),(ax,ay,ax,ay))
                    left,bottom,right,top=map(float,bounds); preferred="below" if (right-left)>(top-bottom)*1.12 else "right"
                    tx,ty,_side,occupied_rect=choose_label_origin(
                        (ax,ay),bounds,w,h,blockers=symbol_blockers,occupied=metadata_occupied,
                        preferred=preferred,gap=3.8 if overview else 4.6,collision_padding=1.15,container=page_container
                    )
                    metadata_occupied.append(occupied_rect)
                    c.setFillColor(alpha_color("#f5faff",float(tag["fill_alpha"])))
                    c.setStrokeColor(alpha_color("#7aa4c7",float(tag["border_alpha"])))
                    c.setLineWidth(float(tag["line_width"]))
                    c.roundRect(tx,ty,w,h,float(tag["radius"]),stroke=1,fill=1)
                    c.setFillColor(alpha_color("#2d5b84",float(tag["text_alpha"])))
                    c.setFont("Helvetica-Bold",fs); c.drawString(tx+pad_x,ty+pad_y+fs*.14,text)

    c.restoreState()
    c.showPage(); c.save()


def print_vector_windows(cad_primitives, placements, cables=None, layer_visibility=None,
                         paper="A4", orientation="Auto",
                         annotation_style=DEFAULT_ANNOTATION_STYLE,
                         annotation_font_size=DEFAULT_ANNOTATION_FONT_SIZE,
                         extents_override=None, printer_name=None, texts=None, fill_page=False,
                         cad_opacity=1.0, rooms=None, room_labels_visible=True,
                         room_codes_visible=False, room_boundaries_visible=False) -> str:
    """Print planen direkte som Windows GDI-vektorer.

    Tidligere blev en PDF sendt til ``os.startfile(..., "print")``. Den vej lader
    PDF-programmet/printerdriveren vælge papir og ender ofte i A4, selv når PDF'en
    er A3. Her oprettes i stedet en printer-DC med en DEVMODE, hvor A3/A4 og
    orientering sættes eksplicit før jobbet startes.

    Returnerer navnet på den printer, der modtog jobbet.
    """
    if os.name != "nt":
        raise RuntimeError("Direkte Windows-udskrivning er kun tilgængelig på Windows.")

    import pywintypes
    import win32api
    import win32con
    import win32gui
    import win32print

    cables = cables or []
    texts = texts or []
    rooms = list(rooms or [])
    try:
        cad_opacity=max(0.0,min(1.0,float(cad_opacity)))
    except Exception:
        cad_opacity=1.0
    cad_gray=int(round(255.0*(1.0-cad_opacity)))
    cad_hex=f"#{cad_gray:02x}{cad_gray:02x}{cad_gray:02x}"
    ext = tuple(extents_override) if extents_override is not None else print_extents(
        cad_primitives,placements,cables,layer_visibility,texts,rooms,
        room_labels_visible,room_boundaries_visible
    )
    xmin, ymin, xmax, ymax = ext
    if xmax <= xmin or ymax <= ymin:
        raise RuntimeError("Det valgte udskriftsområde er tomt.")

    requested_paper = str(paper).upper()
    paper_code = win32con.DMPAPER_A3 if requested_paper == "A3" else win32con.DMPAPER_A4

    # Auto-orientering følger samme logik som PDF-eksporten.
    page_pts = resolve_page_size(requested_paper, orientation, ext)
    is_landscape = page_pts[0] > page_pts[1]
    orient_code = win32con.DMORIENT_LANDSCAPE if is_landscape else win32con.DMORIENT_PORTRAIT

    pname = printer_name or win32print.GetDefaultPrinter()
    hprinter = None
    hdc = None
    doc_started = False
    page_started = False
    created_objects = []
    try:
        hprinter = win32print.OpenPrinter(pname)
        info = win32print.GetPrinter(hprinter, 2)
        print_processor = info.get("pPrintProcessor") or "winprint"

        # Brug printerens fulde driver-specifikke DEVMODE-størrelse, jf. pywin32s
        # eget print_desktop.py-eksempel. Det er mere robust end at bygge en
        # minimal DEVMODE, som visse drivere afviser.
        dmsize = win32print.DocumentProperties(0, hprinter, pname, None, None, 0)
        driverextra = max(0, int(dmsize) - pywintypes.DEVMODEType().Size)
        dm = pywintypes.DEVMODEType(driverextra)
        win32print.DocumentProperties(0, hprinter, pname, dm, None, win32con.DM_OUT_BUFFER)
        dm.Fields |= win32con.DM_ORIENTATION | win32con.DM_PAPERSIZE | win32con.DM_COPIES
        dm.Orientation = orient_code
        dm.PaperSize = paper_code
        dm.Copies = 1
        result = win32print.DocumentProperties(
            0, hprinter, pname, dm, dm, win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER
        )
        if result < 0:
            raise RuntimeError("Printerdriveren afviste de valgte papirindstillinger.")

        hdc = win32gui.CreateDC(print_processor, pname, dm)
        if not hdc:
            raise RuntimeError("Windows kunne ikke oprette en printerkontekst.")

        dpi_x = max(1, win32print.GetDeviceCaps(hdc, win32con.LOGPIXELSX))
        dpi_y = max(1, win32print.GetDeviceCaps(hdc, win32con.LOGPIXELSY))
        printable_w = max(1, win32print.GetDeviceCaps(hdc, win32con.HORZRES))
        printable_h = max(1, win32print.GetDeviceCaps(hdc, win32con.VERTRES))
        phys_w = max(1, win32print.GetDeviceCaps(hdc, win32con.PHYSICALWIDTH))
        phys_h = max(1, win32print.GetDeviceCaps(hdc, win32con.PHYSICALHEIGHT))

        # Fang den klassiske fejl: driveren har ignoreret A3 og faldet tilbage
        # til A4. Vi måler den fysiske side i stedet for at stole på comboboxen.
        mm_w = phys_w / dpi_x * 25.4
        mm_h = phys_h / dpi_y * 25.4
        short_mm, long_mm = sorted((mm_w, mm_h))
        if requested_paper == "A3" and (short_mm < 270 or long_mm < 390):
            raise RuntimeError(
                f"Printerdriveren skiftede tilbage til ca. {short_mm:.0f}×{long_mm:.0f} mm i stedet for A3. "
                "Kontrollér at den valgte printer faktisk understøtter A3."
            )

        margin_mm = PRINT_MARGIN_MM
        mx = margin_mm / 25.4 * dpi_x
        my = margin_mm / 25.4 * dpi_y
        avail_w = max(1.0, printable_w - 2.0 * mx)
        avail_h = max(1.0, printable_h - 2.0 * my)

        # *Aktuel visning* skal fylde siden på samme måde som PDF'en. Skærmens
        # aspekt og printerens printable område er sjældent identiske, så vi
        # center-cropper kun den overskydende rand før skalering.
        if fill_page:
            physical_ratio=(avail_w/dpi_x)/max(avail_h/dpi_y,1e-12)
            xmin,ymin,xmax,ymax=crop_extents_to_aspect((xmin,ymin,xmax,ymax),physical_ratio)
        dw = xmax - xmin; dh = ymax - ymin
        # Fysisk uniform skalering: samme antal millimeter pr. CAD-enhed i X/Y,
        # også på printere hvor LOGPIXELSX og LOGPIXELSY er forskellige.
        inch_per_unit = min((avail_w / dpi_x) / dw, (avail_h / dpi_y) / dh)
        sx = inch_per_unit * dpi_x
        sy = inch_per_unit * dpi_y
        draw_w = dw * sx; draw_h = dh * sy
        ox = (printable_w - draw_w) / 2.0
        oy = (printable_h - draw_h) / 2.0

        def mappt(x, y):
            return int(round(ox + (float(x) - xmin) * sx)), int(round(oy + (ymax - float(y)) * sy))

        def colorref(value):
            h = normalize_hex_color(value).lstrip("#")
            return win32api.RGB(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

        def select_pen(hex_color, width_mm, line_style="solid"):
            px = max(1, int(round(float(width_mm) / 25.4 * (dpi_x + dpi_y) / 2.0)))
            style=normalize_cable_line_style(line_style)
            ps={"dash":getattr(win32con,"PS_DASH",win32con.PS_SOLID),"dot":getattr(win32con,"PS_DOT",win32con.PS_SOLID),"dashdot":getattr(win32con,"PS_DASHDOT",win32con.PS_SOLID)}.get(style,win32con.PS_SOLID)
            pen = win32gui.CreatePen(ps, px, colorref(hex_color))
            created_objects.append(pen)
            old = win32gui.SelectObject(hdc, pen)
            return old, pen

        def draw_segment(a, b):
            win32gui.MoveToEx(hdc, int(a[0]), int(a[1]))
            win32gui.LineTo(hdc, int(b[0]), int(b[1]))

        def draw_polyline(points):
            pts = list(points)
            if len(pts) < 2:
                return
            a = pts[0]
            win32gui.MoveToEx(hdc, int(a[0]), int(a[1]))
            for q in pts[1:]:
                win32gui.LineTo(hdc, int(q[0]), int(q[1]))

        def arc_world_points(cx, cy, r, a1, a2, transform=lambda x, y:(x, y)):
            delta = (float(a2) - float(a1)) % 360.0
            if abs(delta) < 1e-9:
                delta = 360.0
            n = max(8, int(abs(delta) / 5.0) + 1)
            out=[]
            for i in range(n + 1):
                a = math.radians(float(a1) + delta * i / n)
                x = float(cx) + float(r) * math.cos(a)
                y = float(cy) + float(r) * math.sin(a)
                out.append(transform(x, y))
            return out

        def draw_text_world(x, y, text, h_world, rotation=0.0, color="#111111", bold=False):
            px_h = max(5, int(abs(float(h_world)) * sy * 0.78))
            lf = win32gui.LOGFONT()
            lf.lfHeight = -px_h
            lf.lfWeight = 700 if bold else 400
            lf.lfEscapement = int(round(float(rotation) * 10.0))
            lf.lfOrientation = lf.lfEscapement
            lf.lfFaceName = "Arial"
            font = win32gui.CreateFontIndirect(lf); created_objects.append(font)
            old_font = win32gui.SelectObject(hdc, font)
            try:
                win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
                win32gui.SetTextColor(hdc, colorref(color))
                px, py = mappt(x, y)
                win32gui.TextOut(hdc, px, py - px_h, str(text))
            finally:
                win32gui.SelectObject(hdc, old_font)

        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        old_brush = win32gui.SelectObject(hdc, null_brush)

        win32print.StartDoc(hdc, ("Elplan", None, None, 0)); doc_started = True
        win32print.StartPage(hdc); page_started = True
        try:
            # Arkitekttegning. Dæmpning er neutral grå og gælder kun CAD-baggrunden.
            old_pen, _ = select_pen(cad_hex, 0.16)
            try:
                for prim in cad_primitives:
                    if layer_visibility is not None and not layer_visibility.get(prim.layer, True):
                        continue
                    try:
                        if prim.kind == "line":
                            x1,y1,x2,y2=prim.data; draw_segment(mappt(x1,y1),mappt(x2,y2))
                        elif prim.kind == "circle":
                            cx,cy,r=prim.data; a=mappt(cx-r,cy+r); b=mappt(cx+r,cy-r)
                            win32gui.Ellipse(hdc,min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
                        elif prim.kind == "arc":
                            cx,cy,r,a1,a2=prim.data
                            draw_polyline(mappt(x,y) for x,y in arc_world_points(cx,cy,r,a1,a2))
                        elif prim.kind == "polyline":
                            draw_polyline(mappt(*q) for q in prim.data)
                        elif prim.kind == "point":
                            x,y=mappt(*prim.data); rr=max(1,int((dpi_x+dpi_y)/1200)); win32gui.Ellipse(hdc,x-rr,y-rr,x+rr,y+rr)
                        elif prim.kind == "text":
                            x,y,t,h,rot=prim.data; draw_text_world(x,y,t,h,rot,cad_hex,False)
                    except Exception:
                        continue
            finally:
                win32gui.SelectObject(hdc, old_pen)

            room_layer_visible=layer_visibility is None or layer_visibility.get(ROOM_LAYER,True)
            if room_layer_visible and room_boundaries_visible:
                for room in rooms:
                    pts=list(getattr(room,"points",[]) or [])
                    if len(pts)<2:continue
                    old_pen,_=select_pen(getattr(room,"color","#0f766e"),0.18,"dash")
                    try:
                        mapped=[mappt(*q) for q in pts]
                        if len(pts)>=3:mapped.append(mapped[0])
                        draw_polyline(mapped)
                    finally:win32gui.SelectObject(hdc,old_pen)

            # El-symboler.
            for pl in placements:
                layer=symbol_layer(pl.symbol)
                if layer_visibility is not None and not layer_visibility.get(layer, True):
                    continue
                old_pen, _ = select_pen(pl.color, max(0.05,float(pl.line_width)))
                try:
                    def world(lx,ly):
                        rx,ry=rotate_point(lx,ly,pl.rotation); return pl.x+rx,pl.y+ry
                    for prim in symbol_primitives(pl.symbol,pl.size):
                        typ=prim[0]
                        if typ=="line": draw_segment(mappt(*world(prim[1],prim[2])),mappt(*world(prim[3],prim[4])))
                        elif typ=="circle":
                            _,cx,cy,r=prim; wc=world(cx,cy)
                            a=mappt(wc[0]-r,wc[1]+r); b=mappt(wc[0]+r,wc[1]-r)
                            win32gui.Ellipse(hdc,min(a[0],b[0]),min(a[1],b[1]),max(a[0],b[0]),max(a[1],b[1]))
                        elif typ=="arc":
                            _,cx,cy,r,a1,a2=prim
                            pts=arc_world_points(cx,cy,r,a1,a2,world)
                            draw_polyline(mappt(*q) for q in pts)
                        elif typ=="polyline": draw_polyline(mappt(*world(x,y)) for x,y in prim[1])
                        elif typ in {"text","upright_text"}:
                            _,x,y,t,h=prim; wx,wy=world(x,y)
                            text_rotation=0.0 if typ=="upright_text" else pl.rotation
                            draw_text_world(wx,wy,t,h,text_rotation,pl.color,True)
                finally:
                    win32gui.SelectObject(hdc,old_pen)

            # Fri tekst/rumnavne.
            if layer_visibility is None or layer_visibility.get(FREE_TEXT_LAYER,True):
                for item in texts:
                    if str(item.text).strip():
                        draw_text_world(item.x,item.y,item.text,item.height,item.rotation,item.color,False)

            # Kabler/ledninger. Samme kosmetiske lane-separation som PDF'en.
            visible_cables=[cb for cb in cables if layer_visibility is None or layer_visibility.get(cb.layer,True)]
            avg_dpi=max((dpi_x+dpi_y)*.5,1.0); avg_scale=max((sx+sy)*.5,1e-12)
            lane_world=(5.0/72.0*avg_dpi)/avg_scale
            fan_world=(12.0/72.0*avg_dpi)/avg_scale
            cable_visuals=cable_visual_paths(visible_cables,lane_world,fan_length=fan_world)
            for cable in cables:
                if not cable_visible_in_layers(cable,layer_visibility):
                    continue
                display_points=cable_visuals.get(id(cable),cable.points)
                if len(display_points)<2:continue
                old_pen,_=select_pen(normalize_hex_color(getattr(cable,"color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR),max(0.05,float(cable.line_width)),getattr(cable,"line_style",DEFAULT_CABLE_LINE_STYLE))
                try:draw_polyline(mappt(float(x),float(y)) for x,y in display_points)
                finally:win32gui.SelectObject(hdc,old_pen)

            if room_layer_visible and room_labels_visible:
                # draw_text_world tager en verdenshøjde; omregn fra faste 9 pt,
                # så Windows-print matcher PDF'ens kosmetiske rumtekst.
                room_h_world=(9.0/72.0*dpi_y)/max(sy*.78,1e-12)
                for room in rooms:
                    label=room_output_label(room,room_codes_visible)
                    if label:
                        draw_text_world(getattr(room,"label_x",0.0),getattr(room,"label_y",0.0),label,
                                        room_h_world,0.0,getattr(room,"color","#0f766e"),True)

            # Diskret page-space metadata oven på vektorerne. Den har fast fysisk
            # skriftstørrelse ligesom PDF-eksporten, så den ikke eksploderer i
            # størrelse ved zoom.
            if layer_visibility is None or layer_visibility.get(META_LAYER, True):
                try: fs_pt=max(5.5,min(8.0,float(annotation_font_size)-1.5))
                except Exception: fs_pt=6.5
                font_px=max(6,int(round(fs_pt/72.0*dpi_y)))
                lf=win32gui.LOGFONT(); lf.lfHeight=-font_px; lf.lfWeight=400; lf.lfFaceName="Arial"
                font=win32gui.CreateFontIndirect(lf); created_objects.append(font)
                old_font=win32gui.SelectObject(hdc,font)
                white_brush=win32gui.CreateSolidBrush(win32api.RGB(255,255,255)); created_objects.append(white_brush)
                old_b=win32gui.SelectObject(hdc,white_brush)
                white_pen=win32gui.CreatePen(win32con.PS_SOLID,1,win32api.RGB(255,255,255)); created_objects.append(white_pen)
                old_p=win32gui.SelectObject(hdc,white_pen)
                win32gui.SetBkMode(hdc,win32con.TRANSPARENT); win32gui.SetTextColor(hdc,colorref("#176b3a"))
                try:
                    pad=max(1,int(round(dpi_x/300.0)))
                    gap=max(2,int(round(5.0/72.0*dpi_x)))
                    for pl in placements:
                        if layer_visibility is not None and not layer_visibility.get(symbol_layer(pl.symbol),True):continue
                        assoc=association_display(pl)
                        if assoc:
                            ax,ay=association_world_point(pl); rx,ry=mappt(ax,ay)
                            tw,th=win32gui.GetTextExtentPoint32(hdc,assoc)
                            win32gui.Rectangle(hdc,rx-pad,ry-th-pad,rx+tw+pad,ry+pad)
                            win32gui.SetTextColor(hdc,colorref("#285d9b")); win32gui.TextOut(hdc,rx,ry-th,assoc)
                            win32gui.SetTextColor(hdc,colorref("#176b3a"))
                        lines=symbol_annotation_lines(pl,annotation_style)
                        if not lines:continue
                        x,y=mappt(pl.x,pl.y); x+=gap; y-=gap
                        sizes=[win32gui.GetTextExtentPoint32(hdc,str(t)) for t in lines]
                        bw=max((q[0] for q in sizes),default=1)+2*pad; bh=sum(q[1] for q in sizes)+2*pad
                        top=y-bh
                        win32gui.Rectangle(hdc,x-pad,top-pad,x+bw,y+pad)
                        yy=top+pad
                        for line,sz in zip(lines,sizes):
                            win32gui.TextOut(hdc,x,yy,str(line)); yy+=sz[1]
                    for cable in cables:
                        if not cable_visible_in_layers(cable,layer_visibility):continue
                        text=cable_plan_label(cable)
                        if text:
                            wx,wy=polyline_label_point(cable_visuals.get(id(cable),cable.points)); x,y=mappt(wx,wy); x+=gap; y-=gap
                            tw,th=win32gui.GetTextExtentPoint32(hdc,text)
                            win32gui.Rectangle(hdc,x-pad,y-th-pad,x+tw+pad,y+pad)
                            win32gui.TextOut(hdc,x,y-th,text)
                        for rec in cable_section_spec_labels(cable):
                            spec=str(rec.get("cable_spec") or "").strip()
                            if not spec: continue
                            wx,wy=rec.get("point",(0.0,0.0)); x,y=mappt(wx,wy); x+=gap; y+=gap
                            tw,th=win32gui.GetTextExtentPoint32(hdc,spec)
                            win32gui.Rectangle(hdc,x-pad,y-th-pad,x+tw+pad,y+pad)
                            win32gui.SetTextColor(hdc,colorref("#7c3f00")); win32gui.TextOut(hdc,x,y-th,spec)
                            win32gui.SetTextColor(hdc,colorref("#176b3a"))
                finally:
                    win32gui.SelectObject(hdc,old_p); win32gui.SelectObject(hdc,old_b); win32gui.SelectObject(hdc,old_font)

        finally:
            win32gui.SelectObject(hdc, old_brush)
            if page_started:
                try: win32print.EndPage(hdc)
                finally: page_started = False
            if doc_started:
                try: win32print.EndDoc(hdc)
                finally: doc_started = False

        return pname
    except Exception:
        # Hvis et job allerede er startet kan EndDoc fejle; Windows rydder DC'en
        # ved DeleteDC. Vi genkaster den oprindelige fejl til GUI'en.
        raise
    finally:
        if hdc and doc_started:
            try: win32print.AbortDoc(hdc)
            except Exception: pass
        # GDI-objekter må først slettes efter de ikke længere er valgt i DC'en.
        for obj in reversed(created_objects):
            try: win32gui.DeleteObject(obj)
            except Exception: pass
        if hdc:
            try: win32gui.DeleteDC(hdc)
            except Exception: pass
        if hprinter:
            try: win32print.ClosePrinter(hprinter)
            except Exception: pass

def load_document(path: str):
    ext=Path(path).suffix.lower()
    if ext==".dwg": return odafc.readfile(path)
    if ext==".dxf": return ezdxf.readfile(path)
    raise ValueError("Kun DWG og DXF understøttes.")


def document_extents(doc) -> tuple[float,float,float,float]:
    ext=bbox.extents(doc.modelspace(),fast=True)
    if not ext.has_data: return 0.0,0.0,1000.0,1000.0
    xmin,ymin=float(ext.extmin.x),float(ext.extmin.y); xmax,ymax=float(ext.extmax.x),float(ext.extmax.y)
    if xmax<=xmin: xmax=xmin+1
    if ymax<=ymin: ymax=ymin+1
    return xmin,ymin,xmax,ymax


def _entity_layer(entity) -> str:
    try: return str(entity.dxf.layer)
    except Exception: return "0"


def extract_cad_primitives(doc) -> tuple[list[CADPrimitive], dict[str,int]]:
    """Flatten DWG/DXF modelspace to screen-vector primitives.

    INSERTs and DIMENSIONs are recursively decomposed. Curves/splines/polylines
    are flattened to sufficiently fine vector polylines, not a bitmap.  Zoom is
    therefore redrawn/scaled as canvas vectors and stays sharp at any zoom.
    """
    out: list[CADPrimitive]=[]
    counts: dict[str,int]={}
    xmin,ymin,xmax,ymax=document_extents(doc)
    span=max(xmax-xmin,ymax-ymin,1.0)
    flatten=max(span/60000.0,1e-4)

    def add(kind,layer,data):
        out.append(CADPrimitive(kind,layer,tuple(data) if isinstance(data,list) else data))
        counts[kind]=counts.get(kind,0)+1

    def iter_effective(entities, inherited_layer=None):
        # Bevar den effektive lagtilknytning gennem blokke: objekter på lag 0
        # inde i en INSERT arver INSERTens lag. Det er afgørende for lagfilteret.
        for entity in entities:
            raw = _entity_layer(entity)
            effective = inherited_layer if raw == "0" and inherited_layer else raw
            typ = entity.dxftype()
            if typ == "INSERT":
                refs = [entity]
                try:
                    if getattr(entity, "mcount", 1) > 1:
                        refs = list(entity.multi_insert())
                except Exception:
                    pass
                for ref in refs:
                    try:
                        yield from iter_effective(ref.virtual_entities(), effective)
                    except Exception:
                        continue
            elif typ == "DIMENSION":
                try:
                    yield from iter_effective(entity.virtual_entities(), effective)
                except Exception:
                    yield entity, effective
            else:
                yield entity, effective

    for e, layer in iter_effective(doc.modelspace()):
        typ=e.dxftype()
        try:
            if typ=="LINE":
                add("line",layer,(float(e.dxf.start.x),float(e.dxf.start.y),float(e.dxf.end.x),float(e.dxf.end.y))); continue
            if typ=="CIRCLE":
                add("circle",layer,(float(e.dxf.center.x),float(e.dxf.center.y),float(e.dxf.radius))); continue
            if typ=="ARC":
                add("arc",layer,(float(e.dxf.center.x),float(e.dxf.center.y),float(e.dxf.radius),float(e.dxf.start_angle),float(e.dxf.end_angle))); continue
            if typ=="TEXT":
                ins=e.dxf.insert; add("text",layer,(float(ins.x),float(ins.y),str(e.dxf.text),float(e.dxf.height),float(e.dxf.get("rotation",0.0)))); continue
            if typ=="MTEXT":
                ins=e.dxf.insert; txt=e.plain_text() if hasattr(e,"plain_text") else str(e.text)
                add("text",layer,(float(ins.x),float(ins.y),txt,float(e.dxf.char_height),float(e.dxf.get("rotation",0.0)))); continue
            if typ=="POINT":
                loc=e.dxf.location; add("point",layer,(float(loc.x),float(loc.y))); continue
            if typ in ("HATCH","MPOLYGON"):
                for hp in ezpath.from_hatch(e):
                    pts=[(float(v.x),float(v.y)) for v in hp.flattening(flatten)]
                    if len(pts)>=2: add("polyline",layer,tuple(pts))
                continue
            # LWPOLYLINE/POLYLINE/SPLINE/ELLIPSE and other path-compatible entities.
            try:
                pp=ezpath.make_path(e)
                subpaths=list(pp.sub_paths())
                paths=subpaths if subpaths else [pp]
                made=False
                for sp in paths:
                    pts=[(float(v.x),float(v.y)) for v in sp.flattening(flatten)]
                    if len(pts)>=2:
                        add("polyline",layer,tuple(pts)); made=True
                if made: continue
            except Exception:
                pass
            # Last-resort primitive approximation for supported ezdxf entities.
            prim=disassemble.make_primitive(e,max_flattening_distance=flatten)
            verts=[(float(v.x),float(v.y)) for v in prim.vertices()]
            if len(verts)>=2: add("polyline",layer,tuple(verts))
        except Exception:
            # Unsupported display entities must never prevent a drawing opening.
            continue
    return out,counts
