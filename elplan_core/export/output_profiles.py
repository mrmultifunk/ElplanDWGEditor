"""Fælles skala- og mærkningsprofiler til editor og eksport."""

from __future__ import annotations

from elplan_core.constants import OUTPUT_SCREEN_DPI


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
