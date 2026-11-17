from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Iterable, Mapping
from copy import deepcopy
from datetime import datetime

import core_logic as core
from elplan_core import settings as app_settings
from storage_utils import atomic_write_json, read_json

BOM_LIBRARY_VERSION = 5
_LIBRARY_VERSION = BOM_LIBRARY_VERSION
ARTICLE_CATALOG_VERSION = 3
PRICEBOOK_VERSION = 5
_ENV_DIR = "ELPLAN_USER_DATA_DIR"
CORE_DATA_MODE_LOCAL = "local"
CORE_DATA_MODE_SYNCED = "synced"
CORE_DATA_FILENAMES = ("articles.json", "article_prices.json", "bom_assemblies.json")

_ARTICLE_CATALOG_CACHE_SIGNATURE = None
_ARTICLE_CATALOG_CACHE_ROWS: list[dict] | None = None

_BUNDLED_PRICE_FIELDS = (
    "estimated_price", "effective_price", "unit_price", "estimated_price_min", "estimated_price_max",
    "estimated_price_source", "estimated_price_checked", "estimated_price_confidence", "estimated_price_method",
    "estimated_price_sources", "price_observations", "price_currency", "price_unit", "price_kind", "price_status",
    "price_source", "price_checked", "price_note", "sales_package_quantity", "sales_unit",
    "consumption_unit", "minimum_order_quantity", "package_label", "catalog_price_revision",
)

def _article_catalog_signature(path: Path):
    identity=str(path.expanduser().resolve(strict=False))
    try:
        st=path.stat()
        return (identity,int(st.st_mtime_ns),int(st.st_size))
    except OSError:
        return (identity,None,None)



def user_data_dir() -> Path:
    """Lokal Elplan-mappe til indstillinger, cache og logs."""
    override = str(os.environ.get(_ENV_DIR, "") or "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = str(os.environ.get("APPDATA", "") or os.environ.get("LOCALAPPDATA", "") or "").strip()
        if root:
            return Path(root) / "ElplanDWGEditor"
    root = str(os.environ.get("XDG_CONFIG_HOME", "") or "").strip()
    return (Path(root).expanduser() if root else Path.home() / ".config") / "ElplanDWGEditor"


def normalize_core_data_mode(value) -> str:
    text = str(value or "").strip().lower()
    return CORE_DATA_MODE_SYNCED if text in {"synced", "sync", "onedrive", "cloud"} else CORE_DATA_MODE_LOCAL


def configured_core_data(settings: Mapping | None = None) -> tuple[str, Path]:
    """Returnér placeringen af de globale artikeldata, aldrig et projektlager.

    Test-/administrationsoverstyringen ``ELPLAN_USER_DATA_DIR`` har fortsat
    højeste prioritet og isolerer alle autoritative data i den valgte mappe.
    """
    local = user_data_dir()
    if str(os.environ.get(_ENV_DIR, "") or "").strip():
        return CORE_DATA_MODE_LOCAL, local
    data = settings if isinstance(settings, Mapping) else app_settings.load_app_settings()
    mode = normalize_core_data_mode(data.get("core_data_storage_mode"))
    raw = str(data.get("core_data_root", "") or "").strip()
    if mode == CORE_DATA_MODE_SYNCED and raw:
        return mode, Path(raw).expanduser()
    return CORE_DATA_MODE_LOCAL, local


def core_data_dir(settings: Mapping | None = None) -> Path:
    """Global databaseplacering for artikler, priser og styklister."""
    return configured_core_data(settings)[1]


def bom_assemblies_path() -> Path:
    return core_data_dir() / "bom_assemblies.json"


def article_prices_path() -> Path:
    return core_data_dir() / "article_prices.json"


def article_catalog_path() -> Path:
    return core_data_dir() / "articles.json"


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def invalidate_core_data_caches() -> None:
    global _ARTICLE_CATALOG_CACHE_SIGNATURE, _ARTICLE_CATALOG_CACHE_ROWS
    _ARTICLE_CATALOG_CACHE_SIGNATURE = None
    _ARTICLE_CATALOG_CACHE_ROWS = None


def _refresh_bundled_catalog_prices(stored: Iterable[dict], bundled: Iterable[dict]) -> tuple[list[dict], bool]:
    """Opdatér kun reviderede katalogestimater; brugerens prisbog røres ikke.

    ``articles.json`` er normalt autoritativt, men det betød også, at en
    tidligere forkert pakkepris kunne overleve alle programopdateringer. En
    højere ``catalog_price_revision`` i det indbyggede katalog opdaterer derfor
    kun estimat-/pakningsfelterne for samme varenummer. Manuelle priser ligger
    fortsat separat i ``article_prices.json`` og kan ikke blive overskrevet her.
    """
    base={str(row.get("article_no","") or ""):dict(row) for row in bundled or []}
    rows=[]; changed=False
    for raw in stored or []:
        row=dict(raw); bundled_row=base.get(str(row.get("article_no","") or ""))
        try: current_revision=int(float(row.get("catalog_price_revision",0) or 0))
        except (TypeError,ValueError): current_revision=0
        try: bundled_revision=int(float((bundled_row or {}).get("catalog_price_revision",0) or 0))
        except (TypeError,ValueError): bundled_revision=0
        if bundled_row and bundled_revision > current_revision:
            for field in _BUNDLED_PRICE_FIELDS:
                if field in bundled_row:row[field]=deepcopy(bundled_row[field])
                else:row.pop(field,None)
            changed=True
        rows.append(row)
    return rows,changed


def load_core_article_catalog() -> list[dict]:
    """Load the global article database, seeded/extended from the bundled database.

    The merged catalog is cached by the user-file timestamp/size.  Both the
    bundled rows and stored rows are already normalized independently, so the
    merge path deliberately avoids normalizing the full 3k+ catalogue a second
    time.  This is important for the Artikler/BOM dialog where the catalogue is
    normally first touched interactively.
    """
    global _ARTICLE_CATALOG_CACHE_SIGNATURE, _ARTICLE_CATALOG_CACHE_ROWS
    path = article_catalog_path()
    signature=_article_catalog_signature(path)
    if _ARTICLE_CATALOG_CACHE_ROWS is not None and signature == _ARTICLE_CATALOG_CACHE_SIGNATURE:
        return deepcopy(_ARTICLE_CATALOG_CACHE_ROWS)

    # load_predefined_article_catalog() already returns normalized records from
    # its cached bundle.  Do not run normalize_article_catalog() over them again.
    bundled = core.load_predefined_article_catalog()
    stored = []
    bundled_price_refresh = False
    if path.is_file():
        raw = read_json(path, {})
        if isinstance(raw, dict):
            stored = core.normalize_article_catalog(raw.get("articles", []))
        elif isinstance(raw, list):
            stored = core.normalize_article_catalog(raw)
        stored,bundled_price_refresh=_refresh_bundled_catalog_prices(stored,bundled)

    # Stored/user data is authoritative.  Only append bundled article numbers
    # that are genuinely missing.  Since both sources are normalized already,
    # another whole-catalogue semantic enrichment pass would be redundant.
    rows = list(stored)
    seen={str(a.get("article_no","") or "").casefold() for a in rows}
    added=bundled_price_refresh
    for article in bundled:
        key=str(article.get("article_no","") or "").casefold()
        if key and key not in seen:
            rows.append(dict(article)); seen.add(key); added=True

    # Materialise the database in the user-data area. This makes it a real
    # piece of portable core data rather than a project-local snapshot.
    if not path.is_file() or added:
        save_core_article_catalog(rows)
        signature=_article_catalog_signature(path)
    _ARTICLE_CATALOG_CACHE_SIGNATURE=signature
    _ARTICLE_CATALOG_CACHE_ROWS=deepcopy(rows)
    return deepcopy(rows)


def save_core_article_catalog(records: Iterable[dict]) -> Path:
    global _ARTICLE_CATALOG_CACHE_SIGNATURE, _ARTICLE_CATALOG_CACHE_ROWS
    rows = core.normalize_article_catalog(list(records or []))
    path = article_catalog_path()
    atomic_write_json(path, {"version": ARTICLE_CATALOG_VERSION, "articles": rows})
    _ARTICLE_CATALOG_CACHE_SIGNATURE=_article_catalog_signature(path)
    _ARTICLE_CATALOG_CACHE_ROWS=deepcopy(rows)
    return path


def merge_core_article_catalog(records: Iterable[dict], *, overwrite: bool = False) -> tuple[list[dict], int]:
    """Merge records into the global article database without stale-project rollback.

    During legacy project migration, an incoming record may replace the current
    value only when the current value is still identical to the bundled base
    record. Once the user has a distinct core-data version, that version wins.
    Explicit package import uses its own authoritative merge/replace logic.
    """
    current = load_core_article_catalog()
    merged = {a["article_no"]: a for a in current}
    bundled = {a["article_no"]: a for a in core.normalize_article_catalog(core.load_predefined_article_catalog())}
    added = 0
    changed = False
    for row in core.normalize_article_catalog(list(records or [])):
        no = row["article_no"]
        existing = merged.get(no)
        if existing is None:
            merged[no] = row; added += 1; changed = True
            continue
        if existing == row:
            continue
        if overwrite or existing == bundled.get(no):
            merged[no] = row; changed = True
    rows = core.normalize_article_catalog(merged.values())
    if changed:
        save_core_article_catalog(rows)
    return rows, added


def _valid_price_amount(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if not (amount >= 0 and amount < 1e12):
        return None
    return amount


def normalize_article_prices(data) -> dict[str, dict]:
    """Normalisér global prisbog: artikelnummer -> prisdata.

    Prisbog v5 holder *estimat*, webshop-observationer, pakningsgrundlag og *manuel pris* adskilt.
    Webshopestimater fra v3 og ældre samt WAGO-estimater fra v4 invalideres
    ved indlæsning, fordi de kan have behandlet en hel salgsæske som én
    fysisk stk. Manuelle priser bevares.
    ``unit_price`` fra
    ældre versioner migreres automatisk: poster mærket ``Manuel ...`` bliver
    manuel pris, mens øvrige poster bliver estimater.  Effektiv pris beregnes
    først ved overlay på artiklen og gemmes derfor ikke som autoritativ data.
    """
    source_version = 0
    if isinstance(data, dict) and "prices" in data:
        try: source_version = int(data.get("version", 0) or 0)
        except (TypeError, ValueError): source_version = 0
        data = data.get("prices", {})
    if isinstance(data, list):
        data = {str(r.get("article_no", "") or ""): r for r in data if isinstance(r, dict)}
    if not isinstance(data, dict):
        return {}
    out = {}
    for article_no, raw in data.items():
        if not isinstance(raw, dict):
            continue
        no = str(article_no or raw.get("article_no", "") or "").strip()
        if not no:
            continue

        estimated = _valid_price_amount(raw.get("estimated_price"))
        manual = _valid_price_amount(raw.get("manual_price"))
        legacy = _valid_price_amount(raw.get("unit_price"))
        legacy_kind = str(raw.get("price_kind", "") or "").strip()
        if estimated is None and manual is None and legacy is not None:
            if "manuel" in legacy_kind.casefold():
                manual = legacy
            else:
                estimated = legacy

        if estimated is None and manual is None:
            continue

        legacy_source = str(raw.get("price_source", "") or "").strip()
        legacy_checked = str(raw.get("price_checked", "") or "").strip()

        # 0.59.24-0.59.26 kunne gemme pakke-/æskepris som kr./stk. Webshop-
        # estimater fra de gamle prisbogsversioner må derfor ikke bruges videre.
        # En eventuel manuel pris er autoritativ og bevares.
        webshop_estimate=bool(
            raw.get("price_observations") or
            "webshops:" in str(raw.get("estimated_price_source", "") or "").casefold()
        )
        wago_connector=bool(re.match(r"^(?:221|2273)-\d+",no,re.I))
        stale_webshop_estimate = bool(
            source_version and webshop_estimate and (
                source_version < 4 or
                (source_version < PRICEBOOK_VERSION and wago_connector)
            )
        )
        if stale_webshop_estimate:
            estimated = None

        if estimated is None and manual is None:
            continue

        rec = {
            "price_currency": str(raw.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK",
            "price_unit": str(raw.get("price_unit", "") or "").strip(),
            "price_note": str(raw.get("price_note", "") or "").strip(),
        }
        if estimated is not None:
            rec["estimated_price"] = estimated
            rec["estimated_price_source"] = str(raw.get("estimated_price_source", legacy_source if manual is None else "") or "").strip()
            rec["estimated_price_checked"] = str(raw.get("estimated_price_checked", legacy_checked if manual is None else "") or "").strip()
            for key in ("estimated_price_confidence", "estimated_price_method"):
                value=str(raw.get(key, "") or "").strip()
                if value: rec[key]=value
            for key in ("estimated_price_sources", "estimated_price_min", "estimated_price_max"):
                value=raw.get(key)
                if value is not None and str(value).strip() != "":
                    try: rec[key]=float(value) if key != "estimated_price_sources" else int(value)
                    except (TypeError, ValueError): pass
            observations=[]
            for obs in (raw.get("price_observations", []) or []):
                if not isinstance(obs,dict): continue
                try:
                    incl=float(obs.get("price_incl_vat")); excl=float(obs.get("price_excl_vat"))
                except (TypeError,ValueError): continue
                if incl <= 0 or excl <= 0: continue
                observation={
                    "provider":str(obs.get("provider","") or "").strip(),
                    "provider_key":str(obs.get("provider_key","") or "").strip(),
                    "price_incl_vat":incl,"price_excl_vat":excl,
                    "currency":str(obs.get("currency","DKK") or "DKK").upper(),
                    "price_unit":str(obs.get("price_unit",rec.get("price_unit","") or "stk") or "stk"),
                    "url":str(obs.get("url","") or "").strip(),
                    "matched_by":str(obs.get("matched_by","") or "").strip(),
                    "matched_value":str(obs.get("matched_value","") or "").strip(),
                    "checked":str(obs.get("checked","") or "").strip(),
                    "confidence":str(obs.get("confidence","") or "").strip(),
                    "vat_rate":float(obs.get("vat_rate",0.25) or 0.25),
                    "normalization_version":int(obs.get("normalization_version",2) or 2),
                }
                for key in ("raw_price_incl_vat","raw_price_excl_vat","package_quantity"):
                    value=obs.get(key)
                    if value is not None and str(value).strip() != "":
                        try: observation[key]=float(value)
                        except (TypeError,ValueError): pass
                label=str(obs.get("package_label","") or "").strip()
                if label: observation["package_label"]=label
                observations.append(observation)
            if observations: rec["price_observations"]=observations
        if manual is not None:
            rec["manual_price"] = manual
            rec["manual_price_source"] = str(raw.get("manual_price_source", legacy_source if estimated is None else "") or "").strip()
            rec["manual_price_checked"] = str(raw.get("manual_price_checked", legacy_checked if estimated is None else "") or "").strip()
        out[no] = rec
    return out


def article_price_view(price_record, *, article_unit="") -> dict:
    """Returnér effektiv prisvisning uden at miste estimatet bag et override."""
    raw = dict(price_record or {})
    estimated = _valid_price_amount(raw.get("estimated_price"))
    manual = _valid_price_amount(raw.get("manual_price"))
    effective = manual if manual is not None else estimated
    if effective is None:
        return {}
    manual_active = manual is not None
    currency = str(raw.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK"
    price_unit = str(raw.get("price_unit", "") or article_unit or "stk").strip() or "stk"
    source = str(raw.get("manual_price_source" if manual_active else "estimated_price_source", "") or "").strip()
    checked = str(raw.get("manual_price_checked" if manual_active else "estimated_price_checked", "") or "").strip()
    view = dict(raw)
    view.update({
        "effective_price": effective,
        # Backward-compatible alias used throughout BOM and existing plugins.
        "unit_price": effective,
        "price_currency": currency,
        "price_unit": price_unit,
        "price_kind": "Manuel" if manual_active else "Estimat",
        "price_status": "Manuel" if manual_active else "Estimeret",
        "price_source": source,
        "price_checked": checked,
        "price_is_manual": manual_active,
    })
    return view


def load_article_prices() -> dict[str, dict]:
    path = article_prices_path()
    if not path.is_file():
        return {}
    raw = read_json(path, {})
    normalized = normalize_article_prices(raw)
    # Behold de gamle effektive felter som read-only kompatibilitetsaliaser.
    # Ældre plugins/tests kan dermed fortsætte med ``unit_price`` samtidig med
    # at v2-prisbogen autoritativt gemmer estimated/manual separat.
    out={}
    for no, rec in normalized.items():
        item=dict(rec); view=article_price_view(rec,article_unit=rec.get("price_unit", ""))
        for key in ("effective_price","unit_price","price_kind","price_status","price_source","price_checked","price_is_manual"):
            if key in view:item[key]=view[key]
        out[no]=item
    return out


def save_article_prices(records) -> Path:
    prices = normalize_article_prices(records)
    payload = {"version": PRICEBOOK_VERSION, "prices": prices}
    path = article_prices_path()
    atomic_write_json(path, payload)
    return path


def apply_article_prices(records: Iterable[dict], prices=None, *, assume_normalized: bool = False,
                         prices_normalized: bool = False) -> list[dict]:
    """Læg prisbog oven på artikelmetadata; manuel pris har altid prioritet.

    ``assume_normalized`` is used by the interactive article/BOM UI after it
    has loaded the authoritative core catalogue.  It avoids two expensive
    whole-catalogue semantic normalization passes while preserving the old safe
    default for import/plugin callers that may supply arbitrary records.
    ``prices_normalized`` similarly avoids re-normalizing a price book returned
    directly by :func:`load_article_prices`.
    """
    raw_prices=load_article_prices() if prices is None else prices
    pricebook = dict(raw_prices or {}) if prices_normalized else normalize_article_prices(raw_prices)
    rows = list(records or []) if assume_normalized else core.normalize_article_catalog(list(records or []))
    out = []
    source_keys={
        "estimated_price","manual_price","unit_price","effective_price",
        "estimated_price_source","manual_price_source","estimated_price_checked","manual_price_checked",
        "estimated_price_confidence","estimated_price_method","estimated_price_sources",
        "estimated_price_min","estimated_price_max","price_observations","price_currency","price_unit","price_note",
    }
    for row in rows:
        item = dict(row)
        no = item.get("article_no", "")
        # Most catalogue rows have no embedded price data at all.  Avoid calling
        # normalize_article_prices thousands of times for that common case.
        source_price={}
        if any(key in item and item.get(key) not in (None, "", [], {}) for key in source_keys):
            source_price = normalize_article_prices({no: item}).get(no, {})
        override = pricebook.get(no, {})
        combined = dict(source_price)
        # Prisbogens estimat må gerne erstatte et kildeestimat, og dens manuelle
        # pris er altid øverste lag. Tomme metadata i prisbogen overskriver ikke
        # nyttig provenance fra kataloget.
        for key, value in override.items():
            if value not in (None, "") or key in {"price_note", "price_unit"}:
                combined[key] = value
        view = article_price_view(combined, article_unit=item.get("unit", "stk"))
        if view:
            item.update(view)
        out.append(item)
    return out if assume_normalized else core.normalize_article_catalog(out)


def merge_price_estimates(records, estimates) -> dict[str, dict]:
    """Flet automatiske webshopestimater ind uden at røre manuelle overrides."""
    current=normalize_article_prices(records)
    for article_no, estimate in dict(estimates or {}).items():
        no=str(article_no or "").strip()
        if not no or not isinstance(estimate,dict): continue
        existing=dict(current.get(no,{}) or {})
        # Kun estimatorens egne felter må ændres. Manuelle felter og brugerens
        # note/enhedsvalg bevares altid.
        for key in (
            "estimated_price","estimated_price_source","estimated_price_checked",
            "estimated_price_confidence","estimated_price_method","estimated_price_sources",
            "estimated_price_min","estimated_price_max","price_observations",
        ):
            if key in estimate: existing[key]=deepcopy(estimate[key])
        existing.setdefault("price_currency",str(estimate.get("price_currency","DKK") or "DKK"))
        if not existing.get("price_unit"):
            existing["price_unit"]=str(estimate.get("price_unit","") or "")
        current[no]=existing
    return normalize_article_prices(current)


def load_global_bom_library() -> tuple[list[dict], list[dict]]:
    path = bom_assemblies_path()
    if not path.is_file():
        return [], []
    raw = read_json(path, None)
    if raw is None:
        return [], []
    if isinstance(raw, list):  # 0.41.2 beta/legacy global format
        return core.normalize_bom_assemblies(raw), []
    if not isinstance(raw, dict):
        return [], []
    assemblies = core.normalize_bom_assemblies(raw.get("assemblies", []))
    articles = core.normalize_article_catalog(raw.get("articles", []))
    return assemblies, articles


def load_global_bom_assemblies() -> list[dict]:
    return load_global_bom_library()[0]


def load_global_bom_articles() -> list[dict]:
    return load_global_bom_library()[1]


def save_global_bom_assemblies(records: Iterable[dict], article_catalog: Iterable[dict] | None = None) -> Path:
    rows = core.normalize_bom_assemblies(list(records or []))
    all_articles = core.normalize_article_catalog(list(article_catalog or []))
    wanted = {item["article_no"] for row in rows for item in row.get("items", [])}
    articles = [a for a in all_articles if a.get("article_no") in wanted]
    payload = {
        "version": _LIBRARY_VERSION,
        "assemblies": rows,
        # Snapshot af artikler som styklisterne bruger. Det gør globale
        # styklister anvendelige i andre projekter, også for brugerartikler.
        "articles": articles,
    }
    path = bom_assemblies_path()
    atomic_write_json(path, payload)
    return path


def merge_global_bom_assemblies(records: Iterable[dict], article_catalog: Iterable[dict] | None = None) -> tuple[list[dict], int]:
    """Flet gamle projektafhængige styklister ind i brugerbiblioteket.

    Eksisterende globale ID'er er autoritative. Nye legacy-ID'er tilføjes.
    """
    current, saved_articles = load_global_bom_library()
    incoming = core.normalize_bom_assemblies(list(records or []))
    ids = {row["id"] for row in current}
    added = 0
    for row in incoming:
        if row["id"] in ids:
            continue
        current.append(row)
        ids.add(row["id"])
        added += 1
    current = core.normalize_bom_assemblies(current)
    if added:
        merged_articles = core.normalize_article_catalog(list(saved_articles) + list(article_catalog or []))
        save_global_bom_assemblies(current, merged_articles)
    return current, added


def migrate_legacy_project_core_data(project_raw: dict) -> dict:
    """Move pre-0.45 project-embedded core data into the global stores.

    Each category is removed from ``project_raw`` only after it has been saved
    successfully, so a partial migration never silently loses data.
    """
    result={"changed":False,"articles":0,"assemblies":0,"custom_symbols":0}
    if not isinstance(project_raw,dict):
        return result

    legacy_articles=core.normalize_article_catalog(project_raw.get("article_catalog",[]))
    if legacy_articles:
        _rows,added=merge_core_article_catalog(legacy_articles)
        project_raw.pop("article_catalog",None)
        result["articles"]=len(legacy_articles); result["changed"]=True

    legacy_custom=list(project_raw.get("custom_symbols",[]) or []) if isinstance(project_raw.get("custom_symbols",[]),list) else []
    if legacy_custom:
        settings=app_settings.load_app_settings()
        existing={str(r.get("code","") or ""):deepcopy(r) for r in settings.get("custom_symbols",[]) if isinstance(r,dict) and str(r.get("code","") or "")}
        count=0
        for row in legacy_custom:
            if not isinstance(row,dict):continue
            code=str(row.get("code","") or "").strip()
            if not code:continue
            existing[code]=deepcopy(row); count+=1
        settings["custom_symbols"]=list(existing.values())
        app_settings.save_app_settings(settings)
        core.register_custom_symbol_records(settings["custom_symbols"])
        project_raw.pop("custom_symbols",None)
        result["custom_symbols"]=count; result["changed"]=True

    legacy_assemblies=core.normalize_bom_assemblies(project_raw.get("bom_assemblies",[]))
    if legacy_assemblies:
        merged,added=merge_global_bom_assemblies(legacy_assemblies,load_core_article_catalog())
        project_raw.pop("bom_assemblies",None)
        result["assemblies"]=len(legacy_assemblies); result["changed"]=True
    return result


def backup_core_article_catalog(label: str = "backup") -> Path:
    """Create a timestamped safety copy of the current global article database."""
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(label or "backup"))
    folder = core_data_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / f"articles_{safe}_{stamp}.json"
    rows = load_core_article_catalog()
    atomic_write_json(target, {"version": ARTICLE_CATALOG_VERSION, "articles": rows})
    return target


def _read_articles_from(directory: Path) -> list[dict]:
    path = directory / "articles.json"
    if not path.is_file():
        return []
    raw = read_json(path, {})
    return core.normalize_article_catalog(raw.get("articles", []) if isinstance(raw, dict) else raw)


def _read_prices_from(directory: Path) -> dict[str, dict]:
    path = directory / "article_prices.json"
    return normalize_article_prices(read_json(path, {})) if path.is_file() else {}


def _read_assemblies_from(directory: Path) -> tuple[list[dict], list[dict]]:
    path = directory / "bom_assemblies.json"
    if not path.is_file():
        return [], []
    raw = read_json(path, {})
    if isinstance(raw, list):
        return core.normalize_bom_assemblies(raw), []
    if not isinstance(raw, dict):
        return [], []
    return (
        core.normalize_bom_assemblies(raw.get("assemblies", [])),
        core.normalize_article_catalog(raw.get("articles", [])),
    )


def _merge_rows(source: Iterable[dict], target: Iterable[dict], key: str) -> list[dict]:
    """Flet rækker med målplaceringen som autoritativ ved konflikter."""
    merged = {}
    for row in list(source or []) + list(target or []):
        value = str(row.get(key, "") or "").strip()
        if value:
            merged[value.casefold()] = deepcopy(row)
    return list(merged.values())


def migrate_core_data_directory(source: str | Path, target: str | Path) -> dict:
    """Kopiér/flet global artikeldata til en ny projektafhængig placering.

    Kilden slettes ikke. Hvis målplaceringen allerede indeholder kernedata,
    sikkerhedskopieres de først og har derefter forrang ved nøglekonflikter.
    """
    source_dir = Path(source).expanduser()
    target_dir = Path(target).expanduser()
    if source_dir.resolve(strict=False) == target_dir.resolve(strict=False):
        articles = _read_articles_from(target_dir)
        prices = _read_prices_from(target_dir)
        assemblies, _snapshots = _read_assemblies_from(target_dir)
        return {"articles": len(articles), "prices": len(prices), "assemblies": len(assemblies), "backup": None, "unchanged": True}

    target_dir.mkdir(parents=True, exist_ok=True)
    existing = [target_dir / name for name in CORE_DATA_FILENAMES if (target_dir / name).is_file()]
    backup = None
    if existing:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = target_dir / "backups" / f"before-storage-change-{stamp}"
        backup.mkdir(parents=True, exist_ok=False)
        for path in existing:
            shutil.copy2(path, backup / path.name)

    source_articles = _read_articles_from(source_dir)
    target_articles = _read_articles_from(target_dir)
    articles = core.normalize_article_catalog(_merge_rows(source_articles, target_articles, "article_no"))

    source_prices = _read_prices_from(source_dir)
    target_prices = _read_prices_from(target_dir)
    price_rows = {}
    for article_no, record in list(source_prices.items()) + list(target_prices.items()):
        price_rows[str(article_no).casefold()] = (str(article_no), deepcopy(record))
    prices = {article_no: record for article_no, record in price_rows.values()}

    source_assemblies, source_snapshots = _read_assemblies_from(source_dir)
    target_assemblies, target_snapshots = _read_assemblies_from(target_dir)
    assemblies = core.normalize_bom_assemblies(_merge_rows(source_assemblies, target_assemblies, "id"))
    snapshot_pool = _merge_rows(list(source_snapshots) + list(target_snapshots), articles, "article_no")
    wanted = {str(item.get("article_no", "") or "") for row in assemblies for item in row.get("items", [])}
    snapshots = core.normalize_article_catalog(row for row in snapshot_pool if row.get("article_no") in wanted)

    atomic_write_json(target_dir / "articles.json", {"version": ARTICLE_CATALOG_VERSION, "articles": articles})
    atomic_write_json(target_dir / "article_prices.json", {"version": PRICEBOOK_VERSION, "prices": normalize_article_prices(prices)})
    atomic_write_json(target_dir / "bom_assemblies.json", {
        "version": BOM_LIBRARY_VERSION,
        "assemblies": assemblies,
        "articles": snapshots,
    })
    return {
        "articles": len(articles), "prices": len(prices), "assemblies": len(assemblies),
        "backup": backup, "unchanged": False,
    }
