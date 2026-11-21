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
from elplan_core.bom.articles import (
    ARTICLE_METADATA_FIELDS,
    ARTICLE_STRUCTURED_FIELDS,
    _ARTICLE_COLOR_CANONICAL,
    _ARTICLE_UNIT_ALIASES,
    _format_module_number,
    _module_group_label,
    _module_label,
    _positive_article_number,
    _predefined_article_catalog_cached,
    article_filter_facets,
    article_packaging,
    article_price_basis_quantity,
    article_purchase_requirement,
    bom_article_category,
    cable_article_key,
    cable_article_key_parts,
    cable_type_display,
    load_predefined_article_catalog,
    normalize_article_catalog,
    normalize_article_color,
    normalize_article_module,
    normalize_article_unit,
    normalize_cable_article_bindings,
)
from elplan_core.bom.assemblies import (
    bom_assembly_effective_items,
    bom_assembly_item_counts,
    bom_assembly_lookup,
    bom_assembly_usage,
    normalize_bom_assemblies,
    normalize_symbol_article_bindings,
    normalize_symbol_assembly_bindings,
)
from elplan_core.bom.build import (
    _bom_socket_label,
    _bom_switch_label,
    bom_article_room_usage,
    bom_article_source_uids,
    bom_binding_summary,
    bom_source_breakdown,
    bom_supported_symbol,
    bom_symbol_bindings,
    bom_symbol_parts,
    build_bom,
    project_control_issues,
)
from elplan_core.bom.procurement import (
    MATERIAL_COLOR_PRESETS,
    MOUNTING_ZONE_LABELS,
    MOUNTING_ZONE_OPTIONS,
    bom_purchase_segment_key,
    mounting_zone_label,
    normalize_already_purchased,
    normalize_material_color,
    normalize_mounting_height_mm,
    normalize_mounting_zone,
    placement_procurement_context,
)
from elplan_core.bom.scope import (
    normalize_placement_bom_room_additions,
    placement_bom_room_uids,
    placement_matches_bom_room,
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
