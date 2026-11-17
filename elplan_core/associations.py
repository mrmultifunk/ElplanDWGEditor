"""Lysudgange og logiske relationer mellem afbrydere og lampesteder."""

from __future__ import annotations

from elplan_core.cables.geometry import rotate_point
from elplan_core.constants import LIGHT_ASSOCIATION_SYMBOLS, SWITCH_ASSOCIATION_SYMBOLS
from elplan_core.models import Placement
from elplan_core.symbols.geometry import symbol_local_bbox
from elplan_core.symbols.registry import (
    _split_csv_parts,
    combo_modules,
    combo_switch_symbol,
    is_combo_row_symbol,
    is_combo_symbol,
    normalize_combo_label_mode,
    symbol_display_name,
)


def _association_index_to_text(index: int) -> str:
    n = max(0, int(index)) + 1
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(ord("a") + r) + out
    return out


def _association_text_to_index(value: str) -> int:
    txt = str(value or "").strip().lower()
    if not txt or any(not ("a" <= c <= "z") for c in txt):
        return 10**9
    n = 0
    for c in txt:
        n = n * 26 + (ord(c) - ord("a") + 1)
    return n - 1


def normalize_associations(values) -> list[str]:
    out = []
    for raw in values or []:
        txt = str(raw or "").strip().lower()
        if txt and txt.isalpha() and txt.isascii() and txt not in out:
            out.append(txt)
    return sorted(out, key=_association_text_to_index)


def normalize_light_associations(values) -> list[str]:
    """Normalisér den ene elektriske funktion, et lampested kan tilhøre.

    Flere fysiske afbrydere kan dele samme bogstav ved korrespondance og
    krydsning. Et lampested repræsenterer derimod én tændt udgang; to
    uafhængige udgange skal modelleres som to lampesteder.
    """
    normalized=normalize_associations(values)
    return normalized[:1]


def normalize_light_outputs(values, legacy_associations=None, *, ensure_one: bool=True) -> list[dict]:
    """Normalisér de logiske tændte udgange i ét fysisk lampested.

    ``associations`` var før 0.59.81 en flad liste. Hvis der ikke findes nye
    udgangsdata, migreres hvert gammelt bogstav til sin egen udgang. Dermed
    bliver et fysisk lampeudtag stadig kun talt én gang i BOM og PL-dåsen.
    """
    rows=[]; used_ids=set()
    for index, raw in enumerate(values or []):
        if not isinstance(raw,dict):
            continue
        output_id=str(raw.get("id","") or "").strip() or f"out{index+1}"
        base=output_id; suffix=2
        while output_id in used_ids:
            output_id=f"{base}-{suffix}"; suffix+=1
        used_ids.add(output_id)
        name=str(raw.get("name","") or "").strip() or f"Tænding {len(rows)+1}"
        assoc=normalize_light_associations([raw.get("association","")])
        rows.append({"id":output_id,"name":name,"association":assoc[0] if assoc else ""})
    if not rows:
        for index, letter in enumerate(normalize_associations(legacy_associations or [])):
            rows.append({"id":f"out{index+1}","name":f"Tænding {index+1}","association":letter})
    if ensure_one and not rows:
        rows=[{"id":"out1","name":"Tænding 1","association":""}]
    return rows


def association_role(symbol: str) -> str | None:
    if symbol in SWITCH_ASSOCIATION_SYMBOLS or is_combo_symbol(symbol):
        return "switch"
    if symbol in LIGHT_ASSOCIATION_SYMBOLS:
        return "light"
    return None


def association_capacity(symbol: str) -> int:
    """Antal uafhængige betjeninger på et afbryder-symbol."""
    if is_combo_row_symbol(symbol):
        total = 0
        for base in combo_modules(symbol):
            if base in {"switch_crown", "switch_double_2way"}:
                total += 2
            elif base == "pushbutton_4":
                total += 4
            else:
                total += 1
        return total
    base = combo_switch_symbol(symbol) if is_combo_symbol(symbol) else symbol
    if base in {"switch_crown", "switch_double_2way"}:
        return 2
    if base == "pushbutton_4":
        return 4
    return 1 if association_role(symbol) == "switch" else 0


def association_channel_bases(symbol: str) -> list[str]:
    """Returnér den fysiske afbrydertype for hver uafhængig betjening.

    Listen bruges af tilknytningsguiden, så flerfunktionssymboler (krone,
    dobbelt korrespondance, 4 tryk og kombinationer) kan behandles trin for trin.
    """
    if association_role(symbol) != "switch":
        return []
    if is_combo_row_symbol(symbol):
        modules = combo_modules(symbol)
    else:
        base = combo_switch_symbol(symbol) if is_combo_symbol(symbol) else symbol
        modules = [base] if base else []
    out: list[str] = []
    for base in modules:
        if base in {"switch_crown", "switch_double_2way"}:
            out.extend([base, base])
        elif base == "pushbutton_4":
            out.extend([base] * 4)
        else:
            out.append(base)
    return out


def association_channel_base(symbol: str, index: int) -> str:
    channels = association_channel_bases(symbol)
    if not channels:
        return ""
    idx = min(max(int(index), 0), len(channels) - 1)
    return channels[idx]


def association_module_layout(symbol: str, size: float):
    """Layout for the physical switch modules and their logical channels.

    Returns tuples: (module_no, base_symbol, x, y, radius, channel_indices).
    Coordinates are local CAD symbol coordinates and mirror combo_row_base().
    """
    if association_role(symbol) != "switch":
        return []
    if is_combo_symbol(symbol):
        modules = combo_modules(symbol)
    else:
        modules = [symbol]
    modules = [m for m in modules if m]
    if not modules:
        return []
    row = is_combo_row_symbol(symbol)
    multi = row and len(modules) > 1
    module_scale = 0.82 if multi else 1.0
    step = float(size) * (0.70 if multi else 0.82)
    ys = [(len(modules)-1-i)*step for i in range(len(modules))] if row else [0.0]*len(modules)
    cursor = 0
    out = []
    for module_no, (base, cy) in enumerate(zip(modules, ys), start=1):
        cap = 2 if base in {"switch_crown", "switch_double_2way"} else (4 if base == "pushbutton_4" else 1)
        indices = tuple(range(cursor, cursor + cap))
        cursor += cap
        out.append((module_no, base, 0.0, float(cy), float(size)*module_scale*0.205, indices))
    return out


def association_channel_module(symbol: str, size: float, index: int):
    idx=max(0,int(index))
    for rec in association_module_layout(symbol,size):
        if idx in rec[5]:
            return rec
    layout=association_module_layout(symbol,size)
    return layout[-1] if layout else None


def association_channel_prefers_existing(symbol: str, index: int) -> bool:
    """Korrespondance/krydsning deler normalt samme funktion/tilhørsbogstav."""
    return association_channel_base(symbol, index) in {
        "switch_2way", "switch_cross", "switch_double_2way"
    }


def association_channel_caption(symbol: str, index: int) -> str:
    """Kort brugertekst til guidens aktuelle fysiske betjening.

    For kombisymboler vises modulnummer + type, så fx en kombination med
    1P + 1P + korrespondance ikke blot fremstår som tre anonyme betjeninger.
    """
    idx = max(0, int(index))
    base = association_channel_base(symbol, idx)

    if is_combo_row_symbol(symbol):
        cursor = 0
        for module_no, module_base in enumerate(combo_modules(symbol), start=1):
            module_cap = 2 if module_base in {"switch_crown", "switch_double_2way"} else (4 if module_base == "pushbutton_4" else 1)
            if cursor <= idx < cursor + module_cap:
                sub = idx - cursor + 1
                names = {
                    "switch_1": "1-polet",
                    "switch_2way": "korrespondance",
                    "switch_cross": "krydsning",
                    "switch_crown": "krone",
                    "switch_double_2way": "dobbelt korrespondance",
                    "pushbutton": "tryk",
                    "pushbutton_indicator": "tryk + indikator",
                    "pushbutton_4": "4-tryk",
                }
                name = names.get(module_base, "afbryder")
                if module_cap > 1:
                    return f"Modul {module_no} · {name} · tænding {sub}"
                return f"Modul {module_no} · {name}"
            cursor += module_cap

    number = idx + 1
    if base == "switch_crown":
        return f"Tænding {number}"
    if base == "switch_double_2way":
        return f"Korrespondance {number}"
    if base == "pushbutton_4":
        return f"Tryk {number}"
    return f"Betjening {number}"


def association_channel_stable_id(placement: "Placement", index: int) -> str:
    """Stabil identitet for én fysisk/logisk afbryderkanal.

    Kanalindekset følger den gemte modul-/kanalrækkefølge, mens placement.uid
    identificerer den konkrete afbryder/kombi i projektet. Der kræves derfor
    ikke et ekstra migrationsfelt i projektformatet.
    """
    return f"{str(getattr(placement, 'uid', '') or '').strip()}:{max(0, int(index))}"


def association_channel_source_mark(placement: "Placement", index: int) -> str:
    """Kort mærkning for den konkrete afbryder/modul, der ejer en kanal."""
    idx=max(0,int(index))
    # Ved opdelt kombimærkning bruges mærkningen for det fysiske modul.
    if is_combo_symbol(getattr(placement,"symbol","")) and normalize_combo_label_mode(getattr(placement,"label_mode","Fælles"))=="Opdelt":
        rec=association_channel_module(placement.symbol,getattr(placement,"size",500.0),idx)
        module_no=int(rec[0]) if rec else 1
        if is_combo_row_symbol(placement.symbol):
            count=max(1,len(combo_modules(placement.symbol)))
            groups=_split_csv_parts(getattr(placement,"switch_group",""),count)
            labels=_split_csv_parts(getattr(placement,"switch_label",""),count)
            mi=max(0,min(count-1,module_no-1))
            bits=[str(x).strip() for x in (groups[mi],labels[mi]) if str(x or "").strip()]
            if bits:return " · ".join(bits)
        else:
            bits=[str(x).strip() for x in (getattr(placement,"switch_group",""),getattr(placement,"switch_label","")) if str(x or "").strip()]
            if bits:return " · ".join(bits)
    bits=[str(x).strip() for x in (getattr(placement,"group",""),getattr(placement,"label","")) if str(x or "").strip()]
    return " · ".join(bits) if bits else symbol_display_name(str(getattr(placement,"symbol","") or ""))


def association_channel_records(placement: "Placement") -> list[dict]:
    """Beskriv alle konkrete afbryderkanaler med stabil id og tilhørsforhold."""
    if association_role(getattr(placement,"symbol",""))!="switch":
        return []
    letters=association_channel_letters(placement)
    out=[]
    for idx,letter in enumerate(letters):
        base=association_channel_base(placement.symbol,idx)
        manual=base in {"switch_2way","switch_cross","switch_double_2way"}
        out.append({
            "channel_id":association_channel_stable_id(placement,idx),
            "switch_uid":str(getattr(placement,"uid","") or ""),
            "channel_index":idx,
            "association":str(letter or ""),
            "base_symbol":base,
            "channel_caption":association_channel_caption(placement.symbol,idx),
            "source_mark":association_channel_source_mark(placement,idx),
            "source_symbol":symbol_display_name(str(getattr(placement,"symbol","") or "")),
            "manual_topology":manual,
        })
    return out


def light_output_records(placement: "Placement") -> list[dict]:
    """Returnér logiske lysudgange; andre lyssymboler får én virtuel udgang."""
    if str(getattr(placement,"symbol","") or "") == "light_connection":
        return normalize_light_outputs(
            getattr(placement,"light_outputs",[]),
            getattr(placement,"associations",[]),
        )
    assoc=normalize_light_associations(getattr(placement,"associations",[]))
    return [{"id":"","name":"Lys","association":assoc[0] if assoc else ""}]


def light_output_associations(placement: "Placement") -> list[str]:
    return normalize_associations([
        row.get("association","") for row in light_output_records(placement)
        if row.get("association","")
    ])


def sync_light_outputs(placement: "Placement", outputs=None) -> list[dict]:
    """Gem udgange og synkronisér det gamle primære associationsfelt."""
    if str(getattr(placement,"symbol","") or "") != "light_connection":
        placement.light_outputs=[]
        placement.associations=normalize_light_associations(getattr(placement,"associations",[]))
        return []
    normalized=normalize_light_outputs(
        light_output_records(placement) if outputs is None else outputs,
        getattr(placement,"associations",[]) if outputs is None else [],
    )
    placement.light_outputs=[dict(row) for row in normalized]
    primary=normalized[0].get("association","") if normalized else ""
    placement.associations=normalize_light_associations([primary])
    return normalized


def set_light_output_association(placement: "Placement", output_id: str, letter: str) -> list[dict]:
    rows=light_output_records(placement)
    target=str(output_id or "")
    value=normalize_light_associations([letter])
    for row in rows:
        if str(row.get("id","") or "") == target:
            row["association"]=value[0] if value else ""
            break
    return sync_light_outputs(placement,rows)


def light_output_by_id(placement: "Placement", output_id: str) -> dict:
    rows=light_output_records(placement)
    target=str(output_id or "")
    return next((dict(row) for row in rows if str(row.get("id","") or "")==target),dict(rows[0]))


def light_can_share_switch_group(placement: "Placement") -> bool:
    """Om lyspunktet entydigt kan indgå i handlingen »Samme tænding«."""
    if association_role(str(getattr(placement,"symbol","") or ""))!="light":
        return False
    if str(getattr(placement,"symbol","") or "")=="spot" and str(getattr(placement,"parent_light_uid","") or ""):
        return False
    # Flerudgangs-lampesteder kræver valg af den konkrete udgang.
    return len(light_output_records(placement))==1


def set_lights_shared_association(placements, letter: str) -> int:
    """Giv flere fysiske lyspunkter samme elektriske tændingsfunktion."""
    value=normalize_light_associations([letter])
    if not value:return 0
    association=value[0]; changed=0
    for placement in placements or []:
        if not light_can_share_switch_group(placement):continue
        before=light_output_associations(placement)
        if str(getattr(placement,"symbol","") or "")=="light_connection":
            output=light_output_records(placement)[0]
            set_light_output_association(placement,str(output.get("id","") or ""),association)
        else:
            placement.associations=[association]
        if before!=light_output_associations(placement):changed+=1
    return changed


def normalize_association_channels(symbol: str, channels, associations=None) -> list[str]:
    """Normalisér fast kanal->bogstav mapping for et afbrydersymbol.

    ``associations`` er den ældre flade liste og bruges som migrationskilde.
    Kanalrækkefølgen må aldrig alfabetisk sorteres, da den repræsenterer de
    fysiske betjeninger/moduler.
    """
    cap = association_capacity(symbol)
    if cap <= 0:
        return []
    out = [""] * cap
    seen: set[str] = set()
    for i, raw in enumerate(list(channels or [])[:cap]):
        txt = str(raw or "").strip().lower()
        if txt and txt.isalpha() and txt.isascii() and txt not in seen:
            out[i] = txt
            seen.add(txt)
    # Migrér gamle projekter eller udfyld manglende pladser deterministisk.
    for letter in normalize_associations(associations or []):
        if letter in seen:
            continue
        try:
            slot = out.index("")
        except ValueError:
            break
        out[slot] = letter
        seen.add(letter)
    return out


def association_channel_letters(placement: "Placement") -> list[str]:
    return normalize_association_channels(
        getattr(placement, "symbol", ""),
        getattr(placement, "association_channels", []),
        getattr(placement, "associations", []),
    )


def sync_association_channels(placement: "Placement", channels=None) -> list[str]:
    """Gem kanalrækkefølgen og hold den ældre flade associationsliste synkron.

    Når ``channels`` gives eksplicit, er den autoritativ. Den gamle flade liste
    må da ikke fylde tomme kanaler igen (vigtigt ved ryd/slet/undo).
    """
    explicit = channels is not None
    normalized = normalize_association_channels(
        getattr(placement, "symbol", ""),
        association_channel_letters(placement) if not explicit else channels,
        [] if explicit else getattr(placement, "associations", []),
    )
    placement.association_channels = list(normalized)
    placement.associations = normalize_associations([x for x in normalized if x])
    return normalized


def set_association_channel(placement: "Placement", index: int, letter: str) -> list[str]:
    channels = association_channel_letters(placement)
    if not channels:
        return []
    idx = min(max(int(index), 0), len(channels) - 1)
    value = str(letter or "").strip().lower()
    if value and (not value.isalpha() or not value.isascii()):
        value = ""
    # Én fysisk afbryder må ikke få samme relation på to forskellige kanaler.
    if value:
        channels = ["" if (i != idx and x == value) else x for i, x in enumerate(channels)]
    channels[idx] = value
    return sync_association_channels(placement, channels)


def association_display(placement: Placement) -> str:
    symbol = getattr(placement, "symbol", "")
    vals = normalize_associations(getattr(placement, "associations", []))
    if symbol == "light_connection":
        outputs=light_output_records(placement)
        assigned=[row for row in outputs if row.get("association","")]
        if len(outputs)>1:
            return " · ".join(
                f"T{i+1}:{row.get('association') or '–'}" for i,row in enumerate(outputs)
            )
        return str(assigned[0].get("association","") or "") if assigned else ""
    if association_role(symbol) == "switch":
        channels = association_channel_letters(placement)
        channel_vals = [x for x in channels if x]
        if is_combo_row_symbol(symbol) and channel_vals:
            mods = combo_modules(symbol)
            labels = []
            i = 0
            part_no = 1
            for base in mods:
                cap = 2 if base in {"switch_crown", "switch_double_2way"} else (4 if base == "pushbutton_4" else 1)
                sub = [x for x in channels[i:i + cap] if x]
                if sub:
                    labels.append(f"A{part_no}:{', '.join(sub)}")
                i += cap
                part_no += 1
            return " · ".join(labels) if labels else ", ".join(channel_vals)
        if channel_vals:
            return ", ".join(channel_vals)
    return ", ".join(vals)


def next_association_letter(placements) -> str:
    used=set()
    for p in placements:
        if association_role(getattr(p,"symbol",""))=="light":
            used.update(light_output_associations(p))
        else:
            used.update(normalize_associations(getattr(p,"associations",[])))
    i = 0
    while True:
        candidate = _association_index_to_text(i)
        if candidate not in used:
            return candidate
        i += 1


def association_world_point(placement: Placement) -> tuple[float, float]:
    """Diskret position lige ved symbollets øvre højre kant."""
    if is_combo_symbol(placement.symbol):
        lx,ly=placement.size*.30,placement.size*.20
        lx,ly=rotate_point(lx,ly,placement.rotation)
        return placement.x+lx,placement.y+ly
    x1, y1, x2, y2 = symbol_local_bbox(placement.symbol, placement.size)
    lx = x2 + placement.size * 0.07
    ly = y2 - placement.size * 0.02
    lx, ly = rotate_point(lx, ly, placement.rotation)
    return placement.x + lx, placement.y + ly
