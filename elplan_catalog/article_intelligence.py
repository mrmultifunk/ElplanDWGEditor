from __future__ import annotations

"""Structured article taxonomy, technical properties, variants and relations.

The module deliberately contains no Qt and no dependency on :mod:`core_logic`.
It receives already-normalised article rows and adds stable, cross-manufacturer
metadata.  Source fields such as ``category`` and ``description`` are never
replaced: controlled metadata lives beside them.
"""

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
from typing import Iterable

TAXONOMY_VERSION = 1
SEMANTIC_MODEL_VERSION = 1

CATEGORY_PATHS = (
    "Installation · Afbrydere og betjening",
    "Installation · Stikkontakter og udtag",
    "Installation · Tangenter og afdækninger",
    "Installation · Rammer",
    "Installation · Dåser og montage",
    "Belysning · Lampeudtag",
    "Belysning · Downlight og armaturer",
    "Belysning · Fronter og tilbehør",
    "Styring · Lysstyring og smart home",
    "Styring · IHC og automatik",
    "Styring · Sensorer og PIR",
    "Styring · Relæer og aktuatorer",
    "Styring · KNX",
    "Forbindelse · Klemmer og samlemateriel",
    "Forbindelse · Stik og konnektorer",
    "Kabler og data · Installationskabel",
    "Kabler og data · Data og netværk",
    "Tavle · Materiel og tilbehør",
    "Tavle · Sikringer og beskyttelse",
    "Installation · Øvrigt installationsmateriel",
    "Øvrigt · Befæstelse og montage",
    "Øvrigt · Tilbehør",
    "Øvrigt · Ukategoriseret",
)

RELATION_TYPES = {
    "compatible": "Kompatibel med",
    "accessory": "Tilbehør til",
    "requires": "Kræver",
    "replacement": "Erstatter / erstatning",
    "alternative": "Alternativ",
    "part_of": "Del af",
}

_SPEC_LABELS = {
    "module_size": "Modul",
    "color": "Farve",
    "mounting_type": "Montage",
    "rated_voltage": "Spænding",
    "rated_current": "Strøm",
    "pole_configuration": "Poler",
    "gang_count": "Antal enheder",
    "has_earth": "Jord",
    "smart_protocol": "Protokol",
    "dimmable": "Dæmpbar",
    "ip_rating": "IP",
    "power": "Effekt",
    "cct": "CCT",
    "diameter": "Diameter",
    "cutout": "Udskæring",
    "terminal_count": "Tilslutninger",
    "conductor_cross_section": "Ledertværsnit",
    "cable_spec": "Kabel",
    "package_length": "Pakning",
    "environment": "Miljø",
    "dimming_type": "Dæmpning",
    "switch_input": "Styresignal",
}


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fold(value) -> str:
    return _text(value).casefold()


def taxonomy_parts(path: str) -> tuple[str, str]:
    path = _text(path)
    if "·" in path:
        a, b = path.split("·", 1)
        return a.strip(), b.strip()
    return (path, "") if path else ("", "")




_DESIGN_SERIES = ("SLIM", "CHOICE", "PURE", "SOFT", "BASE 63", "BASELINE 63", "SOFTLINE 63")
_LK_AIR_STANDARD_FRONT_BOXES = {"504D3010", "504D3015", "504D3020", "504D3025"}
_LK_AIR_FIRE_FRONT_BOXES = {"504D3110", "504D3115", "504D3120", "504D3125"}
_LK_AIR_SLIM_BOXES = {"504D3510", "504D3515", "504D3520", "504D3525"}
_LK_AIR_CAST_BOXES = {
    "504D6010", "504D601020", "504D6015", "504D601520",
    "504D6020", "504D602020", "504D6025", "504D602520",
}
_LK_AIR_MASONRY_BOXES = {"504D8010", "504D8015", "504D8020", "504D8025"}
_LK_AIR_STANDARD_BOXES = _LK_AIR_STANDARD_FRONT_BOXES | _LK_AIR_CAST_BOXES | _LK_AIR_MASONRY_BOXES
_LK_AIR_ALL_BOXES = _LK_AIR_STANDARD_BOXES | _LK_AIR_FIRE_FRONT_BOXES | _LK_AIR_SLIM_BOXES


def _normalise_string_list(values) -> list[str]:
    if isinstance(values, str):
        values = re.split(r"[,;/|]+", values)
    if not isinstance(values, (list, tuple, set)):
        return []
    out = []
    seen = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def normalize_compatibility(value) -> dict:
    """Normalise structured compatibility without turning it into identity.

    Compatibility describes *what this article may be used with*.  It must not
    be reused as the article's own family/variant.  Unknown keys are retained so
    manufacturer-specific importers can add verified compatibility dimensions
    without a schema migration.
    """
    if not isinstance(value, dict):
        return {}
    out = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key)
        if not key:
            continue
        if isinstance(raw_value, (list, tuple, set, str)):
            vals = _normalise_string_list(raw_value)
            if vals:
                out[key] = vals
        elif raw_value not in (None, ""):
            out[key] = _text(raw_value)
    return out


def compatibility_text(record: dict) -> str:
    compat = normalize_compatibility(record.get("compatibility"))
    parts = []
    labels = {
        "design_series": "Designserier",
        "mounting_systems": "Montage",
        "product_families": "Produktfamilier",
        "notes": "Noter",
    }
    for key, value in compat.items():
        if isinstance(value, list) and value:
            parts.append(f"{labels.get(key, key)}: {', '.join(value)}")
        elif _text(value):
            parts.append(f"{labels.get(key, key)}: {_text(value)}")
    return " · ".join(parts)


def _design_series_from_text(text: str) -> list[str]:
    hay = _fold(text)
    found = []
    for label in _DESIGN_SERIES:
        needle = label.casefold()
        if re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", hay):
            found.append(label)
    return found


def _family_from_identity_text(record: dict) -> tuple[str, str]:
    """Return (family, evidence) from product identity, not compatibility prose."""
    desc = _fold(record.get("description"))
    series = _text(record.get("series"))
    series_fold = series.casefold()
    maker = _fold(record.get("manufacturer"))

    # Verified article families repair historical combined series labels before
    # a generic "LK FUGA" name match can hide the AIR sub-family.
    no = _text(record.get("article_no")).upper()
    if no in _LK_AIR_ALL_BOXES:
        return "LK FUGA AIR", "verificeret artikelserie"

    # Product name/heading is strongest evidence.
    patterns = (
        ("lk fuga", "LK FUGA"),
        ("opus 66", "LK OPUS 66"),
        ("opus 73", "LK OPUS 73"),
        ("opus 74", "LK OPUS 74"),
        ("clic'line", "CLIC'LINE"),
        ("clicline", "CLIC'LINE"),
        ("lk one", "LK One"),
        ("actassi", "Actassi"),
        ("lexcom home", "Lexcom Home"),
        ("ihc control", "IHC Control"),
        ("ihc wireless", "IHC Wireless"),
        ("wiser", "Wiser"),
        ("knx", "KNX"),
    )
    for needle, label in patterns:
        if needle in desc:
            if label == "LK FUGA" and re.search(r"\bair\b", desc):
                # The title is product identity. Separators such as "·" or the
                # registered-mark glyph often sit between FUGA and AIR.
                return "LK FUGA AIR", "produktnavn"
            return label, "produktnavn"

    # Series is weaker. Combined labels such as "LK FUGA AIR / SLIM" are
    # intentionally reduced to the actual product family and never to SLIM.
    if "lk fuga air" in series_fold:
        return "LK FUGA AIR", "serie"
    for needle, label in patterns:
        if needle in series_fold:
            return label, "serie"

    # For other manufacturers a clean, single series is a useful family. Avoid
    # slash-combined taxonomy strings because they often mix family + variant.
    if series and "/" not in series and len(series) <= 80:
        return series, "serie"
    if "wago" in maker and _text(record.get("design_family")):
        return _text(record.get("design_family")), "designserie"
    return "", ""


def derive_product_semantics(record: dict) -> dict:
    """Derive product family, own variant and compatibility as separate facts.

    The function is conservative and producer-independent at the model level;
    manufacturer-specific rules only supply stronger evidence where the source
    catalogue is known to conflate identity and compatibility.
    """
    row = dict(record or {})
    evidence = dict(row.get("semantic_evidence")) if isinstance(row.get("semantic_evidence"), dict) else {}

    family_manual = _text(row.get("product_family_manual"))
    variant_manual = _text(row.get("product_variant_manual"))
    current_family = _text(row.get("product_family"))
    current_variant = _text(row.get("product_variant"))

    if family_manual:
        family, family_source = family_manual, "manuel"
    elif current_family:
        family, family_source = current_family, _text(evidence.get("product_family")) or "gemt semantik"
    else:
        family, family_source = _family_from_identity_text(row)
    if family:
        evidence["product_family"] = family_source

    desc = _fold(row.get("description"))
    typ = _fold(row.get("product_type"))
    cat = _fold(row.get("category"))
    no = _text(row.get("article_no")).upper()
    is_box = "dåse" in desc or "dåse" in typ or "dåse" in cat or "daase" in desc
    is_accessory = "tilbehør" in desc or "tilbehoer" in desc
    box_identity_text = " ".join((desc, typ))
    is_physical_box = is_box and not is_accessory and any(
        token in box_identity_text for token in ("forfradåse", "forfra dåse", "forfradaase", "indstøbningsdåse", "indstoebningsdaase", "indmuringsdåse", "indmuringsdaase")
    )
    identity_text = " ".join((desc, typ, cat))

    if variant_manual:
        variant, variant_source = variant_manual, "manuel"
    elif current_variant:
        variant, variant_source = current_variant, _text(evidence.get("product_variant")) or "gemt semantik"
    else:
        variant = ""
        variant_source = ""
        if no in _LK_AIR_SLIM_BOXES:
            variant, variant_source = "SLIM", "verificeret artikelserie"
        elif no in _LK_AIR_FIRE_FRONT_BOXES:
            variant, variant_source = "Brandsikker", "verificeret artikelserie"
        elif no in _LK_AIR_STANDARD_BOXES:
            variant, variant_source = "Standard", "verificeret artikelserie"
        elif family == "LK FUGA AIR" and is_physical_box:
            if re.search(r"\bair\s+slim\b", desc) or re.search(r"\bslim\s+forfra", desc):
                variant, variant_source = "SLIM", "produktnavn"
            else:
                # AIR indmurings-/indstøbnings-/forfradåser are the standard
                # physical box unless the product identity itself says SLIM.
                # A mention of SLIM in design/compatibility data is not enough.
                variant, variant_source = "Standard", "produktnavn"
        # Design series are identity only for visible/product-side parts such as
        # frames/tangents, not for boxes that merely accept those series.
        if not variant and any(x in identity_text for x in ("ramme", "tangent", "afdæk", "front")):
            for design in _DESIGN_SERIES:
                if re.search(rf"(?<![\w]){re.escape(design.casefold())}(?![\w])", desc):
                    variant, variant_source = design, "produktnavn"
                    break
    if variant:
        evidence["product_variant"] = variant_source

    compat = normalize_compatibility(row.get("compatibility"))
    compat_sources = dict(evidence.get("compatibility")) if isinstance(evidence.get("compatibility"), dict) else {}
    source_text = _text(row.get("semantic_source_text"))
    source_hay = source_text.casefold()

    # Verified family data used to repair bundled/legacy AIR rows immediately,
    # even before the next LK sync has downloaded the full product prose.
    if no in _LK_AIR_STANDARD_FRONT_BOXES:
        compat.setdefault("design_series", ["CHOICE", "PURE", "SOFT"])
        compat.setdefault("mounting_systems", ["Teknisk monteringsramme"])
        compat_sources.setdefault("design_series", "LK katalog / artikelserie")
    elif no in (_LK_AIR_CAST_BOXES | _LK_AIR_MASONRY_BOXES):
        compat.setdefault("design_series", ["CHOICE", "PURE", "SOFT", "SLIM"])
        compat.setdefault("mounting_systems", ["Teknisk monteringsramme", "SLIM teknisk monteringsramme"])
        compat.setdefault("notes", ["SLIM-kompatibilitet er betinget af LK's kombinationsregler."])
        compat_sources.setdefault("design_series", "LK katalog / artikelserie")
    elif no in _LK_AIR_SLIM_BOXES:
        compat.setdefault("design_series", ["SLIM", "CHOICE", "PURE", "SOFT"])
        compat.setdefault("mounting_systems", ["SLIM teknisk monteringsramme", "Teknisk monteringsramme"])
        compat_sources.setdefault("design_series", "LK katalog / artikelserie")

    # Fresh LK pages contain richer application prose. Only interpret design
    # names as compatibility when the wording explicitly discusses mounting or
    # supported frames; their mere presence elsewhere must not redefine identity.
    if source_text and is_box and any(phrase in source_hay for phrase in (
        "design rammer", "designrammer", "rammetyper", "kan monteres med", "anvendes med"
    )):
        designs = _design_series_from_text(source_text)
        if designs:
            existing = _normalise_string_list(compat.get("design_series", []))
            compat["design_series"] = _normalise_string_list(existing + designs)
            compat_sources["design_series"] = "producentens anvendelsestekst"
        mounts = []
        if "slim teknisk monteringsramme" in source_hay:
            mounts.append("SLIM teknisk monteringsramme")
        if "teknisk monteringsramme" in source_hay:
            mounts.append("Teknisk monteringsramme")
        if mounts:
            compat["mounting_systems"] = _normalise_string_list(_normalise_string_list(compat.get("mounting_systems", [])) + mounts)
            compat_sources["mounting_systems"] = "producentens anvendelsestekst"

    if compat_sources:
        evidence["compatibility"] = compat_sources

    return {
        "semantic_model_version": str(SEMANTIC_MODEL_VERSION),
        "product_family": family,
        "product_variant": variant,
        "compatibility": compat,
        "semantic_evidence": evidence,
    }


def semantic_summary(record: dict) -> list[str]:
    semantics = derive_product_semantics(record)
    out = []
    if semantics.get("product_family"):
        out.append(f"Familie: {semantics['product_family']}")
    if semantics.get("product_variant"):
        out.append(f"Variant: {semantics['product_variant']}")
    ctext = compatibility_text(semantics)
    if ctext:
        out.append(f"Kompatibilitet: {ctext}")
    return out


def derive_category(record: dict) -> str:
    """Return a controlled category without changing the source category."""
    explicit = _text(record.get("category_normalized"))
    if explicit in CATEGORY_PATHS:
        return explicit

    kind = _fold(record.get("kind"))
    typ = _fold(record.get("product_type"))
    cat = _fold(record.get("category"))
    desc = _fold(record.get("description"))
    series = _fold(record.get("series"))
    hay = " ".join((typ, cat, desc, series))

    if kind == "cable" or "kabel" in typ or "kabler" in cat:
        if any(x in hay for x in ("ethernet", "patch", "data", "cat 6", "cat6", "cat 7", "cat7", "helukat")):
            return "Kabler og data · Data og netværk"
        return "Kabler og data · Installationskabel"
    if any(x in hay for x in ("actassi", "lexcom", "data og netværk", "rj45", "fiber", "patchpanel", "patchkabel")):
        return "Kabler og data · Data og netværk"
    if "sensorer og pir" in cat or any(x in hay for x in ("pir sensor", "bevægelsessensor", "bevaegelsessensor")):
        return "Styring · Sensorer og PIR"
    if "relæer" in cat or "releer" in cat or any(x in hay for x in ("relæmodul", "relaemodul", "relæ", "relay")):
        return "Styring · Relæer og aktuatorer"
    if "knx" in hay:
        return "Styring · KNX"
    if "ihc control" in hay:
        if any(x in hay for x in ("finsikring", "sikring")):
            return "Tavle · Sikringer og beskyttelse"
        if any(x in hay for x in ("flerpolet system", "multiplug", "stikprop", "koblingsstykke")):
            return "Forbindelse · Stik og konnektorer"
        if any(x in hay for x in ("sømplug", "soemplug", "clipsplug", "plugs ", "skrue")):
            return "Øvrigt · Befæstelse og montage"
        return "Styring · IHC og automatik"
    if any(x in typ for x in ("samlemuffe", "klemme")) or any(x in hay for x in ("samlemuffe", "forbindelsesklemme", "fjedersamlemuffe")):
        return "Forbindelse · Klemmer og samlemateriel"
    if "downlight" in typ or "downlight" in hay or "spot" in typ:
        return "Belysning · Downlight og armaturer"
    if typ == "front" or " front" in desc:
        return "Belysning · Fronter og tilbehør"
    if "lampeudtag" in typ or "lampeudtag" in hay:
        return "Belysning · Lampeudtag"
    if any(x in typ for x in ("lysstyring", "wiser")) or any(x in hay for x in ("zigbee", "wiser", "lysstyring", "lysdæmper", "lysdimmer", "dimmer")):
        # Pure FUGA dimmer/controls belong in control rather than generic switch.
        return "Styring · Lysstyring og smart home"
    if "stikkontakt" in typ or "stikkontakt" in hay or re.search(r"\budtag\b", typ):
        return "Installation · Stikkontakter og udtag"
    if any(x in typ for x in ("tangent", "afdæk")) or any(x in hay for x in ("tangent", "afdækning", "dækplade")):
        return "Installation · Tangenter og afdækninger"
    if "ramme" in typ or "ramme" in hay:
        if "teknisk" in hay or "montageramme" in hay:
            return "Installation · Dåser og montage"
        return "Installation · Rammer"
    if "dåse" in typ or "dåse" in hay:
        return "Installation · Dåser og montage"
    if any(x in typ for x in ("afbryder", "betjening")) or any(x in hay for x in ("afbryder", "korrespondance", "krone", "tryk")):
        return "Installation · Afbrydere og betjening"
    if any(x in hay for x in ("resi9", "tavle", "kapsling", "automatsikring", "rcd", "hpfi")):
        return "Tavle · Materiel og tilbehør"
    if any(x in hay for x in ("finsikring", "smeltesikring", "sikring")):
        return "Tavle · Sikringer og beskyttelse"
    if any(x in hay for x in ("flerpolet system", "stikprop", "industristik", "konnektor")):
        return "Forbindelse · Stik og konnektorer"
    if any(x in hay for x in ("sømplug", "soemplug", "clipsplug")) or desc.startswith("plugs "):
        return "Øvrigt · Befæstelse og montage"
    if any(x in series for x in ("lk fuga", "lk opus", "lk one", "clic'line")) or series == "lk":
        return "Installation · Øvrigt installationsmateriel"
    if any(x in hay for x in ("skrue", "tilbehør", "adapter")):
        return "Øvrigt · Tilbehør"
    return "Øvrigt · Ukategoriseret"


def derive_function(record: dict) -> str:
    explicit = _text(record.get("function"))
    if explicit:
        return explicit
    hay = " ".join(_fold(record.get(k)) for k in ("description", "product_type", "category"))
    rules = (
        ("Kroneafbryder", ("kroneafbryder", "krone afbryder")),
        ("Korrespondanceafbryder", ("korrespondance",)),
        ("1-polet afbryder", ("1-polet", "1 polet")),
        ("Tryk", ("fjedertryk", "tryk")),
        ("Lysdæmper", ("lysdæmper", "dimmer")),
        ("Stikkontakt", ("stikkontakt",)),
        ("Lampeudtag", ("lampeudtag",)),
        ("Downlight", ("downlight",)),
        ("Samlemuffe", ("samlemuffe",)),
        ("Ramme", ("ramme",)),
        ("Dåse", ("dåse",)),
        ("Installationskabel", ("installationskabel", "n1xz1",)),
        ("Datakabel", ("ethernet", "patchkabel", "helukat")),
    )
    for label, needles in rules:
        if any(n in hay for n in needles):
            return label
    return _text(record.get("product_type"))


def _put(specs: dict, key: str, value) -> None:
    text = _text(value)
    if text and key not in specs:
        specs[key] = text


def _bool_text(value: bool) -> str:
    return "Ja" if value else "Nej"


def derive_technical_specs(record: dict) -> dict[str, str]:
    """Extract only explicit or strongly evidenced technical properties."""
    specs: dict[str, str] = {}
    for key, field, suffix in (
        ("module_size", "module_size", ""),
        ("color", "color", ""),
        ("mounting_type", "mounting_type", ""),
        ("ip_rating", "ip_rating", ""),
        ("cct", "cct", ""),
        ("power", "power_w", " W"),
        ("diameter", "diameter_mm", " mm"),
        ("cutout", "cutout_mm", " mm"),
        ("cable_spec", "cable_spec", ""),
        ("environment", "environment", ""),
        ("dimming_type", "dimming_type", ""),
        ("switch_input", "switch_input", ""),
    ):
        value = _text(record.get(field))
        if value:
            _put(specs, key, value if not suffix or value.casefold().endswith(suffix.strip().casefold()) else value + suffix)
    if record.get("package_length_m") not in (None, ""):
        _put(specs, "package_length", f"{record.get('package_length_m')} m")

    hay = " ".join(_text(record.get(k)) for k in ("description", "note", "environment", "voltage"))
    lower = hay.casefold()

    # Voltage: prefer a dedicated source field; otherwise parse explicit V/VAC/VDC.
    voltage = _text(record.get("voltage"))
    if voltage:
        _put(specs, "rated_voltage", voltage)
    else:
        m = re.search(r"(?<![\d.,])(\d{2,4}(?:[.,]\d+)?)\s*(V(?:AC|DC)?)(?!\w)", hay, re.I)
        if m:
            _put(specs, "rated_voltage", f"{m.group(1).replace(',', '.')} {m.group(2).upper()}")

    for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:[.,]\d+)?)\s*(A(?:X|C)?)(?!\w)", hay, re.I):
        prefix=hay[max(0,m.start()-8):m.start()].casefold().rstrip()
        # Network categories such as "Cat. 6A" are not ampere ratings.
        if re.search(r"cat\.?\s*$",prefix):
            continue
        _put(specs, "rated_current", f"{m.group(1).replace(',', '.')} {m.group(2).upper()}")
        break

    m = re.search(r"(?<!\w)(\dP(?:\s*\+\s*[NE])?(?:\s*\+\s*[NE])?)(?!\w)", hay, re.I)
    if m:
        _put(specs, "pole_configuration", re.sub(r"\s+", "", m.group(1).upper()))

    m = re.search(r"(?<!\d)([2-6])\s*[- ]?gang\b", lower)
    if m:
        _put(specs, "gang_count", m.group(1))
    elif "dobbelt stikkontakt" in lower:
        _put(specs, "gang_count", "2")

    if any(x in lower for x in ("med jord", "2p+e", "2p + e", "jordkontakt")):
        _put(specs, "has_earth", _bool_text(True))
    elif "uden jord" in lower:
        _put(specs, "has_earth", _bool_text(False))

    protocols = [name for needle, name in (("zigbee", "Zigbee"), ("matter", "Matter"), ("bluetooth", "Bluetooth"), ("wi-fi", "Wi-Fi"), ("wifi", "Wi-Fi")) if needle in lower]
    if protocols:
        _put(specs, "smart_protocol", " / ".join(dict.fromkeys(protocols)))

    if any(x in lower for x in ("dæmpbar", "dæmpning", "lysdæmper", "dimmer")) or _text(record.get("dimming_type")):
        _put(specs, "dimmable", _bool_text(True))

    m = re.search(r"(?<!\d)(\d{1,2})\s*[- ]?leder(?:e)?\b", lower)
    if m:
        _put(specs, "terminal_count", m.group(1))
    m = re.search(r"(?:maks\.?\s*)?(\d+(?:[.,]\d+)?)\s*mm[²2]\b", lower)
    if m:
        _put(specs, "conductor_cross_section", f"{m.group(1).replace(',', '.')} mm²")

    manual = record.get("technical_specs_manual")
    if isinstance(manual, dict):
        for key, value in manual.items():
            key = _text(key)
            value = _text(value)
            if key and value:
                specs[key] = value
    return specs


def spec_label(key: str) -> str:
    return _SPEC_LABELS.get(str(key), str(key).replace("_", " ").strip().capitalize())


def technical_specs_text(record: dict, *, limit: int = 8) -> list[str]:
    specs = record.get("technical_specs") if isinstance(record.get("technical_specs"), dict) else derive_technical_specs(record)
    out = []
    for key, value in specs.items():
        if _text(value):
            out.append(f"{spec_label(key)}: {_text(value)}")
        if len(out) >= max(1, int(limit)):
            break
    return out


def _variant_description(record: dict) -> str:
    text = _text(record.get("description"))
    # Remove leading manufacturer/brand prefix used by the bundled catalogue.
    if "·" in text:
        text = text.split("·", 1)[1].strip()
    removable = []
    for key in ("color", "cct"):
        value = _text(record.get(key))
        if value:
            removable.append(value)
    for value in removable:
        text = re.sub(rf"(?<!\w){re.escape(value)}(?!\w)", " ", text, flags=re.I)
    # CCT is a classic variant axis, even when the source record forgot the field.
    text = re.sub(r"(?<!\d)(?:2200|2400|2500|2700|3000|3500|4000|5000|5700|6000|6500)\s*K(?!\w)", " ", text, flags=re.I)
    text = re.sub(r"\s*[,;/·-]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def auto_variant_group_key(record: dict) -> str:
    manual = _text(record.get("variant_group_manual"))
    if manual:
        return "manual:" + manual.casefold()
    maker = _fold(record.get("manufacturer"))
    family = _fold(record.get("product_family"))
    series = _fold(record.get("series"))
    typ = _fold(record.get("product_type"))
    variant = _fold(record.get("product_variant"))
    module = _fold(record.get("module_size"))
    base = _variant_description(record)
    if not maker or not base:
        return ""
    # Family + own product variant are identity. Compatibility is deliberately
    # excluded, so a box accepting SLIM frames never joins the SLIM box family.
    if not any((family, series, typ, variant)):
        return ""
    return "|".join((maker, family or series, typ, variant, module, base))


def _variant_id(key: str) -> str:
    if not key:
        return ""
    if key.startswith("manual:"):
        raw = key.split(":", 1)[1]
        safe = re.sub(r"[^0-9a-zæøå_-]+", "-", raw, flags=re.I).strip("-")
        return "vg-manual-" + (safe[:36] or hashlib.sha1(key.encode("utf-8")).hexdigest()[:12])
    return "vg-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _variant_attributes(record: dict) -> dict[str, str]:
    out = {}
    for key in ("color", "cct", "module_size", "mounting_type"):
        value = _text(record.get(key))
        if value:
            out[key] = value
    return out


def normalize_relations(value, *, article_no: str = "") -> list[dict]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            value = json.loads(text)
        except Exception:
            return []
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    seen = set()
    for raw in value:
        if isinstance(raw, str):
            raw = {"type": "compatible", "target_article_no": raw}
        if not isinstance(raw, dict):
            continue
        target = _text(raw.get("target_article_no") or raw.get("article_no") or raw.get("target"))
        relation_type = _fold(raw.get("type") or "compatible")
        if not target or target.casefold() == _fold(article_no):
            continue
        if relation_type not in RELATION_TYPES:
            relation_type = "compatible"
        key = (relation_type, target.casefold())
        if key in seen:
            continue
        seen.add(key)
        item = {"type": relation_type, "target_article_no": target}
        source = _text(raw.get("source"))
        note = _text(raw.get("note"))
        if source:
            item["source"] = source
        if note:
            item["note"] = note
        out.append(item)
    return out


def enrich_catalog(records: Iterable[dict]) -> list[dict]:
    """Add controlled metadata and variant context to a whole catalogue."""
    rows = [deepcopy(dict(r)) for r in (records or ()) if isinstance(r, dict)]
    groups = defaultdict(list)
    for row in rows:
        semantics = derive_product_semantics(row)
        row.update(semantics)
        row.pop("semantic_source_text", None)

        # Migrate the legacy generic Design/familie field away from boxes when
        # it merely repeats a compatible design series. Preserve the old value
        # separately for traceability, but do not expose it as product identity.
        legacy_design = _text(row.get("design_family"))
        compat_designs = {x.casefold() for x in _normalise_string_list(row.get("compatibility", {}).get("design_series", []))} if isinstance(row.get("compatibility"), dict) else set()
        own_variant = _fold(row.get("product_variant"))
        is_box = "dåse" in _fold(row.get("description")) or "dåse" in _fold(row.get("product_type")) or "dåse" in _fold(row.get("category"))
        if is_box and legacy_design:
            # A box's own identity is expressed by Product family + Product
            # variant. A legacy design label is kept only as provenance; it may
            # describe compatibility and must never become the box identity.
            row.setdefault("design_family_raw", legacy_design)
            row.pop("design_family", None)

        category = derive_category(row)
        row["taxonomy_version"] = str(TAXONOMY_VERSION)
        row["category_normalized"] = category
        top, sub = taxonomy_parts(category)
        row["category_group"] = top
        row["subcategory"] = sub
        function = derive_function(row)
        if function:
            row["function"] = function
        row["technical_specs"] = derive_technical_specs(row)
        row["relations"] = normalize_relations(row.get("relations", []), article_no=_text(row.get("article_no")))
        key = auto_variant_group_key(row)
        row["variant_group_id"] = _variant_id(key)
        row["variant_attributes"] = _variant_attributes(row)
        row["variant_group_label"] = _text(row.get("variant_group_manual")) or _variant_description(row)
        if key:
            groups[key].append(row)

    for key, members in groups.items():
        axes = []
        for axis in ("color", "cct", "module_size", "mounting_type"):
            vals = {_fold(x.get(axis)) for x in members if _text(x.get(axis))}
            if len(vals) > 1:
                axes.append(axis)
        for row in members:
            row["variant_count"] = len(members)
            row["variant_axes"] = axes
    for row in rows:
        row.setdefault("variant_count", 1)
        row.setdefault("variant_axes", [])
    return rows


def variant_members(article: dict, catalog: Iterable[dict]) -> list[dict]:
    gid = _text(article.get("variant_group_id"))
    if not gid:
        return []
    no = _fold(article.get("article_no"))
    return [dict(r) for r in (catalog or ()) if _text(r.get("variant_group_id")) == gid and _fold(r.get("article_no")) != no]


def _category_sub(record: dict) -> str:
    return taxonomy_parts(_text(record.get("category_normalized") or derive_category(record)))[1]


def _functional_markers(record: dict) -> set[str]:
    hay = _fold(record.get("description"))
    markers = set()
    aliases = (
        ("korrespondance", ("korrespondance",)),
        ("krone", ("krone",)),
        ("jalousi", ("jalousi",)),
        ("dimmer", ("dimmer", "lysdæmper")),
        ("tryk", ("tryk",)),
        ("1-polet", ("1-polet", "1 polet")),
        ("timer", ("timer",)),
        ("usb", ("usb",)),
        ("data", ("rj45", "dataudtag")),
    )
    for label, needles in aliases:
        if any(n in hay for n in needles): markers.add(label)
    return markers


_SYSTEM_MARKER_ALIASES = (
    ("fuga", ("fuga",)),
    ("opus", ("opus",)),
    ("clicline", ("clic'line", "clicline")),
    ("wiser", ("wiser",)),
    ("ihc-wireless", ("ihc wireless",)),
    ("lk-one", ("lk one",)),
)


def _markers_from_text(text: str) -> set[str]:
    hay = _fold(text)
    markers = set()
    for label, needles in _SYSTEM_MARKER_ALIASES:
        if any(n in hay for n in needles):
            markers.add(label)
    return markers


def _description_system_markers(record: dict) -> set[str]:
    """System names explicitly stated in the product text.

    These are stronger evidence than imported series/design metadata.  Some
    historical catalog rows contain a correct product description but a stale
    or inherited series value, so compatibility suggestions must not let the
    latter override an explicit system name in the description.
    """
    return _markers_from_text(_text(record.get("description")))


def _system_markers(record: dict) -> set[str]:
    hay = " ".join(_text(record.get(k)) for k in ("description", "series", "design_family"))
    return _markers_from_text(hay)


def relation_context(article: dict, catalog: Iterable[dict], *, suggestion_limit: int = 16) -> dict:
    """Return confirmed relations, sibling variants and conservative candidates."""
    rows = [dict(r) for r in (catalog or ()) if isinstance(r, dict)]
    lookup = {_fold(r.get("article_no")): r for r in rows}
    source_no = _fold(article.get("article_no"))
    confirmed = []
    confirmed_targets = set()
    for rel in normalize_relations(article.get("relations", []), article_no=_text(article.get("article_no"))):
        target = lookup.get(_fold(rel.get("target_article_no")))
        item = dict(rel)
        item["type_label"] = RELATION_TYPES.get(item.get("type"), item.get("type", ""))
        item["description"] = _text(target.get("description")) if target else "(artiklen findes ikke i databasen)"
        item["manufacturer"] = _text(target.get("manufacturer")) if target else ""
        item["exists"] = bool(target)
        confirmed.append(item)
        confirmed_targets.add(_fold(rel.get("target_article_no")))

    variants = variant_members(article, rows)
    variant_rows = []
    for row in variants:
        attrs = row.get("variant_attributes", {}) if isinstance(row.get("variant_attributes"), dict) else {}
        variant_rows.append({
            "article_no": _text(row.get("article_no")),
            "description": _text(row.get("description")),
            "manufacturer": _text(row.get("manufacturer")),
            "variant": " · ".join(f"{spec_label(k)}: {v}" for k, v in attrs.items() if _text(v)),
        })

    pair_targets = {
        "Afbrydere og betjening": {"Tangenter og afdækninger", "Rammer", "Dåser og montage"},
        "Stikkontakter og udtag": {"Rammer", "Dåser og montage"},
        "Tangenter og afdækninger": {"Afbrydere og betjening"},
        "Rammer": {"Afbrydere og betjening", "Stikkontakter og udtag"},
        "Dåser og montage": {"Afbrydere og betjening", "Stikkontakter og udtag", "Rammer"},
        "Downlight og armaturer": {"Fronter og tilbehør", "Lysstyring og smart home"},
        "Fronter og tilbehør": {"Downlight og armaturer"},
        "Lampeudtag": {"Lysstyring og smart home"},
    }
    source_sub = _category_sub(article)
    allowed = pair_targets.get(source_sub, set())
    suggestions = []
    if allowed:
        a_maker = _fold(article.get("manufacturer")); a_series = _fold(article.get("series")); a_design = _fold(article.get("design_family"))
        a_family = _fold(article.get("product_family")); a_variant = _fold(article.get("product_variant"))
        a_compat = normalize_compatibility(article.get("compatibility"))
        a_compat_designs = {x.casefold() for x in a_compat.get("design_series", []) if _text(x)}
        a_module = _fold(article.get("module_size")); a_group = _fold(article.get("category_group"))
        a_markers=_functional_markers(article); a_systems=_system_markers(article)
        a_description_systems = _description_system_markers(article)
        for row in rows:
            target_no = _fold(row.get("article_no"))
            if not target_no or target_no == source_no or target_no in confirmed_targets:
                continue
            target_sub = _category_sub(row)
            if target_sub not in allowed:
                continue
            score = 25
            reasons = [f"kategori: {source_sub} ↔ {target_sub}"]
            maker = _fold(row.get("manufacturer"))
            if a_maker and maker == a_maker:
                score += 15; reasons.append("samme producent")
            elif a_maker and maker and maker != a_maker:
                # Cross-manufacturer compatibility needs explicit confirmation.
                continue
            target_family = _fold(row.get("product_family")); target_variant = _fold(row.get("product_variant"))
            target_compat = normalize_compatibility(row.get("compatibility"))
            target_compat_designs = {x.casefold() for x in target_compat.get("design_series", []) if _text(x)}
            if a_family and target_family == a_family:
                score += 20; reasons.append("samme produktfamilie")
            elif a_series and _fold(row.get("series")) == a_series:
                score += 10; reasons.append("samme kildeserie")
            if a_design and _fold(row.get("design_family")) == a_design:
                score += 6; reasons.append("samme legacy-design")
            # Compatibility is allowed to influence relation suggestions, but it
            # never changes either article's identity. For FUGA boxes/frames it
            # is stronger evidence than a shared generic source series.
            if target_variant and a_compat_designs:
                if target_variant in a_compat_designs:
                    score += 24; reasons.append("variant er eksplicit kompatibel")
                elif target_sub == "Rammer" and target_variant in {x.casefold() for x in _DESIGN_SERIES}:
                    continue
            if a_variant and target_compat_designs:
                if a_variant in target_compat_designs:
                    score += 24; reasons.append("kildevariant er eksplicit kompatibel")
                elif source_sub == "Rammer" and a_variant in {x.casefold() for x in _DESIGN_SERIES}:
                    continue
            if a_group and _fold(row.get("category_group")) == a_group:
                score += 4
            target_systems=_system_markers(row)
            target_description_systems = _description_system_markers(row)
            # Explicit product text is stronger evidence than series/design
            # metadata.  This prevents stale imported metadata from proposing
            # e.g. CLIC'LINE hardware as compatible with FUGA.
            if (a_description_systems and target_description_systems
                    and a_description_systems.isdisjoint(target_description_systems)):
                continue
            if a_systems and target_systems and a_systems.isdisjoint(target_systems):
                continue
            target_markers=_functional_markers(row)
            if a_markers and target_markers:
                if a_markers & target_markers:
                    score += 12; reasons.append("samme funktionsmarkør")
                else:
                    score -= 22
            elif a_markers:
                score -= 6
            target_module = _fold(row.get("module_size"))
            if a_module and target_module:
                if a_module == target_module:
                    score += 15; reasons.append("samme modul")
                elif source_sub in {"Afbrydere og betjening", "Stikkontakter og udtag", "Tangenter og afdækninger", "Rammer", "Dåser og montage"}:
                    continue
            if score < 65:
                continue
            suggestions.append({
                "article_no": _text(row.get("article_no")),
                "description": _text(row.get("description")),
                "manufacturer": _text(row.get("manufacturer")),
                "confidence": min(score, 88),
                "reason": " · ".join(reasons),
                "suggested_type": "compatible",
            })
    suggestions.sort(key=lambda r: (-int(r.get("confidence", 0)), _fold(r.get("description")), _fold(r.get("article_no"))))
    return {"confirmed": confirmed, "variants": variant_rows, "suggestions": suggestions[:max(1, int(suggestion_limit))]}
