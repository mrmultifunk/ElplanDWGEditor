"""Lavt koblede PL-dåseværdier, som også bruges ved symbolkopiering.

Den resterende PL-dåsemodel flyttes hertil i fase 2.7.
"""

from __future__ import annotations


PL_BOX_ORIENTATIONS = {
    0: "0° · 1-2-3 mod plantegningens top",
    90: "90° · 1-2-3 mod højre",
    180: "180° · 1-2-3 mod bunden",
    270: "270° · 1-2-3 mod venstre",
}


PL_OUTLET_TYPES = {
    "generic": "Generisk PL / samleklemmer",
    "lk_classic": "LK klassisk lampeudtag",
    "wiser_dimmer": "LK Wiser / dæmpbar",
    "nordtronic_zigbee": "Nordtronic lampeudtag m. Zigbee dimmer",
}


def normalize_pl_box_orientation(value) -> int:
    """Normalisér PL-dåsens fysiske orientering til 0/90/180/270 grader."""
    try:
        angle=int(round(float(value))) % 360
    except (TypeError,ValueError):
        angle=0
    return min(PL_BOX_ORIENTATIONS, key=lambda candidate: min((angle-candidate)%360,(candidate-angle)%360))


def normalize_pl_outlet_type(value) -> str:
    key=str(value or "").strip().lower()
    aliases={
        "": "generic", "pl": "generic", "generic_pl": "generic",
        "lk": "lk_classic", "classic": "lk_classic", "lk_original": "lk_classic",
        "wiser": "wiser_dimmer", "dimmer": "wiser_dimmer", "smart": "wiser_dimmer",
        "nordtronic": "nordtronic_zigbee", "nordtronic_zigbee_dimmer": "nordtronic_zigbee",
        "98425033": "nordtronic_zigbee", "ceiling_outlet_zigbee": "nordtronic_zigbee",
    }
    key=aliases.get(key,key)
    return key if key in PL_OUTLET_TYPES else "generic"
