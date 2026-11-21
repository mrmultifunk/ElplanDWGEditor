"""Skriv el-symboler, kabler og fritekst til DXF."""

from __future__ import annotations

import ezdxf

from elplan_core.appearance import normalize_hex_color
from elplan_core.associations import association_display, association_world_point
from elplan_core.cables.categories import cable_category_layer_name, normalize_cable_line_style
from elplan_core.cables.geometry import cable_label_point, rotate_point
from elplan_core.cables.sections import cable_section_spec_labels
from elplan_core.cables.visual import cable_plan_label
from elplan_core.constants import (
    CABLE_LAYER,
    DEFAULT_ANNOTATION_STYLE,
    DEFAULT_CABLE_CATEGORY,
    DEFAULT_CABLE_COLOR,
    DEFAULT_CABLE_LINE_STYLE,
    FREE_TEXT_LAYER,
    GENERATED_LAYER_COLORS,
    META_LAYER,
    PATCH_CABLE_LAYER,
    WIRE_LAYER,
)
from elplan_core.models import CablePlacement, Placement, TextPlacement
from elplan_core.symbols.clipboard import symbol_annotation_lines, symbol_layer
from elplan_core.symbols.geometry import symbol_primitives


def _nearest_dxf_lineweight(width_mm: float) -> int:
    """Konvertér mm til nærmeste gyldige DXF lineweight (1/100 mm)."""
    valid = (0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211)
    target = max(0.0, float(width_mm)) * 100.0
    return min(valid, key=lambda value: abs(value - target))


def _true_color_int(hex_color: str) -> int:
    c = normalize_hex_color(hex_color)
    return int(c[1:], 16)


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
