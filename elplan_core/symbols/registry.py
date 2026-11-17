"""Symbolregister, kombisymboler og stabile visningsnavne."""

from __future__ import annotations

from elplan_core.constants import (
    CUSTOM_COMBO_MAX_MODULES,
    CUSTOM_COMBO_PREFIX,
    CUSTOM_SWITCH_SHORT,
    CUSTOM_SWITCH_TYPES,
    SYMBOL_GROUPS,
    SYMBOL_NAMES_BY_CODE,
    SYMBOLS,
)


COMBO_SYMBOLS = {"combo_switch_1_socket", "combo_switch_2way_socket", "combo_switch_crown_socket", "combo_switch_cross_socket", "combo_switch_double_2way_socket", "combo_pushbutton_socket", "combo_pushbutton_indicator_socket", "combo_row_2x1_socket", "combo_row_1_2way_socket", "combo_row_2way_2way_socket", "combo_row_crown_1_socket", "combo_row_3x1_socket", "combo_row_2x1_2way_socket", "combo_row_crown_2x1_socket"}


COMBO_LABEL_MODES = ("Fælles", "Opdelt")


CUSTOM_SYMBOL_NAMES: dict[str,str] = {}


COMBO_ROW_PARTS = {
    "combo_row_2x1_socket": ["switch_1", "switch_1"],
    "combo_row_1_2way_socket": ["switch_1", "switch_2way"],
    "combo_row_2way_2way_socket": ["switch_2way", "switch_2way"],
    "combo_row_crown_1_socket": ["switch_crown", "switch_1"],
    "combo_row_3x1_socket": ["switch_1", "switch_1", "switch_1"],
    "combo_row_2x1_2way_socket": ["switch_1", "switch_1", "switch_2way"],
    "combo_row_crown_2x1_socket": ["switch_crown", "switch_1", "switch_1"],
}


def custom_combo_auto_name(modules, socket_kind="none") -> str:
    """Kort, læsbart navn til symbolpaletten baseret på den aktuelle modulrække."""
    mods=[str(x) for x in (modules or [])]
    parts=[]
    i=0
    while i < len(mods):
        j=i+1
        while j < len(mods) and mods[j] == mods[i]:
            j += 1
        count=j-i
        short=CUSTOM_SWITCH_SHORT.get(mods[i], mods[i])
        parts.append(f"{count}× {short}" if count>1 else short)
        i=j
    if socket_kind == "socket":
        parts.append("Stik")
    elif socket_kind == "socket_earth":
        parts.append("Stik+J")
    return " + ".join(parts) if parts else "Brugerdefineret kombi"


def normalize_combo_template_records(records):
    out=[]; seen=set()
    for item in records or []:
        if not isinstance(item,dict):
            continue
        code=str(item.get("code", ""))
        parsed=parse_custom_combo_symbol(code) if 'parse_custom_combo_symbol' in globals() else None
        if not parsed or code in seen:
            continue
        name=str(item.get("name", "")).strip() or custom_combo_auto_name(parsed[0],parsed[1])
        out.append({"name":name,"code":code}); seen.add(code)
    return out


def symbol_display_name(code: str) -> str:
    if code in SYMBOL_NAMES_BY_CODE:
        return SYMBOL_NAMES_BY_CODE[code]
    parsed=parse_custom_combo_symbol(code)
    if parsed:
        modules,socket_kind=parsed
        return "Kombi: " + custom_combo_auto_name(modules,socket_kind)
    return code


def _split_csv_parts(value: str | None, count: int) -> list[str]:
    parts=[x.strip() for x in str(value or "").split(",")]
    if count<=0:
        return []
    if not parts:
        return [""]*count
    parts=[p for p in parts]
    if len(parts)<count:
        parts.extend([""]*(count-len(parts)))
    return parts[:count]


def parse_custom_combo_symbol(symbol: str):
    value=str(symbol or "")
    if not value.startswith(CUSTOM_COMBO_PREFIX):
        return None
    try:
        payload=value[len(CUSTOM_COMBO_PREFIX):]
        module_text,socket_kind=payload.rsplit("|",1)
        modules=[x for x in module_text.split(",") if x]
        allowed=set(CUSTOM_SWITCH_TYPES.values())
        if not (1 <= len(modules) <= CUSTOM_COMBO_MAX_MODULES) or any(x not in allowed for x in modules):
            return None
        if socket_kind not in {"none","socket","socket_earth"}:
            return None
        return modules,socket_kind
    except Exception:
        return None


def make_custom_combo_code(modules, socket_kind="none") -> str:
    allowed=set(CUSTOM_SWITCH_TYPES.values())
    mods=[str(x) for x in modules if str(x) in allowed][:CUSTOM_COMBO_MAX_MODULES]
    if not mods:
        raise ValueError("Vælg mindst én afbryder.")
    socket_kind=socket_kind if socket_kind in {"none","socket","socket_earth"} else "none"
    return CUSTOM_COMBO_PREFIX + ",".join(mods) + "|" + socket_kind


def is_custom_combo_symbol(symbol: str) -> bool:
    return parse_custom_combo_symbol(symbol) is not None


def is_combo_symbol(symbol: str) -> bool:
    return symbol in COMBO_SYMBOLS or is_custom_combo_symbol(symbol)


def is_combo_row_symbol(symbol: str) -> bool:
    return symbol in COMBO_ROW_PARTS or is_custom_combo_symbol(symbol)


def combo_modules(symbol: str) -> list[str]:
    parsed=parse_custom_combo_symbol(symbol)
    if parsed:return list(parsed[0])
    if symbol in COMBO_ROW_PARTS:return list(COMBO_ROW_PARTS[symbol])
    base=combo_switch_symbol(symbol)
    return [base] if base else []


def combo_socket_kind(symbol: str) -> str:
    parsed=parse_custom_combo_symbol(symbol)
    if parsed:return parsed[1]
    return "socket" if is_combo_symbol(symbol) else "none"


def _unique_custom_name(base: str, code: str) -> str:
    base=(str(base or "").strip() or symbol_display_name(code)).strip()
    if base not in SYMBOLS or SYMBOLS.get(base)==code:return base
    n=2
    while f"{base} ({n})" in SYMBOLS and SYMBOLS.get(f"{base} ({n})")!=code:n+=1
    return f"{base} ({n})"


def register_custom_symbol(code: str, name: str|None=None) -> str | None:
    if not is_custom_combo_symbol(code):return None
    if code in SYMBOL_NAMES_BY_CODE:
        return SYMBOL_NAMES_BY_CODE[code]
    display=_unique_custom_name(name or symbol_display_name(code),code)
    CUSTOM_SYMBOL_NAMES[code]=display
    SYMBOL_GROUPS.setdefault("Kombi",{})[display]=code
    SYMBOLS[display]=code; SYMBOL_NAMES_BY_CODE[code]=display
    return display


def custom_symbol_records():
    return [{"code":c,"name":SYMBOL_NAMES_BY_CODE.get(c,symbol_display_name(c))} for c in CUSTOM_SYMBOL_NAMES]


def register_custom_symbol_records(records):
    for item in records or []:
        if isinstance(item,dict):register_custom_symbol(str(item.get("code", "")),str(item.get("name", "")))


def combo_switch_symbol(symbol: str) -> str | None:
    if symbol in COMBO_ROW_PARTS:
        return None
    return {
        "combo_switch_1_socket": "switch_1",
        "combo_switch_2way_socket": "switch_2way",
        "combo_switch_crown_socket": "switch_crown",
        "combo_switch_cross_socket": "switch_cross",
        "combo_switch_double_2way_socket": "switch_double_2way",
        "combo_pushbutton_socket": "pushbutton",
        "combo_pushbutton_indicator_socket": "pushbutton_indicator",
    }.get(symbol)


def normalize_combo_label_mode(value: str) -> str:
    return "Opdelt" if str(value or "").strip().casefold() == "opdelt".casefold() else "Fælles"
