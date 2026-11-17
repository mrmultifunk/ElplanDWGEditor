"""Kabelkategorier, lag og visuel linjestil."""

from __future__ import annotations

import re

from elplan_core.appearance import normalize_hex_color
from elplan_core.constants import (
    CABLE_LAYER,
    DEFAULT_CABLE_CATEGORIES,
    DEFAULT_CABLE_CATEGORY,
    DEFAULT_CABLE_COLOR,
    DEFAULT_CABLE_LINE_STYLE,
    PATCH_CABLE_LAYER,
    WIRE_LAYER,
)


def _cable_category_id(value: str) -> str:
    text=str(value or "").strip().lower()
    text=re.sub(r"[^a-z0-9_\-]+","_",text).strip("_-")
    return text or DEFAULT_CABLE_CATEGORY


def normalize_cable_category_id(value: str) -> str:
    return _cable_category_id(value)


def default_cable_category_records() -> list[dict]:
    return [dict(row) for row in DEFAULT_CABLE_CATEGORIES]


def normalize_cable_category_records(records) -> list[dict]:
    """Normalisér projektets kabelkategorier med stabile id'er og visuel stil."""
    source=list(records or []) if isinstance(records,(list,tuple)) else []
    out=[]; seen=set()
    for raw in source:
        if not isinstance(raw,dict):
            continue
        cid=_cable_category_id(raw.get("id") or raw.get("name"))
        if cid in seen:
            continue
        seen.add(cid)
        name=str(raw.get("name") or cid.replace("_"," ").title()).strip() or cid
        default_row=next((row for row in DEFAULT_CABLE_CATEGORIES if row["id"]==cid),None)
        if "description" in raw:
            description=str(raw.get("description") or "").strip()
        else:
            description=str((default_row or {}).get("description","") or "").strip()
        out.append({
            "id":cid,
            "name":name,
            "description":description,
            "color":normalize_hex_color(raw.get("color",DEFAULT_CABLE_COLOR),DEFAULT_CABLE_COLOR),
            "line_style":normalize_cable_line_style(raw.get("line_style",DEFAULT_CABLE_LINE_STYLE)),
        })
    if not out:
        out=default_cable_category_records()
    if DEFAULT_CABLE_CATEGORY not in {x["id"] for x in out}:
        out.append(dict(next(x for x in DEFAULT_CABLE_CATEGORIES if x["id"]==DEFAULT_CABLE_CATEGORY)))
    return out


def cable_category_record(records, category_id: str) -> dict:
    categories=normalize_cable_category_records(records)
    cid=_cable_category_id(category_id)
    for row in categories:
        if row["id"]==cid:
            return dict(row)
    for row in categories:
        if row["id"]==DEFAULT_CABLE_CATEGORY:
            return dict(row)
    return dict(categories[0])


def cable_category_style(records, category_id: str) -> tuple[str,str]:
    row=cable_category_record(records,category_id)
    return str(row["color"]), str(row["line_style"])


def cable_category_layer_name(base_layer: str, category_id: str) -> str:
    base=str(base_layer or CABLE_LAYER).strip() or CABLE_LAYER
    cid=_cable_category_id(category_id).upper().replace("_","-")
    return f"{base}-KAT-{cid}"


def cable_effective_layer(cable) -> str:
    return cable_category_layer_name(getattr(cable,"layer",CABLE_LAYER),getattr(cable,"cable_category",DEFAULT_CABLE_CATEGORY))


def cable_category_layer_label(layer_name: str, records=None) -> str:
    text=str(layer_name or "")
    marker="-KAT-"
    if marker not in text:
        return text
    base,raw_id=text.rsplit(marker,1)
    cid=_cable_category_id(raw_id.replace("-","_"))
    row=cable_category_record(records,cid)
    prefix={CABLE_LAYER:"Kabel",PATCH_CABLE_LAYER:"Patchkabel",WIRE_LAYER:"Ledning"}.get(base,"Kabel")
    return f"{prefix} · {row['name']}"


def cable_visible_in_layers(cable, layer_visibility) -> bool:
    if layer_visibility is None:
        return True
    base=str(getattr(cable,"layer",CABLE_LAYER) or CABLE_LAYER)
    effective=cable_effective_layer(cable)
    # Kategori-laget er autoritativt. Hvis et ældre projekt endnu ikke har en
    # kategori-nøgle, bruges det gamle EL-KABLER/EL-LEDNINGER-lag som fallback.
    return bool(layer_visibility.get(effective,layer_visibility.get(base,True)))


def normalize_cable_line_style(value: str) -> str:
    """Return stable internal cable line-style key."""
    key=str(value or "").strip().casefold().replace("_", "").replace("-", "")
    aliases={
        "solid":"solid", "fuldt optrukket":"solid", "fuldtoptrukket":"solid",
        "dash":"dash", "dashed":"dash", "stiplet":"dash",
        "dot":"dot", "dotted":"dot", "prikket":"dot",
        "dashdot":"dashdot", "stregprik":"dashdot", "streg prik":"dashdot",
    }
    return aliases.get(key, DEFAULT_CABLE_LINE_STYLE)
