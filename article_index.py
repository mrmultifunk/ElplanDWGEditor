from __future__ import annotations

"""Reusable in-memory search metadata and ranking for the article catalogue."""

from collections.abc import Iterable
import re
import unicodedata

import core_logic as core

ARTICLE_SEARCH_FIELDS = (
    "article_no", "description", "manufacturer", "series", "category", "el_no", "ean", "status",
    "cable_spec", "product_type", "design_family", "module_size", "module_group", "color", "mounting_type",
    "category_normalized", "category_group", "subcategory", "function", "brand", "variant_group_label",
    "product_family", "product_variant",
    "diameter_mm", "cutout_mm", "cct", "power_w", "ip_rating", "shape", "environment",
    "consumption_unit", "sales_unit", "sales_package_quantity", "minimum_order_quantity", "package_label",
)

# Search aliases that make the browser forgiving without changing stored producer data.
_SEARCH_REPLACEMENTS = (
    ("½", ".5"), ("¼", ".25"), ("¾", ".75"),
    ("ø", "o"), ("æ", "ae"), ("å", "a"),
)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/+\-][a-z0-9]+)*", re.I)


def normalize_search_text(value) -> str:
    """Fold Danish characters, punctuation and fractions into a stable search form."""
    text=str(value or "").strip().casefold()
    for src,dst in _SEARCH_REPLACEMENTS:
        text=text.replace(src,dst)
    # Danish fallback spellings: both "dåse", "dase" and "daase" should meet.
    text=text.replace("aa","a")
    text=unicodedata.normalize("NFKD",text)
    text="".join(ch for ch in text if not unicodedata.combining(ch))
    text=text.replace(",",".")
    return " ".join(_TOKEN_RE.findall(text))


def search_terms(query) -> list[str]:
    return [x for x in normalize_search_text(query).split() if x]


def build_article_search_index(records: Iterable[dict], *, include_cables: bool = True) -> list[dict]:
    """Return enriched article rows with facets and precomputed search metadata."""
    indexed: list[dict] = []
    for raw in records or ():
        if not include_cables and str(raw.get("kind", "") or "") == "cable":
            continue
        article = dict(raw, **core.article_filter_facets(raw))
        specs = article.get("technical_specs", {}) if isinstance(article.get("technical_specs"), dict) else {}
        spec_text = " ".join(f"{k} {v}" for k, v in specs.items())
        raw_blob=" ".join(str(article.get(key, "") or "") for key in ARTICLE_SEARCH_FIELDS)+" "+spec_text
        article["_search_blob"] = raw_blob.casefold()
        article["_search_blob_folded"] = normalize_search_text(raw_blob)
        article["_search_article_no"] = normalize_search_text(article.get("article_no",""))
        article["_search_description"] = normalize_search_text(article.get("description",""))
        article["_search_identity"] = normalize_search_text(" ".join(str(article.get(k,"") or "") for k in ("ean","el_no")))
        article["_search_facets"] = normalize_search_text(" ".join(str(article.get(k,"") or "") for k in (
            "manufacturer","product_family","product_variant","category_normalized","product_type","function","module_size","color"
        )))
        indexed.append(article)
    return indexed


def article_search_score(article: dict, query: str, *, favorite=False, recent_rank=None, project=False) -> float | None:
    """Rank a catalogue row for a free-text query.

    Returns ``None`` when every term is not present. Exact identifiers and article
    number prefixes intentionally dominate descriptive matches. Usage signals only
    break ties / improve likely choices; they never make a non-match visible.
    """
    terms=search_terms(query)
    blob=str(article.get("_search_blob_folded",article.get("_search_blob","")) or "")
    if terms and not all(term in blob for term in terms):
        return None
    score=0.0
    normalized=normalize_search_text(query)
    ano=str(article.get("_search_article_no","") or "")
    desc=str(article.get("_search_description","") or "")
    identity=str(article.get("_search_identity","") or "")
    facets=str(article.get("_search_facets","") or "")
    if normalized:
        if normalized==ano: score+=10000
        elif ano.startswith(normalized): score+=4500
        elif normalized in ano: score+=2500
        if normalized and normalized in identity: score+=4000
        if normalized and desc.startswith(normalized): score+=1200
        elif normalized and normalized in desc: score+=700
        if normalized and normalized in facets: score+=350
        for term in terms:
            if term==ano: score+=1800
            elif ano.startswith(term): score+=700
            if term in desc: score+=180
            if term in facets: score+=90
    if favorite: score+=120
    if project: score+=80
    if recent_rank is not None:
        try: score+=max(0,60-int(recent_rank)*5)
        except (TypeError,ValueError): pass
    return score


def facet_value_counts(records: Iterable[dict], key: str) -> dict[str,int]:
    counts={}
    for article in records or ():
        value=str(article.get(key,"") or "").strip()
        if value:counts[value]=counts.get(value,0)+1
    return counts
