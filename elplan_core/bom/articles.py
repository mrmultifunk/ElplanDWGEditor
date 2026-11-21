"""Artikelkatalog, kategorier, pakninger og kabelartikelbindinger."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

import article_intelligence

from elplan_core.constants import CABLE_LAYER, CABLE_TYPES


ARTICLE_METADATA_FIELDS = (
    "category", "series", "el_no", "ean", "status", "kind",
    "cable_spec", "source", "source_checked",
    "product_type", "design_family", "design_family_raw", "module_size", "module_size_raw", "color", "color_raw", "mounting_type",
    "brand", "category_normalized", "category_group", "subcategory", "function", "taxonomy_version",
    "product_family", "product_variant", "product_family_manual", "product_variant_manual", "semantic_model_version",
    "variant_group_manual", "variant_group_id", "variant_group_label",
    "product_page", "supplier_page", "image_url", "image_local_path", "datasheet_url", "manual_url", "image_source",
    "diameter_mm", "cutout_mm", "cct", "power_w", "voltage", "dimming_type", "switch_input", "ip_rating", "shape", "environment",
    "price_currency", "price_unit", "price_kind", "price_status", "price_source", "price_checked", "price_note",
    "consumption_unit", "sales_unit", "package_label", "catalog_price_revision",
    "estimated_price_source", "estimated_price_checked", "estimated_price_confidence", "estimated_price_method",
    "manual_price_source", "manual_price_checked",
)

ARTICLE_STRUCTURED_FIELDS = (
    "technical_specs_manual", "technical_specs", "relations", "variant_attributes", "variant_axes",
    "compatibility", "semantic_evidence", "price_observations",
)


_ARTICLE_UNIT_ALIASES = {
    "styk":"stk", "stykke":"stk", "pieces":"stk", "piece":"stk", "each":"stk",
    "meter":"m", "metre":"m", "metres":"m", "meters":"m",
    "roll":"rulle", "coil":"rulle", "pack":"pakke", "package":"pakke",
    "set":"sæt", "saet":"sæt",
}


def normalize_article_unit(value, default="stk") -> str:
    """Normalisér almindelige enhedsnavne uden at afvise frie specialenheder."""
    text=str(value or "").strip().casefold().rstrip(".")
    if not text:
        text=str(default or "stk").strip().casefold() or "stk"
    return _ARTICLE_UNIT_ALIASES.get(text,text)


def _positive_article_number(value, default=1.0) -> float:
    try:number=float(value)
    except (TypeError,ValueError):number=float(default)
    return number if math.isfinite(number) and number > 0 else float(default)


def article_packaging(record) -> dict:
    """Returnér ét bagudkompatibelt forbrugs-/salgsgrundlag for en artikel.

    ``unit`` bevares som den eksisterende BOM-/leveringsenhed. De nye felter
    beskriver eksplicit hvad projektet forbruger, og hvordan varen købes. For
    ældre kabelruller udledes modellen fortsat af ``package_length_m``.
    """
    row=dict(record or {})
    legacy_unit=normalize_article_unit(row.get("unit","stk"))
    try:package_length=float(row.get("package_length_m",0) or 0)
    except (TypeError,ValueError):package_length=0.0
    packaged_cable=(str(row.get("kind","") or "").casefold()=="cable" and package_length > 0)
    package_qty=_positive_article_number(
        row.get("sales_package_quantity"),package_length if packaged_cable else 1.0)
    consumption=normalize_article_unit(row.get("consumption_unit"),"m" if packaged_cable else legacy_unit)
    default_sales=("rulle" if packaged_cable else ("pakke" if package_qty > 1.0000001 else legacy_unit))
    sales=normalize_article_unit(row.get("sales_unit"),default_sales)
    minimum=_positive_article_number(row.get("minimum_order_quantity"),1.0)
    label=str(row.get("package_label","") or "").strip()
    if not label and package_qty > 1.0000001:
        label=f"{sales} á {package_qty:g} {consumption}"
    return {
        "legacy_unit":legacy_unit,
        "consumption_unit":consumption,
        "sales_unit":sales,
        "sales_package_quantity":package_qty,
        "minimum_order_quantity":minimum,
        "package_label":label,
    }


def article_purchase_requirement(record, required_quantity) -> dict:
    """Beregn indkøbsmængde og overskud ud fra artiklens salgsforpakning."""
    pack=article_packaging(record)
    try:required=max(0.0,float(required_quantity or 0))
    except (TypeError,ValueError):required=0.0
    per_package=pack["sales_package_quantity"]
    packages=float(math.ceil(required/per_package-1e-12)) if required > 0 else 0.0
    packages=max(packages,pack["minimum_order_quantity"] if required > 0 else 0.0)
    purchased=packages*per_package
    surplus=max(0.0,purchased-required)
    summary=(
        f"{required:g} {pack['consumption_unit']} behov → {packages:g} {pack['sales_unit']}"
        if required > 0 else f"0 {pack['consumption_unit']}"
    )
    if per_package > 1.0000001:
        summary+=f" á {per_package:g} {pack['consumption_unit']}"
    if surplus > 1e-9:
        summary+=f" · {surplus:g} {pack['consumption_unit']} i overskud"
    return {**pack,"required_quantity":required,"purchase_quantity":packages,
            "purchased_consumption_quantity":purchased,"surplus_quantity":surplus,
            "summary":summary}


def article_price_basis_quantity(record, required_quantity) -> float:
    """Mængden en artikelpris skal multipliceres med for det givne behov."""
    pack=article_packaging(record); purchase=article_purchase_requirement(record,required_quantity)
    price_unit=normalize_article_unit(record.get("price_unit"),pack["consumption_unit"])
    if price_unit==pack["sales_unit"] and price_unit!=pack["consumption_unit"]:
        return float(purchase["purchase_quantity"])
    return float(purchase["required_quantity"])


def bom_article_category(record, roles=None, source_types=None) -> str:
    """Returnér en kort, brugerrettet BOM-type for filtrering og indkøb.

    Styklistens rolle har højeste prioritet, fordi samme produktfamilie fx kan
    indeholde både en indsats og dens tangent. Derefter bruges artikelgrunddata
    og beskrivelse. Formuleringer som ``uden tangent`` må ikke fejlkategorisere
    selve afbryderindsatsen som en tangent.
    """
    row=dict(record or {})
    role_text=" ".join(str(x or "") for x in (roles or [])).casefold()
    source_set={str(x or "").casefold() for x in (source_types or [])}
    if not row and not role_text:
        return "Ukendt artikel"
    if "cable" in source_set or str(row.get("kind","") or "").casefold()=="cable":
        return "Kabler"
    if "wago" in source_set:
        return "Samlemuffer og klemmer"

    role_rules=(
        ("afdæk","Afdækninger"),("tangent","Tangenter"),("indsats","Indsatser"),
        ("dåse","Dåser"),("montageramme","Rammer"),("ramme","Rammer"),
        ("muffe","Samlemuffer og klemmer"),("klemme","Samlemuffer og klemmer"),
        ("front","Fronter og tilbehør"),
    )
    for token,label in role_rules:
        if token in role_text:return label

    description=str(row.get("description","") or "").casefold()
    product_type=str(row.get("product_type","") or "").casefold()
    function=str(row.get("function","") or "").casefold()
    category=" ".join((str(row.get("category_normalized","") or ""),str(row.get("category","") or ""))).casefold()
    hay=" ".join((description,product_type,function,category))

    if ("afdækning" in description and "uden afdækning" not in description) or "dækbjælke" in description:
        return "Afdækninger"
    if "tangent" in description and "uden tangent" not in description and "uden tangenter" not in description:
        return "Tangenter"
    if "indsats" in description:return "Indsatser"
    if "dåse" in product_type or function=="dåse" or "· dåser" in category:return "Dåser"
    if "ramme" in product_type or function=="ramme" or "· rammer" in category:return "Rammer"
    if "samlemuffe" in hay or "klemmer og samlemateriel" in category:return "Samlemuffer og klemmer"
    if "kabel" in product_type or "kabel" in category:return "Kabler"
    if "lampeudtag" in hay:return "Lampeudtag"
    if "downlight" in hay or "armatur" in hay:return "Downlights og armaturer"
    if "front" in product_type or function=="front":return "Fronter og tilbehør"
    if "sensor" in hay or "pir" in hay:return "Sensorer"
    if "data og netværk" in category or "datakabel" in function:return "Data og netværk"
    if "stikkontakt" in hay or "udtag" in product_type:return "Stikkontakter og udtag"
    if "afbryder" in hay or "betjening" in product_type:return "Afbrydere og betjening"
    if "wiser" in hay or "lysstyring" in hay or "lysdæmper" in function:return "Lysstyring og smart home"
    if "tangent / afdækning" in product_type:return "Tangenter og afdækninger"
    return str(row.get("product_type","") or row.get("category_normalized","") or row.get("category","") or "Andet")


def _format_module_number(value: float) -> str:
    """Formatér valideret modulmål med dansk ½-notation."""
    value=float(value)
    if value.is_integer():
        return str(int(value))
    if abs((value % 1.0)-0.5) < 1e-9:
        whole=int(value)
        return (str(whole) if whole else "")+"½"
    return ""


def normalize_article_module(value) -> str:
    """Normalisér en *eksplicit* modulbetegnelse konservativt.

    Moduldata bruges som filter/taksonomi og må derfor ikke opfindes ud fra
    produkt-/varenummer-lignende tal. Vi accepterer kun halve moduler i et
    realistisk interval samt dokumenterede flerfeltsformer. Producentens rå
    værdi bliver ikke ændret i artikelposten; dette er alene UI-facetten.
    """
    text=str(value or "").strip().replace("×","x").replace(",",".").replace("½",".5")
    text=re.sub(r"\s+","",text)
    m=re.fullmatch(r"(\d+)x(\d+(?:\.5)?)M",text,re.I)
    if m:
        count=int(m.group(1)); size=float(m.group(2))
        # FUGA-lignende modulfelter i databasen ligger langt under dette.
        # Grænsen er bevidst konservativ, så fx 451200M aldrig bliver en facet.
        if 1 <= count <= 6 and 0.5 <= size <= 6.0 and abs(size*2-round(size*2)) < 1e-9 and count*size <= 12.0:
            size_txt=_format_module_number(size)
            return f"{count}×{size_txt}M" if size_txt else ""
        # Schneider Resi9 cabinet covers/rows use explicit Nx13M / Nx18M.
        if 1 <= count <= 4 and size in (13.0,18.0):
            return f"{count}×{int(size)}M"
        return ""
    m=re.fullmatch(r"((?:\d+(?:\.5)?|\.5))M",text,re.I)
    if not m:
        return ""
    size=float(m.group(1))
    if not (0.5 <= size <= 12.0 and abs(size*2-round(size*2)) < 1e-9):
        return ""
    size_txt=_format_module_number(size)
    return f"{size_txt}M" if size_txt else ""


def _module_label(value):
    """Find kun plausible modulbetegnelser i fri producenttekst.

    Det tidligere generiske ``\\d+M``-match kunne tolke fx et produkt-/mål-tal
    som ``451200M``. Vi finder nu kandidater og accepterer dem kun gennem den
    konservative modulvalidator ovenfor.
    """
    text=str(value or "").replace("×","x").replace(",",".").replace("½",".5")
    patterns=(
        r"(?<![\w])([1-6]\s*x\s*(?:[0-9](?:\.5)?|\.5)\s*M)(?![\w])",
        r"(?<![\w])((?:[0-9](?:\.5)?|\.5)\s*M)(?![\w])",
    )
    for pattern in patterns:
        for match in re.finditer(pattern,text,re.I):
            normalized=normalize_article_module(match.group(1))
            if normalized:
                return normalized
    return ""


def _module_group_label(module):
    normalized=normalize_article_module(module)
    if not normalized:
        return ""
    text=normalized.replace('×','x').replace('½','.5')
    m=re.fullmatch(r'(\d+)x(\d+(?:\.5)?)M',text,re.I)
    if m:
        total=int(m.group(1))*float(m.group(2))
    else:
        m=re.fullmatch(r'(\d+(?:\.5)?)M',text,re.I)
        if not m:return ''
        total=float(m.group(1))
    total_txt=_format_module_number(total)
    return f"{total_txt}M" if total_txt else ""


_ARTICLE_COLOR_CANONICAL = {
    "hvid":"Hvid", "lysegrå":"Lysegrå", "koksgrå":"Koksgrå",
    "sort":"Sort", "stål":"Stål", "staal":"Stål", "rød":"Rød",
    "roed":"Rød", "grøn":"Grøn", "groen":"Grøn", "blå":"Blå",
    "blaa":"Blå", "kobber":"Kobber", "krom":"Krom",
    "børstet alu":"Børstet alu", "boerstet alu":"Børstet alu",
    "uden afdækning":"Uden afdækning",
    "transparent / orange":"Transparent / orange",
    "transparent / hvid":"Transparent / hvid",
    "transparent / rød":"Transparent / rød",
    "transparent / gul":"Transparent / gul",
    "transparent / lysegrå":"Transparent / lysegrå",
    "grå":"Grå", "graa":"Grå", "gul":"Gul", "mørkegrå":"Mørkegrå",
    "moerkegraa":"Mørkegrå", "stålmetallic":"Stålmetallic", "staalmetallic":"Stålmetallic",
    "børstet aluminium":"Børstet aluminium", "antracitgrå":"Antracitgrå",
    "transparent":"Transparent", "klar":"Klar", "sort/hvid":"Sort / hvid",
    "hvid/hvid":"Hvid / hvid", "sort/sort":"Sort / sort", "frosted":"Frosted",
    "lys mellemgrå":"Lys mellemgrå", "orange":"Orange", "grå/mørkegrå":"Grå / mørkegrå",
    "naturel":"Naturel", "hvid/lysegrå":"Hvid / lysegrå", "rød/grøn":"Rød / grøn",
    "hvid/blå":"Hvid / blå", "ral 7035":"RAL 7035", "sort/orange":"Sort / orange",
    "hvid/sort":"Hvid / sort", "hvid/rød":"Hvid / rød", "sølvgrå":"Sølvgrå",
    "aqua":"Aqua", "grøn/hvid":"Grøn / hvid", "mørkebrun":"Mørkebrun",
    "polar hvid":"Polar hvid", "sort/rød":"Sort / rød", "hvid/gul":"Hvid / gul",
    "gul/grøn":"Gul / grøn", "beige":"Beige",
}


def normalize_article_color(value) -> str:
    """Saml kun trivielle stave-/spacingvarianter uden at ændre producentfarven."""
    raw=str(value or "").strip()
    if not raw:
        return ""
    compact=re.sub(r"\s*/\s*"," / ",re.sub(r"\s+"," ",raw)).strip()
    key=compact.casefold()
    return _ARTICLE_COLOR_CANONICAL.get(key,compact)



def article_filter_facets(record):
    """Returnér ensartede, brugerrettede facetter til artikelbrowseren.

    De indbyggede poster kan have eksplicitte facetter. For ældre poster og
    brugerartikler udledes de så vidt muligt fra serie/kategori/beskrivelse.
    """
    r=dict(record or {})
    desc=str(r.get("description","") or "")
    cat=str(r.get("category","") or "")
    series=str(r.get("series","") or "")
    hay=f"{desc} {cat} {series}".casefold()

    product_type=str(r.get("product_type","") or "").strip()
    if not product_type:
        if str(r.get("kind","")).casefold()=="cable": product_type="Kabel"
        elif "teknisk" in hay and "ramme" in hay: product_type="Teknisk monteringsramme"
        elif "forfradåse" in hay or "forfra dåse" in hay: product_type="Forfradåse"
        elif "indmur" in hay and "dåse" in hay: product_type="Indmuringsdåse"
        elif "indstøb" in hay and "dåse" in hay: product_type="Indstøbningsdåse"
        elif "dåse" in hay: product_type="Dåse"
        elif "ramme" in hay: product_type="Ramme"
        elif "stikkontakt" in hay or "udtag" in hay: product_type="Stikkontakt / udtag"
        elif "tangent" in hay or "afdæk" in hay or "dækplade" in hay: product_type="Tangent / afdækning"
        elif "afbryder" in hay or "tryk" in hay or "lysdæmper" in hay: product_type="Afbryder / betjening"
        elif "wiser" in hay: product_type="Wiser"
        else: product_type="Øvrigt"

    design=str(r.get("design_family","") or "").strip()
    if not design:
        if "slim" in hay: design="SLIM"
        elif "baseline 63" in hay: design="BASELINE 63"
        elif "base 63" in hay: design="BASE 63"
        elif "softline 63" in hay: design="SOFTLINE 63"
        elif "choice" in hay: design="CHOICE"
        elif "pure" in hay: design="PURE"
        elif re.search(r"\bsoft\b",hay): design="SOFT"
        elif "wiser" in hay: design="Wiser"
        elif "air" in hay: design="AIR"
        elif "wask" in str(r.get("manufacturer","")).casefold(): design="Installationskabel"
        elif "fuga" in hay: design="FUGA"
        else: design=""

    raw_module=str(r.get("module_size","") or "").strip()
    module=normalize_article_module(raw_module) if raw_module else ""
    if not module and not raw_module and str(r.get("kind","") or "").casefold()!="cable":
        module=_module_label(desc)

    color=normalize_article_color(r.get("color",""))
    if not color:
        # Fallback fra tekst er konservativ og bevarer producentens farvebegreb.
        # Fx er "Antracit" ikke automatisk det samme som LK's "Koksgrå".
        for needle,label in (
            ("koksgrå","Koksgrå"),("lysegrå","Lysegrå"),("hvid","Hvid"),
            ("stålmetallic","Stålmetallic"),("antracit","Antracit"),("stål","Stål"),
            ("sort","Sort"),("petroleum","Petroleum"),("rød","Rød"),
        ):
            if needle in hay:
                color=label; break

    mounting=str(r.get("mounting_type","") or "").strip()
    if not mounting:
        if product_type in ("Forfradåse","Indmuringsdåse","Indstøbningsdåse","Dåse"):
            mounting=product_type
        elif product_type=="Teknisk monteringsramme": mounting="Teknisk ramme"
        elif product_type=="Ramme": mounting="Design-/dækramme"
        else: mounting=""

    semantic_input=dict(r)
    semantic_input["product_type"]=product_type
    semantics=article_intelligence.derive_product_semantics(semantic_input)
    product_family=str(semantics.get("product_family","") or "").strip()
    product_variant=str(semantics.get("product_variant","") or "").strip()
    # The old Design field is retained only as a compatibility/backward-facing
    # facet. Boxes now use Family + Variant; their compatible frame designs must
    # never appear as the box's own design.
    if "dåse" in product_type.casefold():
        design=""
    return {"product_type":product_type,"design_family":design,"product_family":product_family,"product_variant":product_variant,"module_size":module,"module_group":_module_group_label(module),"color":color,"mounting_type":mounting}


def normalize_article_catalog(records):
    """Normalisér et artikelbibliotek uden at miste producentmetadata.

    Artikelnummeret er den stabile nøgle.  Ud over de oprindelige felter
    bevares metadata fra det indbyggede standardbibliotek (serie, kategori,
    EL-nummer, EAN, status og kabeldata), så en artikel kan kopieres ind i et
    projekt og fortsat være fuldt selvbeskrivende.
    """
    out=[]; seen=set()
    for raw in records or []:
        if not isinstance(raw,dict):
            continue
        article_no=str(raw.get("article_no", "") or "").strip()
        key=article_no.casefold()
        if not article_no or key in seen:
            continue
        seen.add(key)
        unit=str(raw.get("unit", "stk") or "stk").strip() or "stk"
        item={
            "article_no":article_no,
            "description":str(raw.get("description", "") or "").strip(),
            "manufacturer":str(raw.get("manufacturer", "") or "").strip(),
            "unit":unit,
            "note":str(raw.get("note", "") or "").strip(),
        }
        facets=article_filter_facets(raw)
        for field_name in ARTICLE_METADATA_FIELDS:
            value=str(raw.get(field_name, "") or "").strip()
            if not value and field_name in facets:
                value=str(facets.get(field_name,"") or "").strip()
            if value:
                item[field_name]=value
        # Structured metadata is deliberately kept outside the legacy string
        # field loop.  It is JSON-safe and lets the article model grow without
        # flattening relation/specification data into opaque prose.
        for field_name in ARTICLE_STRUCTURED_FIELDS:
            value=raw.get(field_name)
            if isinstance(value,dict) and value:
                if field_name in {"compatibility","semantic_evidence"}:
                    # Semantic structures contain nested lists/dicts (e.g.
                    # compatible design series plus provenance per dimension).
                    # Preserve their shape instead of flattening them to repr strings.
                    item[field_name]=json.loads(json.dumps(value,ensure_ascii=False))
                else:
                    item[field_name]={str(k):str(v) for k,v in value.items() if str(k).strip() and str(v).strip()}
            elif isinstance(value,(list,tuple)) and value:
                item[field_name]=json.loads(json.dumps(value,ensure_ascii=False))
        # LK's eget katalog har produktfotos på en stabil varenummerbaseret URL.
        # Brug den direkte kilde som lazy preview (med eksisterende disk-cache),
        # så artikelvælgeren ikke skal hente og parse en hel produktside først.
        lk_hay=" ".join(str(raw.get(k,"") or "") for k in ("description","manufacturer","series","category","source","product_page")).casefold()
        lk_article=bool(re.fullmatch(r"[0-9a-z_-]+",article_no,re.I)) and ("lk fuga" in lk_hay or "lk.dk" in lk_hay or "lauritz knudsen" in lk_hay)
        if lk_article and not str(item.get("image_url","") or "").strip():
            item["image_url"]=f"https://www1.lk.dk/katalog/foto/jpg/{article_no}.jpg"
            item.setdefault("image_source","LK / Schneider Electric")
        if lk_article and not str(item.get("product_page","") or "").strip():
            item["product_page"]=f"https://www.lk.dk/produkter/{article_no}"
        if "package_length_m" in raw:
            try:
                package_length=float(raw.get("package_length_m",0.0) or 0.0)
            except (TypeError,ValueError):
                package_length=0.0
            if math.isfinite(package_length) and package_length >= 0:
                item["package_length_m"]=package_length
        packaging=article_packaging(raw)
        item["consumption_unit"]=packaging["consumption_unit"]
        item["sales_unit"]=packaging["sales_unit"]
        item["sales_package_quantity"]=packaging["sales_package_quantity"]
        item["minimum_order_quantity"]=packaging["minimum_order_quantity"]
        if packaging["package_label"]:
            item["package_label"]=packaging["package_label"]
        # Prisdata fra producent-/importkilder behandles som metadata.  Den
        # separate brugerprisbog lægges ovenpå i UI/BOM, så manuelle priser
        # aldrig kan blive overskrevet af en katalogsynkronisering.
        for price_field in ("estimated_price", "manual_price", "effective_price", "unit_price", "estimated_price_min", "estimated_price_max"):
            if price_field not in raw or str(raw.get(price_field, "")).strip() == "":
                continue
            try:
                price_value=float(raw.get(price_field))
            except (TypeError,ValueError):
                price_value=None
            if price_value is not None and math.isfinite(price_value) and price_value >= 0:
                item[price_field]=price_value
                item.setdefault("price_currency", str(raw.get("price_currency", "DKK") or "DKK").strip().upper() or "DKK")
        if str(raw.get("estimated_price_sources", "") or "").strip():
            try:
                source_count=int(raw.get("estimated_price_sources"))
            except (TypeError,ValueError):
                source_count=0
            if source_count > 0:
                item["estimated_price_sources"]=source_count
        out.append(item)
    # Controlled taxonomy, technical properties, variants and normalised
    # relation data are derived with whole-catalogue context. Source category,
    # description and manufacturer wording remain untouched.
    return article_intelligence.enrich_catalog(out)


@lru_cache(maxsize=1)
def _predefined_article_catalog_cached():
    """Læs programmets indbyggede standardbibliotek én gang.

    Der ligger både en JSON-fil til manuel inspektion/opdatering og en Python-
    fallback, så biblioteket også virker i en pakket Windows-build hvor en
    separat datafil ikke nødvendigvis følger automatisk med.
    """
    records=[]
    try:
        data_path=Path(__file__).parents[2] / "predefined_articles.json"
        payload=json.loads(data_path.read_text(encoding="utf-8"))
        records=payload.get("articles",[]) if isinstance(payload,dict) else []
    except Exception:
        try:
            from predefined_articles_data import ARTICLES as records
        except Exception:
            records=[]
    return tuple(tuple(sorted(item.items())) for item in normalize_article_catalog(records))


def load_predefined_article_catalog():
    """Returnér en mutérbar kopi af LK FUGA/Wiser/Waskönig+Walter-biblioteket."""
    return [dict(items) for items in _predefined_article_catalog_cached()]


def normalize_cable_article_bindings(data):
    """Normalisér kabeltype/specifikation -> artikelnummer."""
    if not isinstance(data,dict):
        return {}
    out={}
    for raw_key,raw_article in data.items():
        key=str(raw_key or "").strip()
        article_no=str(raw_article or "").strip()
        if key and article_no:
            out[key]=article_no
    return out


def cable_article_key(layer: str, cable_spec: str) -> str:
    return f"{str(layer or CABLE_LAYER).strip()}|{str(cable_spec or '').strip()}"


def cable_article_key_parts(key: str) -> tuple[str,str]:
    text=str(key or "")
    if "|" in text:
        layer,spec=text.split("|",1)
        return layer or CABLE_LAYER,spec
    return CABLE_LAYER,text


def cable_type_display(layer: str) -> str:
    reverse={value:name for name,value in CABLE_TYPES.items()}
    return reverse.get(str(layer or ""),str(layer or "Kabel"))
