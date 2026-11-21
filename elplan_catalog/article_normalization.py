from __future__ import annotations

"""Conservative normalisation for manufacturer/imported article data.

The importer is deliberately stricter than the generic article model.  Raw
producer values may be retained in ``*_raw`` fields, while polluted web text,
image asset names and measurement-like module values are not allowed to become
filter/source fields in the core database.
"""

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class NormalizationInfo:
    changed_fields: tuple[str, ...] = ()
    rejected: bool = False
    reason: str = ""


_LK_MAKER_WORDS = ("lauritz knudsen", "schneider electric")
_LK_SOURCE_WORDS = ("lk.dk", "www1.lk.dk")

# The colours below are source concepts observed in the LK/Schneider catalogue.
# Values are stored consistently in lower case (except the RAL notation).  The UI
# may present its own title-case facet without changing the source database.
_CANONICAL_COLORS = {
    "hvid", "lysegrå", "koksgrå", "sort", "grøn", "grå", "rød", "blå", "gul",
    "stålmetallic", "mørkegrå", "børstet aluminium", "antracitgrå", "transparent",
    "klar", "stål", "kobber", "sort/hvid", "hvid/hvid", "sort/sort", "frosted",
    "lys mellemgrå", "orange", "grå/mørkegrå", "naturel", "hvid/lysegrå",
    "transparent/orange", "rød/grøn", "hvid/blå", "RAL 7035", "sort/orange",
    "hvid/sort", "hvid/rød", "sølvgrå", "aqua", "krom", "grøn/hvid",
    "transparent/hvid", "transparent/rød", "transparent/gul",
    "transparent/lysegrå", "mørkebrun", "polar hvid", "sort/rød", "hvid/gul",
    "gul/grøn", "beige",
}
_COLOR_BY_KEY = {c.casefold(): c for c in _CANONICAL_COLORS}
_COLOR_ALIASES = {
    "børstet alu": "børstet aluminium",
    "boerstet alu": "børstet aluminium",
    "grøn og hvid": "grøn/hvid",
    "groen og hvid": "grøn/hvid",
    "transparent / orange": "transparent/orange",
    "transparent / hvid": "transparent/hvid",
    "transparent / rød": "transparent/rød",
    "transparent / rod": "transparent/rød",
    "transparent / gul": "transparent/gul",
    "transparent / lysegrå": "transparent/lysegrå",
    "sort / hvid": "sort/hvid",
    "hvid / hvid": "hvid/hvid",
    "sort / sort": "sort/sort",
    "grå / mørkegrå": "grå/mørkegrå",
    "hvid / lysegrå": "hvid/lysegrå",
    "rød / grøn": "rød/grøn",
    "hvid / blå": "hvid/blå",
    "sort / orange": "sort/orange",
    "hvid / sort": "hvid/sort",
    "hvid / rød": "hvid/rød",
    "grøn / hvid": "grøn/hvid",
    "sort / rød": "sort/rød",
    "hvid / gul": "hvid/gul",
    "gul / grøn": "gul/grøn",
}

_WEB_NOISE_RE = re.compile(
    r"(?:lk\s*nummer|varenummer|vare\s*nr|el\s*nummer|ean|kopier|produktbeskrivelse|"
    r"varianter|billede|download|katalog|\b(?:0[,.]5|1|2|3|5|10|15|20|25|50|100)\s*meter\b)",
    re.I,
)
_NON_COLOR_CONFIGURATION_RE = re.compile(
    r"(?:uden\s+(?:afdæk(?:ning|\.)?|tangent)|u\.\s*tang|afdækning\s*med|kode\s+med)",
    re.I,
)

# Asset suffixes observed in LK/Schneider image filenames.  Real catalogue
# numbers in the data set do not use underscores; hyphens remain allowed for
# Schneider product references such as MEG4010-6534.
_ASSET_SUFFIX_RE = re.compile(r"_(?:\d+|web|angle|image|front|back|side|detail|thumb|small|large)$", re.I)


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_lk_record(row: dict) -> bool:
    if not isinstance(row, dict):
        return False
    maker = _text(row.get("manufacturer")).casefold()
    source = " ".join(_text(row.get(k)) for k in ("source", "product_page", "image_url")).casefold()
    return any(x in maker for x in _LK_MAKER_WORDS) or any(x in source for x in _LK_SOURCE_WORDS)


def normalize_article_no(value: str) -> str:
    """Return a clean plausible catalogue number or an empty string.

    Whitespace and accidental terminal punctuation from prose are removed for
    newly parsed values.  Underscore-based image assets are rejected.
    """
    raw = re.sub(r"\s+", "", str(value or "").strip())
    raw = raw.strip(".,;:")
    low=raw.casefold()
    if not raw or len(raw) > 32 or "_" in raw or _ASSET_SUFFIX_RE.search(raw):
        return ""
    if any(word in low for word in ("appicon", "download", "brochure", "thumbnail", "placeholder", "sprite")):
        return ""
    if raw.isdigit() and len(raw) == 13:  # discovery EAN, not a producer number
        return ""
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z./-]{2,31}", raw):
        return ""
    return raw


def is_valid_discovery_ref(value: str) -> bool:
    raw = str(value or "").strip().strip("'\"&?#/;)")
    if raw.isdigit() and len(raw) == 13:
        return True
    clean=normalize_article_no(raw)
    return bool(clean and any(ch.isdigit() for ch in clean))


def normalize_description(value: str) -> str:
    text = _text(value)
    if not text:
        return ""
    # Preserve manufacturer wording, only repair mechanical scrape/spacing noise.
    text = re.sub(r"\s*·\s*", " · ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _append_note(note: str, extra: str) -> str:
    note = _text(note)
    extra = _text(extra)
    if not extra:
        return note
    if extra.casefold() in note.casefold():
        return note
    return f"{note} · {extra}" if note else extra


def normalize_color(value: str, *, description: str = "", trusted_source_field: bool = False) -> tuple[str, str]:
    """Return ``(canonical_color, note_extra)``.

    ``trusted_source_field`` means the value came from an explicit producer
    colour label on the currently parsed page.  Existing legacy records are
    treated more conservatively because old scraper versions sometimes filled
    the colour field with material names or neighbouring UI text.
    """
    raw = _text(value)
    if not raw:
        return "", ""
    if _WEB_NOISE_RE.search(raw):
        return "", ""
    if _NON_COLOR_CONFIGURATION_RE.search(raw):
        return "", f"Variant: {raw}"

    compact = re.sub(r"\s*/\s*", "/", raw).strip()
    key = compact.casefold()
    if key == "hvid, antibakteriel":
        return "hvid", "Egenskab: antibakteriel"
    key = _COLOR_ALIASES.get(key, key)
    canonical = _COLOR_BY_KEY.get(str(key).casefold(), "")
    if not canonical:
        return "", ""

    # Material words were a major source of false colours in legacy data.  When
    # there is no proof that the value came from a dedicated colour field, keep
    # them only for products whose own description clearly uses them as finish.
    if not trusted_source_field and canonical in {"stål", "kobber"}:
        desc = _text(description).casefold()
        finish_context = any(x in desc for x in ("ramme", "afdæk", "tangent", "front", "design"))
        if canonical not in desc or not finish_context:
            return "", ""
    return canonical, ""


def normalize_module(value: str) -> str:
    """Conservatively normalise an explicit module value.

    Accepted: half-module increments up to 12M and structured cabinet widths
    Nx13M/Nx18M (1..4 rows). Measurements such as 451200M, 600x400M and cable
    lengths are rejected.
    """
    text = _text(value).replace("×", "x").replace(",", ".").replace("½", ".5")
    text = re.sub(r"\s+", "", text)

    def fmt(num: float) -> str:
        if num.is_integer():
            return str(int(num))
        if abs((num % 1.0) - 0.5) < 1e-9:
            whole = int(num)
            return (str(whole) if whole else "") + "½"
        return ""

    m = re.fullmatch(r"(\d+)x(\d+(?:\.5)?)M", text, re.I)
    if m:
        count = int(m.group(1)); size = float(m.group(2))
        if count in range(1, 7) and 0.5 <= size <= 6 and abs(size * 2 - round(size * 2)) < 1e-9 and count * size <= 12:
            return f"{count}×{fmt(size)}M"
        if count in range(1, 5) and size in (13.0, 18.0):
            return f"{count}×{int(size)}M"
        return ""
    m = re.fullmatch(r"((?:\d+(?:\.5)?|\.5))M", text, re.I)
    if not m:
        return ""
    size = float(m.group(1))
    if not (0.5 <= size <= 12.0 and abs(size * 2 - round(size * 2)) < 1e-9):
        return ""
    return f"{fmt(size)}M"


def infer_module_from_description(description: str) -> str:
    text = _text(description).replace("×", "x")
    # Prefer explicit 'mod/modul' wording. A bare module suffix is accepted only
    # as uppercase M; lower-case 'm' is a metre and must never become a module.
    number=r"(?:\d{1,2}(?:[,.]5|½)?|½)"
    patterns = (
        (rf"(?<!\w)(\d{{1,2}}\s*x\s*{number})(?:\s*)(?:mod(?:ul)?(?:er)?)\b", re.I),
        (rf"(?<!\w)({number})(?:\s*)(?:modul(?:er)?)\b", re.I),
        (rf"(?<!\w)(\d{{1,2}}\s*x\s*{number})\s*M(?![\w])", 0),
        (rf"(?<!\w)({number})\s*M(?![\w])", 0),
    )
    for pattern,flags in patterns:
        for m in re.finditer(pattern, text, flags):
            candidate = m.group(1) + "M"
            normalized = normalize_module(candidate)
            if normalized:
                return normalized
    return ""

def normalize_lk_article(row: dict, *, parsed_now: bool = False) -> tuple[dict | None, NormalizationInfo]:
    """Normalise one LK/Schneider row. Returns ``None`` for safe-to-drop assets."""
    if not isinstance(row, dict):
        return None, NormalizationInfo(rejected=True, reason="not_a_record")
    out = dict(row)
    changed: list[str] = []

    raw_no = _text(out.get("article_no"))
    clean_no = normalize_article_no(raw_no)
    # Existing records ending in punctuation/underscore are known scrape assets
    # or cross-variant artefacts; do not merge them into a real product number.
    if not clean_no or (not parsed_now and clean_no != raw_no) or (parsed_now and not any(ch.isdigit() for ch in clean_no)):
        return None, NormalizationInfo(rejected=True, reason="invalid_or_asset_article_no")
    if clean_no != raw_no:
        out["article_no"] = clean_no; changed.append("article_no")

    desc = normalize_description(out.get("description"))
    if desc != _text(out.get("description")):
        out["description"] = desc; changed.append("description")

    raw_color = _text(out.get("color"))
    trusted_color = parsed_now or bool(_text(out.get("color_raw")))
    color, note_extra = normalize_color(raw_color, description=desc, trusted_source_field=trusted_color)
    if raw_color:
        # Only retain raw values that look like actual producer data/configuration;
        # web chrome such as "LK nummer: ... Kopier" has no source-data value.
        if not _WEB_NOISE_RE.search(raw_color) and len(raw_color) <= 80:
            if _text(out.get("color_raw")) != raw_color:
                out["color_raw"] = raw_color; changed.append("color_raw")
    if color:
        if _text(out.get("color")) != color:
            out["color"] = color; changed.append("color")
    elif "color" in out:
        out.pop("color", None); changed.append("color")
    if note_extra:
        new_note = _append_note(out.get("note", ""), note_extra)
        if new_note != _text(out.get("note")):
            out["note"] = new_note; changed.append("note")

    raw_module = _text(out.get("module_size"))
    raw_module_norm = normalize_module(raw_module) if raw_module else ""
    inferred = infer_module_from_description(desc)
    desc_cf=desc.casefold()
    safe_legacy_type=any(x in desc_cf for x in ("fuga", "opus")) and any(
        x in desc_cf for x in ("ramme", "dåse", "tangent", "afdæk", "blænddæksel", "stikkontakt", "afbryder")
    )
    module = inferred or (raw_module_norm if raw_module_norm and (parsed_now or safe_legacy_type) else "")
    if raw_module:
        if module != raw_module:
            if _text(out.get("module_size_raw")) != raw_module:
                out["module_size_raw"] = raw_module; changed.append("module_size_raw")
            if module:
                out["module_size"] = module; changed.append("module_size")
            elif "module_size" in out:
                out.pop("module_size", None); changed.append("module_size")
    elif module:
        out["module_size"] = module; changed.append("module_size")

    return out, NormalizationInfo(tuple(dict.fromkeys(changed)))


def normalize_lk_catalog(records: Iterable[dict], *, parsed_now: bool = False) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    stats = {"input": 0, "output": 0, "rejected": 0, "changed_articles": 0, "changed_fields": 0}
    for raw in records or ():
        stats["input"] += 1
        if not isinstance(raw, dict):
            stats["rejected"] += 1
            continue
        if not is_lk_record(raw):
            out = dict(raw)
            no = _text(out.get("article_no"))
            if not no or no.casefold() in seen:
                continue
            seen.add(no.casefold()); rows.append(out); continue
        out, info = normalize_lk_article(raw, parsed_now=parsed_now)
        if out is None:
            stats["rejected"] += 1
            continue
        key = _text(out.get("article_no")).casefold()
        if not key or key in seen:
            stats["rejected"] += 1
            continue
        seen.add(key); rows.append(out)
        if info.changed_fields:
            stats["changed_articles"] += 1
            stats["changed_fields"] += len(info.changed_fields)
    stats["output"] = len(rows)
    return rows, stats
