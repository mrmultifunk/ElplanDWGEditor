from __future__ import annotations

"""VAT-aware price presentation without changing Elplan's net-price model.

All authoritative article and BOM prices remain stored excluding VAT.  This
module only converts copies for display and export.  Retail observations are
the exception: they already contain both exact webshop values and are read
directly in the selected mode.
"""

from copy import deepcopy


VAT_MODE_EXCL = "excl"
VAT_MODE_INCL = "incl"
DEFAULT_VAT_RATE = 0.25
PRICE_FIELDS = ("estimated_price", "manual_price", "unit_price", "line_total")


def normalize_vat_mode(value) -> str:
    return VAT_MODE_INCL if str(value or "").strip().casefold() == VAT_MODE_INCL else VAT_MODE_EXCL


def vat_caption(value) -> str:
    return "inkl. moms" if normalize_vat_mode(value) == VAT_MODE_INCL else "ekskl. moms"


def to_display_amount(value, vat_mode=VAT_MODE_EXCL, vat_rate=DEFAULT_VAT_RATE):
    if value is None or str(value).strip() == "":
        return None
    amount = float(value)
    if normalize_vat_mode(vat_mode) == VAT_MODE_INCL:
        amount *= 1.0 + float(vat_rate)
    return amount


def from_display_amount(value, vat_mode=VAT_MODE_EXCL, vat_rate=DEFAULT_VAT_RATE):
    if value is None or str(value).strip() == "":
        return None
    amount = float(value)
    if normalize_vat_mode(vat_mode) == VAT_MODE_INCL:
        divisor = 1.0 + float(vat_rate)
        if divisor <= 0:
            raise ValueError("Momssatsen skal være større end -100 %.")
        amount /= divisor
    return amount


def convert_bom_rows(rows, vat_mode=VAT_MODE_EXCL, vat_rate=DEFAULT_VAT_RATE):
    """Return converted row copies suitable for the selected export mode."""
    mode = normalize_vat_mode(vat_mode)
    converted = []
    for raw in rows or []:
        row = deepcopy(dict(raw or {}))
        for key in PRICE_FIELDS:
            if row.get(key) is not None and str(row.get(key)).strip() != "":
                row[key] = to_display_amount(row[key], mode, vat_rate)
        converted.append(row)
    return converted


def _number(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def comparison_rows(price_record, vat_mode=VAT_MODE_EXCL):
    """Build comparable retailer rows from exact stored observations.

    The cheapest marker and difference are calculated independently for every
    currency/unit pair.  One current observation per provider is kept.
    """
    mode = normalize_vat_mode(vat_mode)
    selected = {}
    observations = list(dict(price_record or {}).get("price_observations", []) or [])
    for index, raw in enumerate(observations):
        if not isinstance(raw, dict):
            continue
        obs = dict(raw)
        provider_key = str(obs.get("provider_key", "") or obs.get("provider", "") or index).casefold()
        price_key = "price_incl_vat" if mode == VAT_MODE_INCL else "price_excl_vat"
        unit_price = _number(obs.get(price_key))
        if unit_price is None:
            continue
        rank = (str(obs.get("checked", "") or ""), index)
        current = selected.get(provider_key)
        if current is None or rank >= current[0]:
            selected[provider_key] = (rank, obs, unit_price)

    rows = []
    for _rank, obs, unit_price in selected.values():
        package_key = "raw_price_incl_vat" if mode == VAT_MODE_INCL else "raw_price_excl_vat"
        package_price = _number(obs.get(package_key))
        package_quantity = _number(obs.get("package_quantity")) or 1.0
        if package_quantity <= 1.0001 and not str(obs.get("package_label", "") or "").strip():
            package_price = None
        rows.append({
            "provider": str(obs.get("provider", "") or obs.get("provider_key", "") or "Webshop"),
            "provider_key": str(obs.get("provider_key", "") or ""),
            "unit_price": unit_price,
            "currency": str(obs.get("currency", "DKK") or "DKK").upper(),
            "price_unit": str(obs.get("price_unit", "stk") or "stk"),
            "package_price": package_price,
            "package_quantity": package_quantity,
            "package_label": str(obs.get("package_label", "") or ""),
            "url": str(obs.get("url", "") or ""),
            "checked": str(obs.get("checked", "") or ""),
            "matched_by": str(obs.get("matched_by", "") or ""),
            "matched_value": str(obs.get("matched_value", "") or ""),
            "confidence": str(obs.get("confidence", "") or ""),
            "vat_mode": mode,
        })

    cheapest = {}
    for row in rows:
        group = (row["currency"], row["price_unit"].casefold())
        cheapest[group] = min(row["unit_price"], cheapest.get(group, row["unit_price"]))
    for row in rows:
        best = cheapest[(row["currency"], row["price_unit"].casefold())]
        difference = row["unit_price"] - best
        row["difference"] = difference
        row["difference_percent"] = (difference / best * 100.0) if best else 0.0
        row["is_cheapest"] = abs(difference) < 1e-9
    rows.sort(key=lambda row: (row["currency"], row["price_unit"].casefold(), row["unit_price"], row["provider"].casefold()))
    return rows
