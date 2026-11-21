"""Indlæsning af CAD-filer, enheder og vektorprimitiver."""

from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf import bbox, disassemble, path as ezpath
from ezdxf.addons import odafc

from elplan_core.models import CADPrimitive


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
