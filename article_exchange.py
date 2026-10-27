from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import core_logic as core

FORMAT_NAME = "ElplanDWGEditor article library"
FORMAT_VERSION = 4

# Stable, human-friendly order for CSV. Unknown future fields are appended.
CSV_FIELDS = [
    "article_no", "description", "manufacturer", "unit", "consumption_unit", "sales_unit",
    "sales_package_quantity", "minimum_order_quantity", "package_label", "category", "series",
    "brand", "category_normalized", "product_type", "function", "product_family", "product_variant", "design_family_raw", "module_size", "color", "mounting_type",
    "el_no", "ean", "status", "kind", "cable_spec", "package_length_m",
    "product_page", "supplier_page", "datasheet_url", "image_url", "image_source",
    "source", "source_checked", "diameter_mm", "cutout_mm", "cct", "power_w",
    "ip_rating", "shape", "environment", "estimated_price", "price_currency", "price_unit", "estimated_price_source", "estimated_price_checked",
    "variant_group_manual", "compatibility", "semantic_evidence", "technical_specs_manual", "relations", "note",
]


# One shared schema drives the in-app import guide and bundled templates.
# ``article_no`` is the only hard requirement; the remaining fields are optional.
ARTICLE_FIELD_GUIDE = [
    ("article_no", "Artikelnummer", "Påkrævet", "Unikt artikel-/varenummer. Bruges som stabil nøgle ved import og fletning.", "ABC-123"),
    ("description", "Beskrivelse", "Anbefalet", "Kort, entydig produktbeskrivelse.", "Dobbelt stikkontakt 2P+E, 2M"),
    ("manufacturer", "Fabrikat", "Anbefalet", "Producent eller fabrikat.", "Schneider Electric / Lauritz Knudsen"),
    ("brand", "Brand", "Valgfri", "Brand/produktmærke når det skal adskilles fra den juridiske producent.", "LK"),
    ("unit", "Enhed", "Valgfri", "Mængdeenhed. Hvis feltet mangler bruges 'stk'.", "stk"),
    ("consumption_unit", "Forbrugsenhed", "Valgfri", "Enheden projektet forbruger og BOM-behovet opgøres i, fx stk eller m.", "stk"),
    ("sales_unit", "Salgsenhed", "Valgfri", "Enheden varen bestilles i, fx pakke, rulle eller stk.", "pakke"),
    ("sales_package_quantity", "Antal pr. salgsenhed", "Valgfri", "Hvor mange forbrugsenheder én salgsenhed indeholder.", "50"),
    ("minimum_order_quantity", "Mindste bestilling", "Valgfri", "Mindste antal salgsenheder der kan bestilles.", "1"),
    ("package_label", "Pakningsbeskrivelse", "Valgfri", "Kort leverandørtekst for pakningen. Udledes automatisk hvis den er tom.", "Pakke á 50 stk."),
    ("category", "Kategori", "Valgfri", "Overordnet kategori til filtrering.", "LK FUGA · Stikkontakter og udtag"),
    ("category_normalized", "Standardkategori", "Valgfri", "Kontrolleret Elplan-kategori. Ukendte værdier bliver valideret i Datakvalitet.", "Installation · Stikkontakter og udtag"),
    ("series", "Serie (kilde)", "Valgfri", "Producentens/kildens rå serienavn. Kan historisk blande familie og variant; bruges derfor ikke alene som kontrolleret identitet.", "LK FUGA AIR"),
    ("product_type", "Produkttype", "Valgfri", "Brugerrettet produkttype til filtrering.", "Stikkontakt / udtag"),
    ("function", "Funktion", "Valgfri", "Produktspecifik funktion, fx Kroneafbryder, Lampeudtag eller Samlemuffe.", "Stikkontakt"),
    ("product_family", "Produktfamilie", "Valgfri", "Kontrolleret produktfamilie. Beskriver hvad produktet ER, ikke hvad det passer sammen med.", "LK FUGA AIR"),
    ("product_variant", "Produktvariant", "Valgfri", "Produktets egen variant inden for familien, fx Standard eller SLIM.", "Standard"),
    ("design_family_raw", "Legacy design (rå)", "Valgfri", "Historisk/producentnært designfelt bevaret som provenance. Må ikke bruges som kompatibilitetsbevis.", "SLIM"),
    ("module_size", "Modul", "Valgfri", "Modulstørrelse, fx 1M, 1½M, 2M eller 2×1M.", "2M"),
    ("color", "Farve", "Valgfri", "Produktets farve.", "Koksgrå"),
    ("mounting_type", "Montagetype", "Valgfri", "Montage-/installationstype.", "Forfradåse"),
    ("el_no", "EL-nr.", "Valgfri", "Dansk EL-nummer/LM-nummer hvis kendt.", "1017056211"),
    ("ean", "EAN", "Valgfri", "EAN/GTIN som tekst, så eventuelle foranstillede nuller bevares.", "5703302157070"),
    ("status", "Status", "Valgfri", "Fx Aktiv, Udgået eller Ukendt.", "Aktiv"),
    ("kind", "Art", "Valgfri", "Intern hovedtype. Brug 'cable' for kabelartikler, ellers normalt 'component'.", "component"),
    ("cable_spec", "Kabelspecifikation", "Valgfri", "Kabeldimension/-specifikation for kabelartikler.", "3G1,5"),
    ("package_length_m", "Pakkelængde [m]", "Valgfri", "Fast pakke-/rullelængde i meter. 0 kan bruges for afmålt kabel.", "100"),
    ("product_page", "Produktlink", "Valgfri", "URL til producentens produktside.", "https://example.com/product"),
    ("supplier_page", "Leverandørlink", "Valgfri", "URL til grossist/leverandør.", "https://example.com/supplier"),
    ("datasheet_url", "Datablad", "Valgfri", "Direkte URL til datablad eller dokumentation.", "https://example.com/datasheet.pdf"),
    ("image_url", "Billede", "Valgfri", "Direkte URL til produktbillede. Bruges af billedpreviewet.", "https://example.com/product.jpg"),
    ("image_source", "Billedkilde", "Valgfri", "Kilde/credit for produktbilledet.", "Producent"),
    ("source", "Kilde", "Valgfri", "Kilde til artikelmetadata.", "https://example.com/catalog"),
    ("source_checked", "Kilde kontrolleret", "Valgfri", "Dato for seneste kontrol i ISO-format ÅÅÅÅ-MM-DD.", "2026-08-22"),
    ("diameter_mm", "Diameter [mm]", "Valgfri", "Produktdiameter i mm, hvis relevant.", "85"),
    ("cutout_mm", "Udskæring [mm]", "Valgfri", "Udskæringsmål i mm, hvis relevant.", "76"),
    ("cct", "CCT", "Valgfri", "Farvetemperatur, fx 2700K eller 3000K.", "3000K"),
    ("power_w", "Effekt [W]", "Valgfri", "Nominel effekt i watt.", "7.5"),
    ("ip_rating", "IP", "Valgfri", "IP-klasse.", "IP44"),
    ("shape", "Form", "Valgfri", "Form/fysisk udførelse, hvis relevant.", "Rund"),
    ("environment", "Miljø", "Valgfri", "Anvendelsesmiljø, fx Inde/Ude.", "Inde"),
    ("estimated_price", "Estimeret pris", "Valgfri", "Automatisk/importeret prisestimat ekskl. moms. Manuelle priser gemmes separat og har altid prioritet.", "49.95"),
    ("price_currency", "Prisvaluta", "Valgfri", "Valuta for prisestimat, normalt DKK.", "DKK"),
    ("price_unit", "Pris pr.", "Valgfri", "Enheden som prisestimatet gælder for, fx stk, m, rulle eller pakke.", "stk"),
    ("estimated_price_source", "Priskilde", "Valgfri", "Kilde til det importerede prisestimat.", "Grossist / prisestimat"),
    ("estimated_price_checked", "Pris opdateret", "Valgfri", "Dato for prisestimat i ISO-format ÅÅÅÅ-MM-DD.", "2026-08-26"),
    ("variant_group_manual", "Variantgruppe", "Valgfri", "Manuelt gruppenavn hvis automatisk variantgruppering skal tilsidesættes.", "FUGA 1½M stikkontakt m. jord"),
    ("compatibility", "Kompatibilitet", "Valgfri", "JSON-objekt med verificeret kompatibilitet, fx designserier eller montagesystemer. Kompatibilitet er adskilt fra produktidentiteten.", '{"design_series":["CHOICE","PURE","SOFT"]}'),
    ("technical_specs_manual", "Tekniske egenskaber", "Valgfri", "JSON-objekt med manuelt verificerede tekniske egenskaber. JSON anbefales frem for CSV.", '{"rated_current":"16 A","has_earth":"Ja"}'),
    ("relations", "Relationer", "Valgfri", "JSON-liste med bekræftede relationer til andre artikelnumre. Automatiske forslag gemmes ikke her.", '[{"type":"compatible","target_article_no":"ABC-124"}]'),
    ("note", "Note", "Valgfri", "Fri note. Overskrives aldrig af tomme importfelter.", "Eksempelnote"),
]

CSV_TEMPLATE_COLUMNS = [(label, key) for key, label, _level, _description, _example in ARTICLE_FIELD_GUIDE]

ALIASES = {
    "artikelnummer": "article_no",
    "artikel nr": "article_no",
    "artikelnr": "article_no",
    "article number": "article_no",
    "article_no": "article_no",
    "varenummer": "article_no",
    "varenr": "article_no",
    "beskrivelse": "description",
    "description": "description",
    "fabrikat": "manufacturer",
    "producent": "manufacturer",
    "manufacturer": "manufacturer",
    "enhed": "unit",
    "unit": "unit",
    "forbrugsenhed": "consumption_unit",
    "consumption unit": "consumption_unit",
    "consumption_unit": "consumption_unit",
    "salgsenhed": "sales_unit",
    "sales unit": "sales_unit",
    "sales_unit": "sales_unit",
    "antal pr. salgsenhed": "sales_package_quantity",
    "pakningsantal": "sales_package_quantity",
    "sales_package_quantity": "sales_package_quantity",
    "mindste bestilling": "minimum_order_quantity",
    "minimum order quantity": "minimum_order_quantity",
    "minimum_order_quantity": "minimum_order_quantity",
    "pakningsbeskrivelse": "package_label",
    "package label": "package_label",
    "package_label": "package_label",
    "kategori": "category",
    "category": "category",
    "serie": "series",
    "series": "series",
    "type": "product_type",
    "produkttype": "product_type",
    "product_type": "product_type",
    "design": "design_family_raw",
    "design_family": "design_family_raw",
    "legacy design": "design_family_raw",
    "design_family_raw": "design_family_raw",
    "produktfamilie": "product_family",
    "product_family": "product_family",
    "produktvariant": "product_variant",
    "product_variant": "product_variant",
    "kompatibilitet": "compatibility",
    "compatibility": "compatibility",
    "modul": "module_size",
    "module_size": "module_size",
    "farve": "color",
    "color": "color",
    "el-nr": "el_no",
    "el nr": "el_no",
    "el_no": "el_no",
    "ean": "ean",
    "status": "status",
    "estimated_price": "estimated_price",
    "estimeret pris": "estimated_price",
    "prisvaluta": "price_currency",
    "price_currency": "price_currency",
    "pris pr.": "price_unit",
    "price_unit": "price_unit",
    "priskilde": "estimated_price_source",
    "estimated_price_source": "estimated_price_source",
    "pris opdateret": "estimated_price_checked",
    "estimated_price_checked": "estimated_price_checked",
    "note": "note",
    "produktlink": "product_page",
    "product_page": "product_page",
    "leverandørlink": "supplier_page",
    "supplier_page": "supplier_page",
    "datablad": "datasheet_url",
    "datasheet_url": "datasheet_url",
    "billede": "image_url",
    "billed-url": "image_url",
    "image_url": "image_url",
    "kabelspecifikation": "cable_spec",
    "cable_spec": "cable_spec",
}

# Accept every human-friendly CSV template header in addition to the legacy aliases.
for _label, _key in CSV_TEMPLATE_COLUMNS:
    ALIASES.setdefault(_label.strip().replace("_", " ").casefold(), _key)


def article_template_record(*, include_examples: bool = True) -> dict:
    """Return one template row generated from the exact import schema."""
    row = {}
    for key, _label, level, _description, example in ARTICLE_FIELD_GUIDE:
        if include_examples:
            row[key] = example
        elif level == "Påkrævet":
            row[key] = ""
        else:
            row[key] = ""
    return row


def save_article_template_json(path: str | Path, *, app_version: str = "") -> Path:
    path = Path(path)
    payload = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "application_version": str(app_version or ""),
        "articles": [article_template_record(include_examples=True)],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_article_template_csv(path: str | Path) -> Path:
    path = Path(path)
    example = article_template_record(include_examples=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[label for label, _key in CSV_TEMPLATE_COLUMNS], delimiter=";")
        writer.writeheader()
        writer.writerow({label: example.get(key, "") for label, key in CSV_TEMPLATE_COLUMNS})
    return path


@dataclass(frozen=True)
class ArticleImport:
    articles: list[dict]
    source_format: str
    raw_count: int


def _canonical_header(value: str) -> str:
    text = str(value or "").strip().replace("_", " ").casefold()
    return ALIASES.get(text, str(value or "").strip())


def _clean_mapping(row: dict) -> dict:
    out = {}
    for key, value in dict(row or {}).items():
        canon = _canonical_header(key)
        if not canon:
            continue
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            continue
        if canon in {"technical_specs_manual", "technical_specs", "relations", "variant_attributes", "variant_axes", "compatibility", "semantic_evidence"} and isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                pass
        out[canon] = value
    return out


def load_article_library(path: str | Path) -> ArticleImport:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return _load_csv(path)
    return _load_json(path)


def _load_json(path: Path) -> ArticleImport:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict):
        records = raw.get("articles", [])
        if not isinstance(records, list):
            raise ValueError("JSON-filen indeholder ikke en gyldig 'articles'-liste.")
    else:
        raise ValueError("JSON-filen skal være en liste eller et objekt med feltet 'articles'.")
    cleaned = [_clean_mapping(r) for r in records if isinstance(r, dict)]
    return ArticleImport(core.normalize_article_catalog(cleaned), "JSON", len(records))


def _load_csv(path: Path) -> ArticleImport:
    # utf-8-sig handles Excel's UTF-8 BOM. Sniffer supports both comma and semicolon.
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return ArticleImport([], "CSV", 0)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=";,\t,")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV-filen har ingen kolonneoverskrifter.")
    rows = []
    for raw in reader:
        mapped = {}
        for key, value in raw.items():
            if key is None:
                continue
            canon = _canonical_header(key)
            val = str(value or "").strip()
            if val:
                if canon in {"technical_specs_manual", "technical_specs", "relations", "variant_attributes", "variant_axes", "compatibility", "semantic_evidence"}:
                    try:
                        mapped[canon] = json.loads(val)
                    except Exception:
                        mapped[canon] = val
                else:
                    mapped[canon] = val
        rows.append(mapped)
    return ArticleImport(core.normalize_article_catalog(rows), "CSV", len(rows))


def save_article_library_json(path: str | Path, records: Iterable[dict], *, app_version: str = "") -> Path:
    path = Path(path)
    articles = core.normalize_article_catalog(list(records or []))
    payload = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "application_version": str(app_version or ""),
        "articles": articles,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_article_library_csv(path: str | Path, records: Iterable[dict]) -> Path:
    path = Path(path)
    articles = core.normalize_article_catalog(list(records or []))
    extra = []
    known = set(CSV_FIELDS)
    for row in articles:
        for key in row:
            if key not in known and key not in extra and not str(key).startswith("_"):
                extra.append(key)
    fields = CSV_FIELDS + sorted(extra, key=str.casefold)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in articles:
            values={}
            for k in fields:
                value=row.get(k, "")
                if isinstance(value,(dict,list,tuple)):
                    value=json.dumps(value,ensure_ascii=False,separators=(",",":"))
                values[k]=value
            writer.writerow(values)
    return path


def merge_article_catalog(existing: Iterable[dict], incoming: Iterable[dict], *, mode: str = "fill_missing") -> tuple[list[dict], dict]:
    """Merge imported records into the core article database.

    mode='fill_missing': add new rows and only fill blank fields on existing rows.
    mode='overwrite': add new rows and let non-empty imported fields replace existing fields.
    """
    current = core.normalize_article_catalog(list(existing or []))
    imported = core.normalize_article_catalog(list(incoming or []))
    by_key = {str(r.get("article_no", "")).casefold(): deepcopy(r) for r in current}
    order = [str(r.get("article_no", "")).casefold() for r in current]
    stats = {"added": 0, "updated": 0, "unchanged": 0, "incoming": len(imported)}
    overwrite = str(mode or "").casefold() == "overwrite"

    for row in imported:
        key = str(row.get("article_no", "")).casefold()
        if not key:
            continue
        old = by_key.get(key)
        if old is None:
            by_key[key] = deepcopy(row)
            order.append(key)
            stats["added"] += 1
            continue
        merged = deepcopy(old)
        for field, value in row.items():
            if field == "article_no":
                continue
            if value in (None, ""):
                continue
            if overwrite or merged.get(field) in (None, ""):
                merged[field] = deepcopy(value)
        # Keep the existing spelling/casing of article_no for stable references.
        merged["article_no"] = old.get("article_no", row.get("article_no", ""))
        merged_norm = core.normalize_article_catalog([merged])
        merged = merged_norm[0] if merged_norm else old
        if merged == old:
            stats["unchanged"] += 1
        else:
            by_key[key] = merged
            stats["updated"] += 1

    result = core.normalize_article_catalog([by_key[k] for k in order if k in by_key])
    return result, stats
