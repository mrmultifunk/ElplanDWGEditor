"""Indkøbssegmenter og montageoplysninger for symbolforekomster."""

from __future__ import annotations

import math


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
