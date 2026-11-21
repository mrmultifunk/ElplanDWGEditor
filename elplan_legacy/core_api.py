from __future__ import annotations

"""Eksisterende re-eksporter til core_logic uden at indlæse Tk-brugerfladen."""

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
from elplan_core.cables.visual import (
    _cable_visual_sort_key,
    _line_intersection,
    _visual_segment_info,
    _visual_segments_overlap,
    cable_display_label,
    cable_plan_label,
    cable_visual_layout,
    cable_visual_paths,
)
from elplan_core.cad_io import (
    INSUNITS_METERS,
    _entity_layer,
    document_extents,
    drawing_unit_info,
    extract_cad_primitives,
    load_document,
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
from elplan_core.platform.printing import print_vector_windows
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
from elplan_core.export.dxf_writer import (
    _nearest_dxf_lineweight,
    _true_color_int,
    add_cable_to_dxf,
    add_free_text_to_dxf,
    add_placement_to_dxf,
    ensure_layers,
)
from elplan_core.export.extents import (
    _primitive_bbox,
    _quantile,
    _robust_center_range,
    crop_extents_to_aspect,
    fit_view_extents,
    page_layout,
    print_extents,
    resolve_page_size,
)
from elplan_core.export.output_profiles import (
    annotation_visual_profile,
    output_cad_text_font_size,
    output_equivalent_view_scale,
    output_free_text_font_size,
    output_switch_association_tag_origin,
    output_switch_association_tag_profile,
    output_symbol_text_font_size,
)
from elplan_core.export.pdf import export_vector_pdf
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

from elplan_catalog import article_intelligence
from elplan_shared.annotation_layout import choose_label_origin, expand_rect

import ezdxf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from ezdxf import bbox, disassemble, path as ezpath
from ezdxf.addons import odafc


def first_unassigned_association_channel(placement: "Placement") -> int | None:
    channels = association_channel_letters(placement)
    for i, value in enumerate(channels):
        if not value:
            return i
    return None


def assigned_association_channel_count(placement: "Placement") -> int:
    return sum(1 for value in association_channel_letters(placement) if value)


APPEARANCE_MODES = {"light": "Lys", "dark": "Mørk", "system": "Følg Windows"}


def _screen_line_width(width_mm: float, selected: bool = False) -> int:
    # CAD-lineweight vises som en omtrent fysisk skærmtykkelse og skaleres ikke
    # med zoom, ligesom lineweight normalt gør i en CAD-viewer.
    px = max(1, int(round(max(float(width_mm), 0.01) * 96.0 / 25.4)))
    return px + (1 if selected else 0)


@lru_cache(maxsize=1024)
def _arc_points(cx, cy, r, a1, a2, steps=24):
    return [
        (cx + r * math.cos(math.radians(a1 + (a2 - a1) * i / steps)),
         cy + r * math.sin(math.radians(a1 + (a2 - a1) * i / steps)))
        for i in range(steps + 1)
    ]
