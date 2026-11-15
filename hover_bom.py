from __future__ import annotations

"""Build the compact, VAT-aware BOM shown when a symbol is hovered.

The module is deliberately independent of Qt.  Authoritative prices remain
net prices; conversion only happens while the HTML presentation is built.
"""

from collections import defaultdict
import html
import math

import core_logic as core
import price_display


def _number(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _fmt_qty(value) -> str:
    number = float(value or 0)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.2f}".replace(".", ",")


def _fmt_price(value, currency="DKK") -> str:
    number = _number(value)
    if number is None:
        return "—"
    amount = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{amount} {str(currency or 'DKK').strip().upper() or 'DKK'}"


def _totals_text(totals, vat_mode) -> str:
    values=[]
    for currency, net_amount in sorted(dict(totals or {}).items()):
        shown=price_display.to_display_amount(net_amount, vat_mode)
        values.append(_fmt_price(shown, currency))
    return " · ".join(values) if values else "—"


def _priced_item(article_no, qty, article_lookup) -> dict:
    no=str(article_no or "").strip()
    article=dict(article_lookup.get(no, {}) or {})
    try:
        amount=float(qty or 1.0)
    except (TypeError, ValueError):
        amount=1.0
    if not math.isfinite(amount) or amount <= 0:
        amount=1.0
    unit_price=_number(article.get("effective_price", article.get("unit_price")))
    currency=str(article.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK"
    return {
        "article_no":no,
        "description":str(article.get("description", "") or "").strip(),
        "qty":amount,
        "unit_price":unit_price,
        "price_unit":str(article.get("price_unit", "") or article.get("unit", "stk") or "stk").strip() or "stk",
        "currency":currency,
        "line_total":unit_price * amount if unit_price is not None else None,
    }


def build_hover_bom_model(*, symbol, placement_uid, placement=None, article_lookup=None,
                          article_bindings=None, assembly_bindings=None, assemblies=None) -> dict:
    """Return the effective symbol BOM and net-price totals.

    An assembly replaces direct rows for the same symbol part, exactly as in
    the authoritative BOM.  Disabled optional assembly items are excluded.
    """
    uid=str(placement_uid or "").strip()
    lookup=dict(article_lookup or {})
    direct=core.normalize_symbol_article_bindings(article_bindings or {}).get(uid, {}) if uid else {}
    selected=core.normalize_symbol_assembly_bindings(assembly_bindings or {}).get(uid, {}) if uid else {}
    assembly_lookup=core.bom_assembly_lookup(assemblies or [])
    sections=[]

    for part in core.bom_symbol_parts(str(symbol or "")):
        part_id=str(part.get("id", "") or "")
        part_label=str(part.get("label", part_id) or part_id)
        assembly_id=str(selected.get(part_id, "") or "")
        assembly=assembly_lookup.get(assembly_id) if assembly_id else None
        if assembly is not None:
            raw_items=core.bom_assembly_effective_items(assembly)
            sections.append({
                "part_label":part_label,
                "kind":"assembly",
                "assembly_name":str(assembly.get("name", assembly_id) or assembly_id),
                "items":[_priced_item(row.get("article_no"), row.get("qty", 1.0), lookup) for row in raw_items],
            })
        elif assembly_id:
            sections.append({"part_label":part_label, "kind":"missing_assembly", "assembly_name":assembly_id, "items":[]})
        else:
            raw_items=list(direct.get(part_id, []) or [])
            if raw_items:
                sections.append({
                    "part_label":part_label,
                    "kind":"articles",
                    "assembly_name":"",
                    "items":[_priced_item(row.get("article_no"), row.get("qty", 1.0), lookup) for row in raw_items],
                })

    if placement is not None:
        for splice in core.normalize_pl_box_splices(getattr(placement, "pl_box_splices", []) or []):
            article_no=str(splice.get("article_no", "") or "").strip()
            if not article_no:
                continue
            function=core.pl_wiring_function_caption(str(splice.get("function", "") or ""), core.light_output_associations(placement))
            sections.append({
                "part_label":f"Wago i PL-dåse · {function}",
                "kind":"articles",
                "assembly_name":"",
                "items":[_priced_item(article_no, 1.0, lookup)],
            })

    totals=defaultdict(float); priced=0; item_count=0
    for section in sections:
        section_totals=defaultdict(float); section_priced=0
        for item in section["items"]:
            item_count += 1
            if item["line_total"] is None:
                continue
            currency=item["currency"]
            section_totals[currency] += item["line_total"]
            totals[currency] += item["line_total"]
            section_priced += 1; priced += 1
        section["totals_by_currency"]=dict(section_totals)
        section["priced_items"]=section_priced
    return {"sections":sections, "totals_by_currency":dict(totals), "priced_items":priced, "item_count":item_count}


def build_hover_bom_html(*, vat_mode="excl", max_items=10, **kwargs) -> str:
    model=build_hover_bom_model(**kwargs)
    if not model["sections"]:
        return ""
    mode=price_display.normalize_vat_mode(vat_mode)
    caption=price_display.vat_caption(mode)
    lines=[]; shown=0
    for section in model["sections"]:
        label=html.escape(section["part_label"])
        kind=section["kind"]
        if kind == "assembly":
            name=html.escape(section["assembly_name"])
            subtotal=_totals_text(section["totals_by_currency"], mode)
            lines.append(f"<b>{label}</b><br><span style='color:#64748b'>Stykliste:</span> <b>{name}</b> · styklistepris {caption}: <b>{subtotal}</b>")
        elif kind == "missing_assembly":
            lines.append(f"<b>{label}</b><br><span style='color:#b45309'>⚠ Stykliste findes ikke: {html.escape(section['assembly_name'])}</span>")
            continue
        else:
            lines.append(f"<b>{label}</b>")

        for item in section["items"]:
            if shown >= max(0, int(max_items)):
                continue
            shown += 1
            qty=item["qty"]
            qty_text=f" × {_fmt_qty(qty)}" if abs(qty - 1.0) > 1e-9 else ""
            detail=f"<b>{html.escape(item['article_no'])}</b>{qty_text}"
            if item["description"]:
                detail += f" · {html.escape(item['description'][:82])}"
            if item["unit_price"] is None:
                price="<span style='color:#b45309'>· pris mangler</span>"
            else:
                shown_unit=price_display.to_display_amount(item["unit_price"], mode)
                price=f"<span style='color:#0f766e'>· {_fmt_price(shown_unit, item['currency'])}/{html.escape(item['price_unit'])}"
                if abs(qty - 1.0) > 1e-9:
                    shown_total=price_display.to_display_amount(item["line_total"], mode)
                    price += f" · {_fmt_price(shown_total, item['currency'])} i alt"
                price += "</span>"
            lines.append(f"<span style='color:#315f8f'>●</span>&nbsp; {detail} {price}")

    hidden=max(0, model["item_count"] - shown)
    if hidden:
        lines.append(f"<span style='color:#64748b'>+ {hidden} yderligere artikelrækker</span>")
    if model["item_count"]:
        total=_totals_text(model["totals_by_currency"], mode)
        missing=model["item_count"] - model["priced_items"]
        coverage=f"pris på {model['priced_items']}/{model['item_count']} artikelrækker"
        if missing:
            coverage=f"⚠ {coverage}"
        lines.append(f"<span style='color:#334155'><b>Symboltotal {caption}:</b> {total} · {coverage}</span>")
    return "<br>".join(lines)
