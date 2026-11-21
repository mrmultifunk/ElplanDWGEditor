from __future__ import annotations

import html as _html
import re
import time
import random
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable

from elplan_shared.storage_utils import atomic_write_json, read_json
from elplan_catalog import article_normalization
from elplan_catalog import article_intelligence


CATALOG_ROOT = "https://www1.lk.dk/katalog/nmkatalog.ph7"
CATALOG_CONTENT = "https://www1.lk.dk/katalog/nkatalog.ph7"
CURRENT_PRODUCT_ROOT = "https://www.lk.dk/produkter"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ElplanDWGEditor LK-Catalog-Sync/0.59.22"


class CatalogSyncError(RuntimeError):
    pass


class CatalogHttpError(CatalogSyncError):
    """HTTP error with enough metadata for polite retry/backoff handling."""
    def __init__(self, message: str, *, status: int = 0, retry_after: float | None = None, url: str = "") -> None:
        super().__init__(message)
        self.status = int(status or 0)
        self.retry_after = retry_after
        self.url = str(url or "")


class CatalogAccessLimitedError(CatalogSyncError):
    """Raised when LK keeps rate-limiting/denying requests after backoff."""
    pass


class _LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._capture: list[str] = []
        self._h1_depth = 0
        self.h1_parts: list[str] = []
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self._title_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        # LK's legacy catalogue has changed markup several times. Product/category
        # navigation has appeared in href, src, onclick, onmousedown and custom
        # data attributes. Keep every attribute value as a discovery candidate;
        # the strict regexes below decide whether it is useful.
        attr_map = dict(attrs)
        for _key, raw_value in attrs:
            val = str(raw_value or "").strip()
            if val:
                self.links.append(val)
        if tag.lower() == "h1":
            self._h1_depth += 1
        if tag.lower() == "title":
            self._title_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "h1" and self._h1_depth:
            self._h1_depth -= 1
        if tag.lower() == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if not text:
            return
        self.text_parts.append(text)
        if self._h1_depth:
            self.h1_parts.append(text)
        if self._title_depth:
            self.title_parts.append(text)


@dataclass
class SyncStats:
    category_pages: int = 0
    product_refs: int = 0
    product_pages: int = 0
    parsed_products: int = 0
    skipped_products: int = 0
    cached_products: int = 0
    database_reused_products: int = 0
    retried_products: int = 0
    network_products: int = 0
    index_cache_hit: bool = False
    workers: int = 0
    rate_limit_events: int = 0
    backoff_wait_seconds: float = 0.0
    checkpoint_resumed: bool = False
    checkpoint_reused_products: int = 0
    request_delay_min: float = 0.0
    request_delay_max: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class CatalogSnapshot:
    articles: list[dict]
    stats: SyncStats


_CACHE_VERSION = 3

def _empty_sync_cache() -> dict:
    return {"version": _CACHE_VERSION, "index": {}, "products": {}, "checkpoint": {}}

def _load_sync_cache(path: str | Path | None) -> dict:
    if not path:
        return _empty_sync_cache()
    p = Path(path)
    if not p.is_file():
        return _empty_sync_cache()
    raw = read_json(p, {})
    if not isinstance(raw, dict):
        return _empty_sync_cache()
    # 0.59.20 can reuse the v2 index/product cache from 0.59.18/19.  Only the
    # new checkpoint metadata is absent, so migrating it is safe and avoids a
    # needless full recrawl immediately after upgrading.
    version = int(raw.get("version", 0) or 0)
    if version not in (2, _CACHE_VERSION):
        return _empty_sync_cache()
    index = raw.get("index", {}) if isinstance(raw.get("index", {}), dict) else {}
    products = raw.get("products", {}) if isinstance(raw.get("products", {}), dict) else {}
    checkpoint = raw.get("checkpoint", {}) if isinstance(raw.get("checkpoint", {}), dict) else {}
    return {"version": _CACHE_VERSION, "index": index, "products": products, "checkpoint": checkpoint}

def _save_sync_cache(path: str | Path | None, cache: dict) -> None:
    if not path:
        return
    atomic_write_json(Path(path), cache)

def _fresh_epoch(value, max_age_hours: float, now: float | None = None) -> bool:
    try:
        stamp = float(value)
    except (TypeError, ValueError):
        return False
    now = time.time() if now is None else float(now)
    return 0 <= now - stamp <= max(0.0, float(max_age_hours)) * 3600.0

def _source_checked_fresh(value: str, max_age_hours: float) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        checked = date.fromisoformat(text[:10])
    except ValueError:
        return False
    age_days = (date.today() - checked).days
    return 0 <= age_days <= max(0, int(float(max_age_hours) / 24.0))

def _existing_ref_map(records: Iterable[dict], max_age_hours: float) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for raw in records or []:
        if not isinstance(raw, dict) or not _source_checked_fresh(raw.get("source_checked", ""), max_age_hours):
            continue
        maker = str(raw.get("manufacturer", "") or "").casefold()
        source = str(raw.get("source", "") or "").casefold()
        if "lauritz" not in maker and "schneider" not in maker and "lk.dk" not in source:
            continue
        for key in (raw.get("article_no", ""), raw.get("ean", "")):
            ref = str(key or "").strip()
            if ref:
                out[ref] = dict(raw)
    return out

def _cache_product_entry(cache: dict, ref: str, article: dict | None, extras: Iterable[str]) -> None:
    products = cache.setdefault("products", {})
    products[str(ref)] = {
        "fetched_at": time.time(),
        "article": dict(article) if isinstance(article, dict) else None,
        "extras": sorted({str(x).strip() for x in extras if str(x).strip()}),
    }

def _fetch_product_once(ref: str, timeout: float) -> tuple[str, str, dict | None, set[str]]:
    url = product_detail_url(ref)
    page = fetch_text(url, timeout=timeout, retries=0)
    extras = extract_product_refs(page)
    article = parse_product_page(page, source_url=url, fallback_article_no=ref)
    return ref, url, article, extras


def _decode_bytes(payload: bytes, content_type: str = "") -> str:
    match = re.search(r"charset\s*=\s*([\w.-]+)", content_type or "", re.I)
    candidates = [match.group(1)] if match else []
    candidates += ["utf-8", "windows-1252", "iso-8859-1"]
    for enc in candidates:
        try:
            return payload.decode(enc)
        except (LookupError, UnicodeDecodeError):
            pass
    return payload.decode("utf-8", errors="replace")


def _retry_after_seconds(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    # RFC 7231 also permits Retry-After as an HTTP date.
    try:
        when = parsedate_to_datetime(text)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def fetch_text(url: str, *, timeout: float = 12.0, retries: int = 1) -> str:
    """Fetch one LK page.

    ``collect_catalog`` owns the site-wide pacing/backoff policy.  This helper
    still supports a small retry count for callers outside that pipeline, but
    preserves HTTP status codes so 403/429/5xx can be handled responsibly.
    """
    last: Exception | None = None
    for attempt in range(max(1, retries + 1)):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "da-DK,da;q=0.9,en;q=0.6",
                    # Do not explicitly bypass intermediary/browser caches.
                    # Conditional/proxy caching is friendlier to LK than the old
                    # ``Cache-Control: no-cache`` header.
                    "Connection": "keep-alive",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
                return _decode_bytes(data, str(response.headers.get("Content-Type", "") or ""))
        except urllib.error.HTTPError as exc:
            last = exc
            retry_after = _retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
            wrapped = CatalogHttpError(
                f"LK.dk svarede HTTP {exc.code} for {url}",
                status=int(exc.code or 0), retry_after=retry_after, url=url,
            )
            if attempt < retries and int(exc.code or 0) not in (403, 429) and not 500 <= int(exc.code or 0) <= 599:
                time.sleep(0.35 * (attempt + 1))
                continue
            raise wrapped from exc
        except Exception as exc:  # network errors are reported with the URL later
            last = exc
            if attempt < retries:
                time.sleep(0.35 * (attempt + 1))
    raise CatalogSyncError(f"Kunne ikke hente {url}: {last}")


def _clean_text(value: str) -> str:
    value = _html.unescape(str(value or ""))
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^(?:Image\s*)+", "", value, flags=re.I).strip()
    return value


def _all_candidate_strings(page_html: str) -> list[str]:
    parser = _LinkTextParser()
    try:
        parser.feed(page_html)
    except Exception:
        pass
    # Include raw HTML too because a number of catalogue links are embedded in JavaScript.
    return parser.links + [page_html]


def extract_category_ids(page_html: str) -> set[int]:
    out: set[int] = set()
    for blob in _all_candidate_strings(page_html):
        decoded = urllib.parse.unquote(_html.unescape(blob))
        for match in re.finditer(r"(?:[?&]|\b)iid\s*=\s*(\d{1,5})", decoded, re.I):
            try:
                out.add(int(match.group(1)))
            except ValueError:
                pass
    return out


def extract_product_refs(page_html: str) -> set[str]:
    """Return product EAN/reference ids used by LK's old catalogue URLs."""
    refs: set[str] = set()
    for blob in _all_candidate_strings(page_html):
        decoded = urllib.parse.unquote(_html.unescape(blob)).replace("\\/", "/")
        for pattern in (
            r"(?:[?&]|\b)vnr\s*=\s*([0-9A-Za-z._/-]{3,32})",
            r"urlref\s*=\s*[/]?produkt[/=]([0-9A-Za-z_-]{5,32})",
            r"[/]produkt[/]([0-9A-Za-z_-]{5,32})",
            r"produkt%2[fF]([0-9A-Za-z_-]{5,32})",
            # Current legacy category pages often expose the LK varenummer only
            # through the product image URL, e.g. /foto/jpg/588D6693.jpg.
            r"(?:/|\b)foto/(?:jpg|png|webp)/([0-9A-Za-z_-]{5,32})\.(?:jpe?g|png|webp)",
            # A few templates build image paths without the /foto prefix.
            r"(?:^|[/\\])([0-9A-Za-z_-]{5,32})\.(?:jpe?g|png|webp)(?:[?#]|$)",
            # EANs also occur as JavaScript arguments in some catalogue cards.
            r"(?:showProduct|showContent|product|produkt)[^0-9]{0,40}([0-9]{13})",
        ):
            for match in re.finditer(pattern, decoded, re.I):
                ref = match.group(1).strip().strip("'\"&?#/;)")
                if not ref:
                    continue
                # Reject generic artwork names such as Fuga.jpg / info.png. LK
                # article numbers contain at least one digit; EAN references are
                # numeric and normally 13 digits.
                if not any(ch.isdigit() for ch in ref):
                    continue
                if not article_normalization.is_valid_discovery_ref(ref):
                    continue
                refs.add(ref)
    return refs


def product_detail_url(reference: str) -> str:
    ref=str(reference or "").strip()
    # Category pages commonly link directly by LK varenummer (vnr).  Variant
    # links on product pages can instead use a 13 digit EAN/urlref.
    if not (ref.isdigit() and len(ref) == 13):
        return f"{CATALOG_ROOT}?{urllib.parse.urlencode({'vnr': ref})}"
    query = urllib.parse.urlencode({"aktion": "content", "urlref": f"/produkt/{ref}"})
    return f"{CATALOG_CONTENT}?{query}"


def category_url(iid: int) -> str:
    return f"{CATALOG_ROOT}?iid={int(iid)}"


def _field_from_text(text: str, labels: Iterable[str]) -> str:
    for label in labels:
        # Stop at the next well-known field label or line-ish separator.
        pattern = rf"{re.escape(label)}\s*:?\s*(.{{1,120}}?)\s*(?=(?:LK\s*nummer|Varenummer|Vare\s*nr\.?|EL\s*nummer|EAN\s*(?:nummer|nr\.?|:)|Varegruppe|Katalog|Pakkestørrelse|Farve|$))"
        m = re.search(pattern, text, re.I)
        if m:
            return _clean_text(m.group(1))
    return ""


def _simple_field(text: str, label_pattern: str, value_pattern: str = r"([^\s|]{2,80})") -> str:
    m = re.search(rf"{label_pattern}\s*:?\s*{value_pattern}", text, re.I)
    return _clean_text(m.group(1)) if m else ""


def _series_from_text(text: str, title: str) -> str:
    hay = f"{title} {text}".casefold()
    for needle, label in (
        ("lk® one", "LK One"), ("lk one", "LK One"),
        ("lk fuga", "LK FUGA"), ("fuga®", "LK FUGA"),
        ("lk opus® 66", "LK OPUS 66"), ("opus® 66", "LK OPUS 66"),
        ("lk opus® 73", "LK OPUS 73"), ("opus® 73", "LK OPUS 73"),
        ("lk opus® 74", "LK OPUS 74"), ("opus® 74", "LK OPUS 74"),
        ("clic'line", "CLIC'LINE"),
        ("ihc control", "IHC Control"), ("ihc wireless", "IHC Wireless"),
        ("lexcom home", "Lexcom Home"), ("actassi", "Actassi"),
        ("wiser", "Wiser"), ("knx", "KNX"),
    ):
        if needle in hay:
            return label
    return "LK"


def _category_from_series(series: str, title: str, text: str) -> str:
    hay = str(title or "").casefold()
    base = series or "LK"
    def has(*words):
        return any(w in hay for w in words)
    if has("dåse", "daase"):
        label="Dåser"
    elif has("teknisk", "montageramme") and has("ramme", "montageramme"):
        label="Tekniske rammer"
    elif has("ramme"):
        label="Rammer"
    elif has("tangent", "afdæk", "afdaek", "dækplade", "daekplade"):
        label="Tangenter og afdækninger"
    elif has("lampeudtag", "lampestik"):
        label="Lampeudtag"
    elif has("stikkontakt", "stikprop", "udtag"):
        label="Stikkontakter og udtag"
    elif has("lysdæmper", "lysdaemper", "afbryder", "trykkontakt", "trykknap"):
        label="Afbrydere og betjening"
    elif has("pir", "bevæg", "bevaeg", "sensor"):
        label="Sensorer og PIR"
    elif has("rj45", "keystone", "actassi", "datanet", "dataudtag"):
        label="Data og netværk"
    elif has("tavle"):
        label="Tavler"
    elif has("relæ", "rele"):
        label="Relæer"
    else:
        return base
    return f"{base} · {label}"


def _token_field(tokens: list[str], labels: Iterable[str]) -> str:
    """Extract a value from adjacent HTML text nodes before flat-text fallback.

    Some legacy LK templates place all identity fields in one text node, e.g.
    ``LK nummer: ... EL nummer: ... EAN: ...``.  In that case the value is
    clipped at the next known label instead of consuming the whole node.
    """
    labels=tuple(str(x) for x in labels)
    stop_pattern=r"(?=\s*(?:LK\s*nummer|Varenummer|Vare\s*nr\.?|EL\s*nummer|EAN\s*(?:nummer|nr\.?)?|Varegruppe|Katalog|Pakkestørrelse|Farve|Produktbeskrivelse)\s*:?)"
    cleaned=[_clean_text(x) for x in tokens if _clean_text(x)]
    for i,token in enumerate(cleaned):
        low=token.casefold().rstrip(":")
        for label in labels:
            label_cf=label.casefold().rstrip(":")
            if low == label_cf:
                for nxt in cleaned[i+1:i+4]:
                    if re.match(r"^(?:LK\s*nummer|Varenummer|Vare\s*nr\.?|EL\s*nummer|EAN|Varegruppe|Katalog|Pakkestørrelse|Farve|Produktbeskrivelse)\b",nxt,re.I):
                        break
                    if nxt:
                        return nxt
            m=re.search(rf"(?:^|\b){re.escape(label)}\s*:?\s*(.+?){stop_pattern}",token,re.I)
            if m and _clean_text(m.group(1)):
                return _clean_text(m.group(1))
            # Last field in a combined node has no following stop label.
            m=re.search(rf"(?:^|\b){re.escape(label)}\s*:?\s*(.+)$",token,re.I)
            if m and _clean_text(m.group(1)):
                value=_clean_text(m.group(1))
                # If another known label is still present, clip it manually.
                value=re.split(r"\s+(?=(?:LK\s*nummer|Varenummer|Vare\s*nr\.?|EL\s*nummer|EAN\s*(?:nummer|nr\.?)?|Varegruppe|Katalog|Pakkestørrelse|Farve|Produktbeskrivelse)\s*:?)",value,maxsplit=1,flags=re.I)[0]
                if value:return _clean_text(value)
    return ""

def parse_product_page(page_html: str, *, source_url: str = "", fallback_article_no: str = "") -> dict | None:
    parser = _LinkTextParser()
    try:
        parser.feed(page_html)
    except Exception:
        pass
    text = _clean_text("\n".join(parser.text_parts))
    title = _clean_text(" ".join(parser.h1_parts)) or _clean_text(" ".join(parser.title_parts))
    title = re.sub(r"\bLK katalog\b", "", title, flags=re.I).strip(" -|")

    # Prefer adjacent HTML text nodes. Flat page text is only a fallback because
    # variant pages can otherwise let Farve/LK-/EAN fields bleed into each other.
    tokens=list(parser.text_parts)
    parsed_article_no = _token_field(tokens, ("LK nummer", "Varenummer", "Vare nr.")) or _simple_field(text, r"(?:LK\s*nummer|Varenummer|Vare\s*nr\.?)", r"([0-9A-Za-z][0-9A-Za-z._/-]{2,31})")
    el_no = _token_field(tokens, ("EL nummer",)) or _simple_field(text, r"EL\s*nummer", r"([0-9][0-9 .-]{4,24})")
    ean = _token_field(tokens, ("EAN nummer", "EAN nr.", "EAN")) or _simple_field(text, r"EAN\s*(?:nummer|nr\.?|:)?", r"([0-9][0-9 .-]{7,24})")
    color = _token_field(tokens, ("Farve",)) or _field_from_text(text, ("Farve",))
    fallback_clean=article_normalization.normalize_article_no(fallback_article_no)
    article_no = fallback_clean or parsed_article_no
    package_match=re.search(r"Pakkestørrelse\s*:?\s*([0-9]+(?:[.,][0-9]+)?\s*(?:stk\.?|m\b|meter\b|sæt\b|pakke\w*))",text,re.I)
    package=_clean_text(package_match.group(1)) if package_match else ""

    article_no = article_normalization.normalize_article_no(article_no)
    el_no = re.sub(r"\D+", "", el_no)
    ean = re.sub(r"\D+", "", ean)
    if not article_no:
        return None
    if title.casefold().startswith("image "):
        title = title[6:].strip()
    if not title:
        title = article_no

    series = _series_from_text(text, title)
    category = _category_from_series(series, title, text)
    status = ""
    low = text.casefold()
    if "udgået" in low or "udgaaet" in low:
        status = "Udgået"
        if "lager haves" in low:
            status = "Udgået – sælges så længe lager haves"
    else:
        status = "Aktiv/ukendt"

    record = {
        "article_no": article_no,
        "description": title,
        "manufacturer": "Schneider Electric / Lauritz Knudsen",
        "unit": "stk",
        "category": category,
        "series": series,
        "status": status,
        "kind": "component",
        "source": source_url or product_detail_url(ean or article_no),
        "source_checked": date.today().isoformat(),
        "product_page": f"{CURRENT_PRODUCT_ROOT}?iid={urllib.parse.quote(article_no)}",
        "image_url": f"https://www1.lk.dk/katalog/foto/jpg/{urllib.parse.quote(article_no)}.jpg",
        "image_source": "LK / Schneider Electric",
    }
    if el_no:
        record["el_no"] = el_no
    if ean:
        record["ean"] = ean
    if color and len(color) <= 80:
        record["color"] = color
        record["color_raw"] = color
    if package:
        record["note"] = f"Pakkestørrelse: {package}"

    # Build semantic identity from the product heading, while the richer page
    # application text is used only to derive compatibility. The full page text
    # is not persisted in the article database.
    semantic_input = dict(record)
    semantic_input["semantic_source_text"] = text
    semantic = article_intelligence.derive_product_semantics(semantic_input)
    for field_name in ("semantic_model_version", "product_family", "product_variant"):
        value = semantic.get(field_name)
        if value:
            record[field_name] = value
    if semantic.get("compatibility"):
        record["compatibility"] = semantic["compatibility"]
    if semantic.get("semantic_evidence"):
        record["semantic_evidence"] = semantic["semantic_evidence"]

    record, _info = article_normalization.normalize_lk_article(record, parsed_now=True)
    return record


def merge_lk_articles(existing: Iterable[dict], incoming: Iterable[dict]) -> tuple[list[dict], dict]:
    """Merge LK catalogue rows while preserving local-only user metadata.

    Official catalogue fields are refreshed. Manual supplier links, notes (unless
    they only contain the old package-size note), and unrelated/custom records
    survive. Prices are stored separately by the application and are untouched.
    """
    cleaned_existing, cleanup_stats = article_normalization.normalize_lk_catalog(existing, parsed_now=False)
    cleaned_incoming, incoming_stats = article_normalization.normalize_lk_catalog(incoming, parsed_now=True)
    current = {str(r.get("article_no", "") or "").strip().casefold(): dict(r) for r in cleaned_existing if isinstance(r, dict) and str(r.get("article_no", "") or "").strip()}
    added = updated = unchanged = 0
    official_fields = {
        "description", "manufacturer", "unit", "category", "series", "el_no", "ean",
        "status", "kind", "source", "source_checked", "product_type", "design_family", "design_family_raw",
        "module_size", "module_size_raw", "color", "color_raw", "mounting_type", "product_page", "image_url", "image_source",
        "semantic_model_version", "product_family", "product_variant", "compatibility", "semantic_evidence",
    }
    for raw in cleaned_incoming:
        if not isinstance(raw, dict):
            continue
        no = str(raw.get("article_no", "") or "").strip()
        if not no:
            continue
        key = no.casefold()
        old = current.get(key)
        if old is None:
            current[key] = dict(raw)
            added += 1
            continue
        merged = dict(old)
        before = dict(merged)
        for field_name in official_fields:
            value = raw.get(field_name)
            if value not in (None, ""):
                merged[field_name] = value
        # A raw producer field with no accepted normalised value is an explicit
        # clear, not "missing data". Otherwise a formerly polluted/obsolete
        # colour or module could survive forever through the merge.
        if raw.get("color_raw") not in (None, "") and raw.get("color") in (None, ""):
            merged.pop("color", None)
        if raw.get("module_size_raw") not in (None, "") and raw.get("module_size") in (None, ""):
            merged.pop("module_size", None)
        # Package size is useful, but do not destroy a user's own note.
        old_note = str(old.get("note", "") or "").strip()
        new_note = str(raw.get("note", "") or "").strip()
        if new_note and (not old_note or old_note.startswith("Pakkestørrelse:")):
            merged["note"] = new_note
        current[key] = merged
        if merged == before:
            unchanged += 1
        else:
            updated += 1
    return list(current.values()), {
        "added": added, "updated": updated, "unchanged": unchanged,
        "cleanup_removed": int(cleanup_stats.get("rejected", 0)),
        "cleanup_changed": int(cleanup_stats.get("changed_articles", 0)),
        "incoming_rejected": int(incoming_stats.get("rejected", 0)),
        "incoming_changed": int(incoming_stats.get("changed_articles", 0)),
    }


def _article_richness(row: dict) -> int:
    """Score a parsed row so duplicate EAN/vnr discoveries keep richer data."""
    if not isinstance(row, dict):
        return 0
    score = 0
    for name, weight in (("ean", 4), ("el_no", 4), ("color", 2), ("note", 1), ("series", 1), ("category", 1)):
        if str(row.get(name, "") or "").strip():
            score += weight
    title = str(row.get("description", "") or "").strip()
    if title and title.casefold() not in {"lk katalog", "produkt", "produkter"}:
        score += 3
    return score


def _merge_discovered_row(old: dict | None, new: dict) -> dict:
    if not old:
        return dict(new)
    # Prefer the richer row as base, then fill any missing official fields from
    # the other discovery path. This is important because a product can be found
    # both as LK varenummer (image filename) and as EAN (urlref).
    rich, other = (new, old) if _article_richness(new) >= _article_richness(old) else (old, new)
    out = dict(rich)
    for key, value in other.items():
        if out.get(key) in (None, "") and value not in (None, ""):
            out[key] = value
    return out


def collect_catalog(
    *,
    progress: Callable[[str, int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    timeout: float = 12.0,
    product_timeout: float = 8.0,
    max_categories: int = 2500,
    max_products: int = 10000,
    workers: int = 1,
    retry_count: int = 1,
    cache_path: str | Path | None = None,
    cache_max_age_hours: float = 24.0 * 14.0,
    index_cache_hours: float = 24.0,
    force_refresh: bool = False,
    existing_articles: Iterable[dict] = (),
    request_delay_min: float = 0.8,
    request_delay_max: float = 1.5,
    backoff_seconds: tuple[float, ...] = (5.0, 15.0, 45.0, 120.0),
    checkpoint_max_age_hours: float = 24.0 * 7.0,
) -> CatalogSnapshot:
    """Crawl LK's catalogue using a deliberately polite single-request pipeline.

    0.59.20 intentionally serialises *all* LK traffic, including fallback index
    discovery.  A random delay is inserted between network requests.  Fresh
    product/database cache entries are reused for normal synchronisation, and a
    persisted checkpoint lets an interrupted *full* refresh continue without
    downloading already completed pages again.  Even a full product refresh may
    reuse a fresh catalogue index, because re-crawling the category tree adds
    traffic without improving product freshness.

    HTTP 403/429 and 5xx responses trigger escalating backoff.  If LK still
    refuses traffic after the backoff sequence, the crawl stops immediately and
    leaves both cache and checkpoint intact for a later resume; it never hammers
    through the remaining catalogue after a block is detected.
    """
    stats = SyncStats()
    # Kept as an API parameter for backward compatibility; LK traffic is always
    # serial from 0.59.20 onward.
    workers = 1
    retry_count = max(0, min(3, int(retry_count or 0)))
    stats.workers = 1
    delay_min = max(0.0, float(request_delay_min or 0.0))
    delay_max = max(delay_min, float(request_delay_max or delay_min))
    stats.request_delay_min = delay_min
    stats.request_delay_max = delay_max
    backoffs = tuple(max(0.0, float(x)) for x in (backoff_seconds or ()))

    cache = _load_sync_cache(cache_path)
    cache_dirty = False
    last_cache_save = time.monotonic()
    last_request_started: float | None = None

    def cancelled() -> bool:
        return bool(cancel and cancel())

    def save_cache_if_needed(force: bool = False) -> None:
        nonlocal cache_dirty, last_cache_save
        if not cache_path or not cache_dirty:
            return
        if force or time.monotonic() - last_cache_save >= 8.0:
            _save_sync_cache(cache_path, cache)
            cache_dirty = False
            last_cache_save = time.monotonic()

    def wait_interruptible(seconds: float, label: str = "") -> None:
        remaining = max(0.0, float(seconds or 0.0))
        end = time.monotonic() + remaining
        last_shown: int | None = None
        while remaining > 0:
            if cancelled():
                save_cache_if_needed(True)
                raise CatalogSyncError("Synkronisering annulleret.")
            shown = max(1, int(remaining + 0.999))
            if progress and label and shown != last_shown:
                progress(f"{label} · nyt forsøg om {shown} s", 0, 1)
                last_shown = shown
            time.sleep(min(0.25, remaining))
            remaining = max(0.0, end - time.monotonic())

    def pace_request() -> None:
        nonlocal last_request_started
        if last_request_started is not None and delay_max > 0:
            target_gap = random.uniform(delay_min, delay_max)
            elapsed = time.monotonic() - last_request_started
            if elapsed < target_gap:
                wait_interruptible(target_gap - elapsed)
        last_request_started = time.monotonic()

    def polite_fetch(url: str, *, page_timeout: float, context: str) -> str:
        """One-at-a-time request with site-wide pacing and rate-limit backoff."""
        nonlocal cache_dirty
        rate_attempt = 0
        while True:
            if cancelled():
                save_cache_if_needed(True)
                raise CatalogSyncError("Synkronisering annulleret.")
            pace_request()
            try:
                return fetch_text(url, timeout=page_timeout, retries=0)
            except CatalogHttpError as exc:
                status = int(getattr(exc, "status", 0) or 0)
                limited = status in (403, 429) or 500 <= status <= 599
                if not limited:
                    raise
                stats.rate_limit_events += 1
                if rate_attempt >= len(backoffs):
                    save_cache_if_needed(True)
                    raise CatalogAccessLimitedError(
                        f"LK.dk begrænser fortsat forespørgsler (HTTP {status}). "
                        "Synkroniseringen er stoppet for at undgå yderligere blokering. "
                        "Fremskridtet er gemt og kan fortsættes senere."
                    ) from exc
                wait_for = backoffs[rate_attempt]
                retry_after = getattr(exc, "retry_after", None)
                if retry_after is not None:
                    wait_for = max(wait_for, min(300.0, float(retry_after)))
                stats.backoff_wait_seconds += wait_for
                rate_attempt += 1
                label = f"LK.dk begrænser forespørgsler (HTTP {status})"
                if progress:
                    progress(f"{label} · synkronisering sat på pause", 0, 1)
                wait_interruptible(wait_for, label)
            except CatalogAccessLimitedError:
                raise

    # --- Discover current catalogue references -------------------------------
    product_refs: set[str] = set()
    cached_index = cache.get("index", {}) if isinstance(cache.get("index", {}), dict) else {}
    if (
        _fresh_epoch(cached_index.get("fetched_at"), index_cache_hours)
        and isinstance(cached_index.get("refs"), list)
        and cached_index.get("refs")
    ):
        product_refs.update(str(x).strip() for x in cached_index["refs"] if str(x).strip())
        stats.index_cache_hit = True
        if progress:
            progress(f"Bruger cached LK-katalogindeks · {len(product_refs):,} produktreferencer".replace(",", "."), 1, 1)
    else:
        category_queue: deque[int | None] = deque([None])
        category_seen: set[int | None] = set()
        while category_queue:
            if cancelled():
                save_cache_if_needed(True)
                raise CatalogSyncError("Synkronisering annulleret.")
            iid = category_queue.popleft()
            if iid in category_seen:
                continue
            if len(category_seen) >= max_categories:
                raise CatalogSyncError(f"Kataloget overskred sikkerhedsgrænsen på {max_categories} kategorisider.")
            category_seen.add(iid)
            url = CATALOG_ROOT if iid is None else category_url(iid)
            if progress:
                progress("Finder produktkategorier…", len(category_seen), max(1, len(category_seen) + len(category_queue)))
            try:
                page = polite_fetch(url, page_timeout=timeout, context="katalogindeks")
            except CatalogAccessLimitedError:
                save_cache_if_needed(True)
                raise
            except Exception as exc:
                stats.errors.append(str(exc))
                continue
            stats.category_pages += 1
            for child in sorted(extract_category_ids(page)):
                if child not in category_seen:
                    category_queue.append(child)
            product_refs.update(extract_product_refs(page))

        # If even the catalogue front page could not be retrieved, do not turn
        # a connectivity/DNS failure into hundreds of fallback requests.
        if stats.category_pages == 0:
            detail = stats.errors[-1] if stats.errors else "ukendt netværksfejl"
            raise CatalogSyncError(
                "LK-katalogets startside kunne ikke hentes. Synkroniseringen stoppes uden fallback-probing. "
                f"Detalje: {detail}"
            )

        # Fallback probe remains intentionally sequential.  It is only used if
        # recursive discovery found suspiciously little.
        if len(product_refs) < 100:
            probe_ids = [iid for iid in range(1, 451) if iid not in category_seen]
            for done_count, iid in enumerate(probe_ids, start=1):
                if cancelled():
                    save_cache_if_needed(True)
                    raise CatalogSyncError("Synkronisering annulleret.")
                if progress:
                    progress("Supplerer LK-katalogindeks…", done_count, max(1, len(probe_ids)))
                try:
                    page = polite_fetch(category_url(iid), page_timeout=timeout, context="katalogindeks")
                except CatalogAccessLimitedError:
                    save_cache_if_needed(True)
                    raise
                except Exception:
                    continue
                stats.category_pages += 1
                product_refs.update(extract_product_refs(page))

        if not product_refs:
            raise CatalogSyncError(
                "LK-kataloget kunne hentes, men ingen produktreferencer blev fundet. "
                "Katalogets webstruktur kan være ændret."
            )
        cache["index"] = {"fetched_at": time.time(), "refs": sorted(product_refs)}
        cache_dirty = True
        save_cache_if_needed(True)

    if len(product_refs) > max_products:
        raise CatalogSyncError(f"Kataloget indeholder over sikkerhedsgrænsen på {max_products} produkter.")
    stats.product_refs = len(product_refs)

    # --- Resume/checkpoint -----------------------------------------------------
    initial_refs = sorted(product_refs)
    checkpoint = cache.get("checkpoint", {}) if isinstance(cache.get("checkpoint", {}), dict) else {}
    checkpoint_stamp = checkpoint.get("updated_at", checkpoint.get("started_at"))
    checkpoint_matches = bool(
        checkpoint.get("active")
        and _fresh_epoch(checkpoint_stamp, checkpoint_max_age_hours)
        and bool(checkpoint.get("force_refresh")) == bool(force_refresh)
        and checkpoint.get("catalog_refs") == initial_refs
    )
    if checkpoint_matches:
        resume_completed = {
            str(x).strip() for x in checkpoint.get("completed_refs", [])
            if str(x).strip()
        }
        stats.checkpoint_resumed = bool(resume_completed)
    else:
        resume_completed: set[str] = set()
        checkpoint = {
            "active": True,
            "started_at": time.time(),
            "force_refresh": bool(force_refresh),
            "catalog_refs": initial_refs,
            "known_refs": initial_refs,
            "completed_refs": [],
        }
        cache["checkpoint"] = checkpoint
        cache_dirty = True
        save_cache_if_needed(True)

    checkpoint_completed: set[str] = set(resume_completed)
    checkpoint_known: set[str] = {
        str(x).strip() for x in checkpoint.get("known_refs", initial_refs) if str(x).strip()
    } | set(product_refs)

    def sync_checkpoint() -> None:
        nonlocal cache_dirty
        checkpoint["active"] = True
        checkpoint["force_refresh"] = bool(force_refresh)
        checkpoint["catalog_refs"] = initial_refs
        checkpoint["known_refs"] = sorted(checkpoint_known)
        checkpoint["completed_refs"] = sorted(checkpoint_completed)
        checkpoint["updated_at"] = time.time()
        cache["checkpoint"] = checkpoint
        cache_dirty = True

    # Existing recently synced LK rows are a zero-network seed for normal sync.
    existing_by_ref = {} if force_refresh else _existing_ref_map(existing_articles, cache_max_age_hours)
    products_cache = cache.setdefault("products", {})
    known_refs: set[str] = set(product_refs) | checkpoint_known
    pending: deque[str] = deque(sorted(known_refs))
    completed: set[str] = set()
    articles_by_no: dict[str, dict] = {}

    def add_article(article: dict | None) -> None:
        if not isinstance(article, dict) or not str(article.get("article_no", "") or "").strip():
            return
        article, _info = article_normalization.normalize_lk_article(article, parsed_now=bool(article.get("color_raw")))
        if not article:
            stats.skipped_products += 1
            return
        key = str(article["article_no"]).casefold()
        articles_by_no[key] = _merge_discovered_row(articles_by_no.get(key), article)
        stats.parsed_products = len(articles_by_no)

    def add_extras(extras: Iterable[str]) -> None:
        for extra in extras or ():
            ref = str(extra or "").strip()
            if not ref or ref in known_refs or not article_normalization.is_valid_discovery_ref(ref):
                continue
            if len(known_refs) >= max_products:
                continue
            known_refs.add(ref)
            checkpoint_known.add(ref)
            pending.append(ref)
            sync_checkpoint()

    def mark_completed(ref: str) -> None:
        completed.add(ref)
        checkpoint_completed.add(ref)
        sync_checkpoint()

    def progress_products() -> None:
        if not progress:
            return
        done_n = len(completed)
        total_n = max(1, len(known_refs))
        parts = [f"Henter LK-artikler… {done_n:,} / {total_n:,}".replace(",", "."), "1 forbindelse"]
        reused = stats.cached_products + stats.database_reused_products
        if reused:
            parts.append(f"{reused:,} fra cache".replace(",", "."))
        if stats.checkpoint_resumed:
            parts.append("fortsætter tidligere synkronisering")
        progress(" · ".join(parts), done_n, total_n)

    def try_reuse(ref: str) -> bool:
        nonlocal cache_dirty
        entry = products_cache.get(ref)
        # A matching checkpoint is explicitly allowed to reuse pages completed
        # during an interrupted full refresh, even though force_refresh normally
        # bypasses cache.  This is what makes full-refresh resume useful.
        checkpoint_ok = ref in resume_completed and isinstance(entry, dict)
        fresh_cache = (
            not force_refresh
            and isinstance(entry, dict)
            and _fresh_epoch(entry.get("fetched_at"), cache_max_age_hours)
        )
        if checkpoint_ok or fresh_cache:
            article = entry.get("article") if isinstance(entry, dict) else None
            extras = entry.get("extras", []) if isinstance(entry, dict) and isinstance(entry.get("extras", []), list) else []
            if isinstance(article, dict) and str(article.get("article_no", "") or "").strip():
                add_article(article)
            else:
                stats.skipped_products += 1
            add_extras(extras)
            stats.cached_products += 1
            if checkpoint_ok:
                stats.checkpoint_reused_products += 1
            mark_completed(ref)
            return True
        if not force_refresh:
            row = existing_by_ref.get(ref)
            if isinstance(row, dict):
                add_article(row)
                _cache_product_entry(cache, ref, row, ())
                cache_dirty = True
                stats.database_reused_products += 1
                mark_completed(ref)
                return True
        return False

    # --- Sequential detail-page pipeline --------------------------------------
    while pending:
        if cancelled():
            sync_checkpoint()
            save_cache_if_needed(True)
            raise CatalogSyncError("Synkronisering annulleret.")
        ref = pending.popleft()
        if ref in completed:
            continue
        if try_reuse(ref):
            progress_products()
            save_cache_if_needed()
            continue

        attempt = 0
        while True:
            try:
                url = product_detail_url(ref)
                page = polite_fetch(url, page_timeout=product_timeout, context="produktside")
                extras = extract_product_refs(page)
                article = parse_product_page(page, source_url=url, fallback_article_no=ref)
                stats.product_pages += 1
                stats.network_products += 1
                add_extras(extras)
                if article:
                    add_article(article)
                else:
                    stats.skipped_products += 1
                # Cache successful parses *and* known non-product refs.  A short
                # cache lifetime already protects against permanent stale data,
                # while avoiding repeated traffic to the same bad asset/ref.
                _cache_product_entry(cache, ref, article, extras)
                cache_dirty = True
                mark_completed(ref)
                break
            except CatalogAccessLimitedError:
                sync_checkpoint()
                save_cache_if_needed(True)
                raise
            except Exception as exc:
                if attempt < retry_count:
                    attempt += 1
                    stats.retried_products += 1
                    # Ordinary network/parser failures get one polite retry after
                    # the normal inter-request delay; no burst retry is allowed.
                    continue
                stats.errors.append(str(exc))
                stats.skipped_products += 1
                mark_completed(ref)
                break
        progress_products()
        save_cache_if_needed()

    if not articles_by_no:
        sync_checkpoint()
        save_cache_if_needed(True)
        raise CatalogSyncError("Ingen LK-artikler kunne fortolkes fra onlinekataloget.")
    if len(articles_by_no) < 100:
        sync_checkpoint()
        save_cache_if_needed(True)
        raise CatalogSyncError(
            f"Synkroniseringen fandt kun {len(articles_by_no)} artikler. "
            "Det er mistænkeligt lavt for LK's katalog, så databasen blev ikke ændret."
        )

    # Only a completely successful crawl clears the checkpoint.  The product
    # cache remains and is the basis for fast, low-traffic normal syncs.
    cache["checkpoint"] = {}
    cache_dirty = True
    save_cache_if_needed(True)
    return CatalogSnapshot(list(articles_by_no.values()), stats)

