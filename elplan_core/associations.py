"""Rene normaliseringsprimitiver for lys- og afbryderrelationer.

Den resterende relationslogik flyttes hertil i fase 2.6.
"""

from __future__ import annotations


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
