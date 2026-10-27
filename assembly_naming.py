from __future__ import annotations

"""Deterministisk navnehjælp til globale styklister.

0.59.33 samler brugerens frie navn og de strukturerede navneparametre i samme arbejdsgang.  De
strukturerede felter kan bruges til sortering/filtrering i styklistebiblioteket,
mens selve navnet altid må redigeres manuelt.

System-/serielisten er bevidst kurateret.  Den indeholder kun betegnelser, der
kan dokumenteres i LK/Schneider Electric-materiale, og skelner mellem FUGA-
designserier, installationssystemer og øvrige produktprogrammer.  Dermed bliver
fx AIR ikke fejlagtigt behandlet som en designserie.
"""

import re
from typing import Iterable, Mapping

TYPE_OPTIONS = (
    "",
    "Stikkontakt",
    "Afbryder",
    "Kombiafbryder",
    "Lampeudtag",
    "Spot",
    "PIR",
    "Dataudtag",
    "TV-/antenneudtag",
    "USB-udtag",
    "Lysdæmper",
    "Ringetryk",
    "Dåse",
    "Ramme",
    "Wago / samling",
    "Andet",
)

CONFIGURATION_OPTIONS = (
    "",
    "1M",
    "1½M",
    "2M",
    "2½M",
    "3M",
    "3½M",
    "2×1M",
    "2×1½M",
    "3×1M",
    "3×1½M",
    "2×2M",
)

FUNCTION_OPTIONS = (
    "",
    "1-polet",
    "2-polet",
    "Krone",
    "Korrespondance",
    "Dobbelt korrespondance",
    "Krydsning",
    "Tryk",
    "4-tryk",
    "Med jord",
    "Uden jord",
    "Med USB",
    "Original",
    "Dæmpbar",
)

MOUNTING_OPTIONS = (
    "",
    "Forfra",
    "Indmuring",
    "Indstøbning",
    "Planforsænket",
    "Udvendig",
)

# Kurateret registry. ``value`` er det stabile felt, som gemmes i styklister.
# ``label`` giver kontekst i dropdown'en uden at forurene det genererede navn.
# ``status`` bruges kun som forklarende metadata; legacy-produkter er stadig
# reelle og nyttige i renoveringsprojekter.
SYSTEM_SERIES = (
    {"value": "", "label": "Ikke angivet", "kind": ""},
    {"value": "LK FUGA", "label": "LK FUGA — produktprogram", "kind": "Produktprogram"},
    {"value": "LK FUGA AIR", "label": "LK FUGA AIR — installationssystem", "kind": "Installationssystem"},
    {"value": "LK FUGA AIR SLIM", "label": "LK FUGA AIR SLIM — installationsvariant", "kind": "Installationsvariant"},
    {"value": "LK FUGA SLIM", "label": "LK FUGA SLIM — designserie", "kind": "Designserie"},
    {"value": "LK FUGA SOFT", "label": "LK FUGA SOFT — designserie", "kind": "Designserie"},
    {"value": "LK FUGA PURE", "label": "LK FUGA PURE — designserie", "kind": "Designserie"},
    {"value": "LK FUGA CHOICE", "label": "LK FUGA CHOICE — designserie", "kind": "Designserie"},
    {"value": "LK FUGA BASE 63", "label": "LK FUGA BASE 63 — designserie", "kind": "Designserie"},
    {"value": "LK FUGA BASELINE 50", "label": "LK FUGA BASELINE 50 — designserie", "kind": "Designserie"},
    {"value": "LK FUGA SOFTLINE 63", "label": "LK FUGA SOFTLINE 63 — ældre designserie", "kind": "Designserie", "status": "legacy"},
    {"value": "LK FUGA SOFTLINE 68", "label": "LK FUGA SOFTLINE 68 — ældre designserie", "kind": "Designserie", "status": "legacy"},
    {"value": "LK OPUS 66", "label": "LK OPUS 66 — produktprogram", "kind": "Produktprogram"},
    {"value": "LK OPUS 74", "label": "LK OPUS 74 — produktprogram", "kind": "Produktprogram"},
    {"value": "LK CLIC'LINE", "label": "LK CLIC'LINE — produktprogram", "kind": "Produktprogram"},
    {"value": "Wiser", "label": "Wiser — smart home-system", "kind": "Smart home-system"},
)
SYSTEM_OPTIONS = tuple(row["value"] for row in SYSTEM_SERIES)
SYSTEM_LABELS = {row["value"]: row["label"] for row in SYSTEM_SERIES}
SYSTEM_KINDS = {row["value"]: row.get("kind", "") for row in SYSTEM_SERIES}
SYSTEM_VALUES_CASEFOLD = {str(v).casefold(): v for v in SYSTEM_OPTIONS if v}
SYSTEM_ALIASES = {
    "fuga": "LK FUGA",
    "fuga air": "LK FUGA AIR",
    "fuga air slim": "LK FUGA AIR SLIM",
    "fuga slim": "LK FUGA SLIM",
    "fuga soft": "LK FUGA SOFT",
    "fuga pure": "LK FUGA PURE",
    "fuga choice": "LK FUGA CHOICE",
    "fuga base 63": "LK FUGA BASE 63",
    "base 63": "LK FUGA BASE 63",
    "fuga baseline 50": "LK FUGA BASELINE 50",
    "baseline 50": "LK FUGA BASELINE 50",
    "fuga softline 63": "LK FUGA SOFTLINE 63",
    "softline 63": "LK FUGA SOFTLINE 63",
    "fuga softline 68": "LK FUGA SOFTLINE 68",
    "softline 68": "LK FUGA SOFTLINE 68",
    "opus 66": "LK OPUS 66",
    "opus 74": "LK OPUS 74",
    "clicline": "LK CLIC'LINE",
    "clic'line": "LK CLIC'LINE",
    "wiser": "Wiser",
}

COLOR_OPTIONS = (
    "",
    "Hvid",
    "Lysegrå",
    "Grå",
    "Koksgrå",
    "Sort",
    "Antracit",
    "Blå",
    "Aluminium",
    "Stål",
    "Stål metallic",
    "Messing",
)

NAMING_KEYS = (
    "product_type",
    "configuration",
    "function",
    "system_series",
    "mounting",
    "color",
    "extra",
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_naming_fields(value: Mapping[str, object] | None) -> dict[str, str]:
    raw = dict(value or {})
    # 0.59.31 kaldte opbygning/funktion samlet ``execution`` og systemfeltet
    # blot ``system``. Accepter begge ved migration.
    configuration = _clean(raw.get("configuration", ""))
    function = _clean(raw.get("function", ""))
    legacy_execution = _clean(raw.get("execution", ""))
    if legacy_execution and not (configuration or function):
        if legacy_execution in CONFIGURATION_OPTIONS:
            configuration = legacy_execution
        else:
            function = legacy_execution
    system = _clean(raw.get("system_series", raw.get("system", "")))
    canonical = (SYSTEM_VALUES_CASEFOLD.get(system.casefold()) or SYSTEM_ALIASES.get(system.casefold(), "")) if system else ""
    # Strukturerede systemværdier må kun være fra det verificerede registry.
    # Ukendte gamle værdier bliver ikke løftet ind i filterfeltet; det frie navn
    # bevares uændret i selve styklisteposten.
    system = canonical
    return {
        "product_type": _clean(raw.get("product_type", "")),
        "configuration": configuration,
        "function": function,
        "system_series": system,
        "mounting": _clean(raw.get("mounting", "")),
        "color": _clean(raw.get("color", "")),
        "extra": _clean(raw.get("extra", "")),
    }


def build_assembly_name(*, product_type: str = "", configuration: str = "", function: str = "", system_series: str = "", mounting: str = "", color: str = "", extra: str = "", execution: str = "", system: str = "") -> str:
    """Byg et ensartet navn fra brugerens strukturerede valg.

    ``execution``/``system`` accepteres fortsat for 0.59.31-kompatibilitet.
    """
    if execution and not (configuration or function):
        if _clean(execution) in CONFIGURATION_OPTIONS:
            configuration = execution
        else:
            function = execution
    if system and not system_series:
        system_series = system
    system_series = normalize_naming_fields({"system_series": system_series})["system_series"]
    # Det strukturerede filterfelt beholder den verificerede producentbetegnelse
    # (fx ``LK FUGA SLIM``), mens selve stykliste-navnet holdes kompakt og i
    # samme stil som de eksisterende brugeroprettede styklister.
    system_name = _clean(system_series)
    if system_name.startswith("LK "):
        system_name = system_name[3:]
    return " ".join(
        part for part in (
            _clean(configuration),
            system_name,
            _clean(mounting),
            _clean(product_type),
            _clean(function),
            _clean(color),
            _clean(extra),
        ) if part
    )


def naming_summary(fields: Mapping[str, object] | None) -> str:
    values = normalize_naming_fields(fields)
    return " · ".join(values[k] for k in NAMING_KEYS if k != "extra" and values.get(k))


def _contains(text: str, *needles: str) -> bool:
    hay = text.casefold()
    return all(n.casefold() in hay for n in needles)


def _first_type(text: str) -> str:
    checks = (
        ("Kombiafbryder", ("kombiafbryder",)),
        ("Lampeudtag", ("lampeudtag",)),
        ("Stikkontakt", ("stikkontakt",)),
        ("Afbryder", ("afbryder",)),
        ("Dataudtag", ("dataudtag",)),
        ("TV-/antenneudtag", ("antenneudtag",)),
        ("USB-udtag", ("usb", "udtag")),
        ("Lysdæmper", ("lysdæmper",)),
        ("Ringetryk", ("ringetryk",)),
        ("PIR", ("pir",)),
        ("Spot", ("spot",)),
        ("Wago / samling", ("wago",)),
        ("Dåse", ("dåse",)),
        ("Ramme", ("ramme",)),
    )
    for label, needles in checks:
        if _contains(text, *needles):
            return label
    return ""


def _first_system(text: str) -> str:
    # Specifikke betegnelser først; kun registry-værdier må returneres.
    checks = (
        ("LK FUGA AIR SLIM", (("fuga", "air", "slim"),)),
        ("LK FUGA SOFTLINE 68", (("fuga", "softline", "68"), ("softline 68",))),
        ("LK FUGA SOFTLINE 63", (("fuga", "softline", "63"), ("softline 63",), ("fuga", "softline"))),
        ("LK FUGA BASELINE 50", (("fuga", "baseline", "50"), ("baseline 50",))),
        ("LK FUGA BASE 63", (("fuga", "base 63"), ("base 63",), ("baseline 63",))),
        ("LK FUGA CHOICE", (("fuga", "choice"),)),
        ("LK FUGA PURE", (("fuga", "pure"),)),
        ("LK FUGA SOFT", (("fuga", "soft"),)),
        ("LK FUGA SLIM", (("fuga", "slim"),)),
        ("LK FUGA AIR", (("fuga", "air"),)),
        ("LK OPUS 74", (("opus", "74"),)),
        ("LK OPUS 66", (("opus", "66"),)),
        ("LK CLIC'LINE", (("clic'line",), ("clicline",))),
        ("Wiser", (("wiser",),)),
        ("LK FUGA", (("lk fuga",), ("fuga",))),
    )
    for label, alternatives in checks:
        if any(_contains(text, *needles) for needles in alternatives):
            return label
    return ""


def _first_color(text: str) -> str:
    checks = (
        ("Stål metallic", ("stål metallic", "staal metallic", "stålmetallic", "staalmetallic")),
        ("Koksgrå", ("koksgrå", "koksgraa")),
        ("Lysegrå", ("lysegrå", "lysegraa")),
        ("Antracit", ("antracit",)),
        ("Aluminium", ("aluminium",)),
        ("Messing", ("messing",)),
        ("Hvid", ("hvid",)),
        ("Sort", ("sort",)),
        ("Blå", ("blå", "blaa")),
        ("Stål", ("stål", "staal")),
        ("Grå", (" grå", " graa")),
    )
    hay = " " + text.casefold()
    for label, needles in checks:
        if any(n.casefold() in hay for n in needles):
            return label
    return ""


def _first_configuration(text: str) -> str:
    folded = text.casefold().replace("×", "x")
    patterns = (
        ("3×1½M", r"\b3\s*x\s*1(?:½|[,.]5)\s*m\b"),
        ("2×1½M", r"\b2\s*x\s*1(?:½|[,.]5)\s*m\b"),
        ("3×1M", r"\b3\s*x\s*1\s*m\b"),
        ("2×1M", r"\b2\s*x\s*1\s*m\b"),
        ("2×2M", r"\b2\s*x\s*2\s*m\b"),
        ("3½M", r"\b3(?:½|[,.]5)\s*m\b"),
        ("2½M", r"\b2(?:½|[,.]5)\s*m\b"),
        ("1½M", r"\b1(?:½|[,.]5)\s*m\b"),
        ("3M", r"\b3\s*m\b"),
        ("2M", r"\b2\s*m\b"),
        ("1M", r"\b1\s*m\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, folded, flags=re.IGNORECASE):
            return label
    return ""


def _first_function(text: str) -> str:
    folded = text.casefold()
    checks = (
        ("Dobbelt korrespondance", "dobbelt korrespondance"),
        ("Korrespondance", "korrespondance"),
        ("Krydsning", "krydsning"),
        ("Krone", "krone"),
        ("4-tryk", "4-tryk"),
        ("2-polet", "2-polet"),
        ("1-polet", "1-polet"),
        ("Med USB", "usb"),
        ("Med jord", "med jord"),
        ("Uden jord", "uden jord"),
        ("Dæmpbar", "dæmp"),
        ("Original", "original"),
        ("Tryk", "tryk"),
    )
    for label, needle in checks:
        if needle in folded:
            return label
    return ""


def _first_mounting(text: str) -> str:
    folded = text.casefold()
    checks = (
        ("Forfra", ("forfra", "isætning forfra", "isaetning forfra")),
        ("Indmuring", ("indmuring", "indmurings")),
        ("Indstøbning", ("indstøbning", "indstoebning", "indstøbnings", "indstoebnings")),
        ("Planforsænket", ("planforsænket", "planforsaenket")),
        ("Udvendig", ("udvendig", "underlag")),
    )
    for label, needles in checks:
        if any(n in folded for n in needles):
            return label
    return ""


def _article_text(record: Mapping[str, object], catalog: Iterable[Mapping[str, object]] | Mapping[str, Mapping[str, object]]) -> str:
    # Reuse a caller-provided article lookup when many styklister are analysed
    # together.  Rebuilding a 3k+ item dictionary once per stykliste was a
    # surprisingly large part of opening Artikler/BOM.
    if isinstance(catalog, Mapping):
        lookup = catalog
    else:
        lookup = {str(a.get("article_no", "") or ""): a for a in catalog or []}
    parts: list[str] = []
    for item in record.get("items", []) or []:
        article_no = str((item or {}).get("article_no", "") or "")
        art = lookup.get(article_no, {})
        for key in (
            "description", "name", "product_family", "product_variant", "variant",
            "color", "manufacturer", "series", "mounting_type", "product_type",
        ):
            value = _clean(art.get(key, ""))
            if value:
                parts.append(value)
    return " ".join(parts)


def _remove_once(text: str, phrase: str) -> str:
    if not text or not phrase:
        return text
    escaped = re.escape(phrase)
    escaped = escaped.replace("×", "[xX×]").replace(r"\½", r"(?:½|[,.]5)")
    return re.sub(escaped, " ", text, count=1, flags=re.IGNORECASE)


def _infer_extra(name: str, fields: Mapping[str, str]) -> str:
    remainder = _clean(name)
    if not remainder:
        return ""
    for key in ("configuration", "system_series", "product_type", "function", "mounting", "color"):
        remainder = _remove_once(remainder, fields.get(key, ""))
        # Navne fra 0.59.31 kunne mangle LK-præfikset.
        if key == "system_series" and fields.get(key, "").startswith("LK "):
            remainder = _remove_once(remainder, fields[key][3:])
    remainder = re.sub(r"\s+", " ", remainder).strip(" ·-_/,.")
    if remainder.casefold() in {"lk", "schneider", "schneider electric"}:
        return ""
    return remainder


def infer_assembly_name_fields(record: Mapping[str, object] | None, catalog: Iterable[Mapping[str, object]] = ()) -> dict[str, str]:
    """Konservative forslag baseret på gemte felter, navn og komponenter."""
    rec = dict(record or {})
    stored = normalize_naming_fields(rec.get("naming", {}))
    name = _clean(rec.get("name", ""))
    category = _clean(rec.get("category", ""))
    variant = _clean(rec.get("variant", ""))
    local_text = " ".join(x for x in (name, category, variant) if x)
    component_text = _article_text(rec, catalog)

    values = dict(stored)
    values["product_type"] = values["product_type"] or _first_type(local_text) or _first_type(component_text)
    values["configuration"] = values["configuration"] or _first_configuration(" ".join(x for x in (name, variant) if x))
    values["function"] = values["function"] or _first_function(local_text) or _first_function(component_text)
    values["system_series"] = values["system_series"] or _first_system(local_text) or _first_system(component_text)
    values["mounting"] = values["mounting"] or _first_mounting(local_text) or _first_mounting(component_text)
    values["color"] = values["color"] or _first_color(local_text) or _first_color(component_text)
    if not values["extra"]:
        values["extra"] = _infer_extra(name, values)
    return normalize_naming_fields(values) | {"extra": values.get("extra", "")}


def effective_naming_fields(record: Mapping[str, object] | None, catalog: Iterable[Mapping[str, object]] = ()) -> dict[str, str]:
    """Felter til UI/filter. Gemte værdier vinder; ældre styklister kan udledes."""
    return infer_assembly_name_fields(record, catalog)
