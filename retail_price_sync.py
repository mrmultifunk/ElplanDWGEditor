from __future__ import annotations

"""Skånsom multi-source prisopdatering for offentlige danske webshops.

0.59.25 holder webshop-observationer adskilt fra den effektive pris. Offentlige
forbrugerpriser antages at være inkl. dansk moms og omregnes til ekskl. moms,
så de passer til Elplans eksisterende BOM-prismodel. Kun sider med et sikkert
identitetsmatch (EAN, EL-nr. eller producentens artikelnummer) accepteres.
"""

import html as html_lib
import json
import math
import random
import re
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

from storage_utils import atomic_write_json, read_json

CACHE_VERSION = 3
PRICE_NORMALIZATION_VERSION = 3
DEFAULT_VAT_RATE = 0.25
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 ElplanDWGEditor/0.59.76"


@dataclass(frozen=True)
class ProviderConfig:
    key: str
    name: str
    base_url: str
    search_templates: tuple[str, ...]


PROVIDERS: tuple[ProviderConfig, ...] = (
    ProviderConfig(
        "wattoo", "WATTOO", "https://www.wattoo.dk",
        ("/search?query={q}", "/search?q={q}", "/?q={q}", "/?search={q}"),
    ),
    ProviderConfig(
        "lavprisel", "LavprisEL", "https://www.lavprisel.dk",
        ("/search?query={q}", "/search?q={q}", "/search/?q={q}", "/?q={q}"),
    ),
    ProviderConfig(
        "greenline", "Greenline", "https://www.greenline.dk",
        ("/search?query={q}", "/search?q={q}", "/search/?q={q}", "/?q={q}"),
    ),
)


@dataclass
class PriceObservation:
    provider: str
    provider_key: str
    price_incl_vat: float
    price_excl_vat: float
    currency: str
    price_unit: str
    url: str
    matched_by: str
    matched_value: str
    checked: str
    confidence: str = "Høj"
    vat_rate: float = DEFAULT_VAT_RATE
    raw_price_incl_vat: float | None = None
    raw_price_excl_vat: float | None = None
    package_quantity: float = 1.0
    package_label: str = ""
    normalization_version: int = PRICE_NORMALIZATION_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PriceSyncStats:
    articles_total: int = 0
    articles_with_observations: int = 0
    estimates_updated: int = 0
    cache_hits: int = 0
    network_requests: int = 0
    provider_errors: int = 0
    rate_limit_events: int = 0
    backoff_wait_seconds: float = 0.0
    cancelled: bool = False


@dataclass
class PriceSyncResult:
    records: dict[str, dict]
    stats: PriceSyncStats


class PriceSyncError(RuntimeError):
    pass


class PriceSyncCancelled(PriceSyncError):
    pass


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _compact(value) -> str:
    return re.sub(r"[^0-9a-z]", "", str(value or "").casefold())


def _valid_amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 < number < 10_000_000 else None


def _parse_decimal(value: str):
    s = str(value or "").strip().replace("\xa0", " ")
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        return None
    # Dansk: 1.234,50. Internationalt schema.org: 1234.50.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return _valid_amount(float(s))
    except ValueError:
        return None


def _normalise_unit(value: str, fallback: str = "stk") -> str:
    text = str(value or "").casefold().strip()
    if re.search(r"\b(m|meter|metre)\b", text):
        return "m"
    if "rulle" in text:
        return "rulle"
    if "pakke" in text or "pakning" in text:
        return "pakke"
    if "sæt" in text or "saet" in text:
        return "sæt"
    if "stk" in text or "piece" in text or "each" in text:
        return "stk"
    return str(fallback or "stk").strip() or "stk"



def _package_quantity_from_page(page_text: str, url: str = "", *, title_text: str = "",
                                product_text: str = "") -> tuple[float | None, str, bool]:
    """Find salgs-pakningens antal styk uden at forveksle antal poler/huller.

    Returnerer ``(antal, label, ambiguous)``. URL'ens *sidste* ``N-stk`` har
    højeste prioritet, fordi WATTOO fx kan have både ``2-stk-huller`` og
    ``10-stk`` i samme URL. Fritekst accepteres kun fra tydelige
    pakningsfraser; flere forskellige antal uden en entydig titel/URL afvises.
    """
    url_values=[]
    for m in re.finditer(r"(?:^|[-_/])(\d{1,5})-stk(?:[-_/]|$)", str(url or "").casefold()):
        try:
            value=int(m.group(1))
        except ValueError:
            continue
        if 1 < value <= 100000:
            url_values.append(value)
    if url_values:
        value=float(url_values[-1])
        return value, f"pakke á {int(value)} stk.", False

    def candidates(text: str, *, allow_plain: bool = False) -> list[int]:
        low=html_lib.unescape(str(text or "")).casefold().replace("á","a")
        pats=(
            r"(?:blisterpakke|pakke|pakning|forpakning|æske|karton|pack(?:age)?|box)\s*(?:a|med|på|af|of|contains?)?\s*(\d{1,5})\s*(?:stk\.?|pcs?\.?|pieces?)",
            r"(\d{1,5})\s*(?:stk\.?|pcs?\.?|pieces?)[^\n|·]{0,45}(?:gør-det-selv\s*)?(?:blister)?(?:pakke|pakning|forpakning|æske|karton|pack(?:age)?|box)",
            r"du\s+får\s+her\s+(\d{1,5})\s*(?:stk\.?|pcs?\.?|pieces?)",
            r"(?:packaging\s+unit|package\s+quantity|pack\s+size|forpakningsstørrelse)\s*:?\s*(\d{1,5})",
        )
        values=[]
        # WAGO angiver ofte hovedpakning og underpakning som fx
        # ``PU (SPU): 1000 (100) Piece``. Webshops handler normalt den mindre
        # underpakning, så tallet i parentes er det relevante stykantal.
        for m in re.finditer(r"\bpu\s*\(\s*spu\s*\)\s*:?\s*\d{1,6}\s*\(\s*(\d{1,5})\s*\)\s*(?:pieces?|pcs?|stk\.?)",low,re.I):
            try: value=int(m.group(1))
            except ValueError: continue
            if 1 < value <= 100000: values.append(value)
        for pat in pats:
            for m in re.finditer(pat, low, re.I):
                try: value=int(m.group(1))
                except ValueError: continue
                if 1 < value <= 100000: values.append(value)
        if allow_plain:
            for m in re.finditer(r"(?<!\d)(\d{1,5})\s*(?:stk\.?|pcs?\.?|pieces?)\b",low,re.I):
                try: value=int(m.group(1))
                except ValueError: continue
                if 1 < value <= 100000: values.append(value)
        return values

    title_values=candidates(title_text,allow_plain=True)
    if title_values and len(set(title_values)) == 1:
        value=float(title_values[0])
        return value, f"pakke á {int(value)} stk.", False

    product_values=candidates(product_text,allow_plain=True)
    if product_values and len(set(product_values)) == 1:
        value=float(product_values[0])
        return value, f"pakke á {int(value)} stk.", False
    if len(set(product_values)) > 1:
        return None, "flere pakningsstørrelser i produktdata", True

    values=candidates(page_text)
    unique=sorted(set(values))
    if len(unique) == 1:
        value=float(unique[0])
        return value, f"pakke á {int(value)} stk.", False
    if len(unique) > 1:
        return None, "flere pakningsstørrelser på siden", True
    return 1.0, "", False


def _normalise_observed_price(raw_price_incl_vat: float, *, vat_rate: float, article_unit: str,
                              observed_unit: str, page_text: str, url: str, title_text: str = "",
                              product_text: str = "", article: dict | None = None):
    """Normalisér webshopprisen til artikelens BOM-enhed.

    Webshops skriver ofte ``pr. stk.`` om *én salgsæske*. For artikler der i
    Elplan forbruges pr. fysisk stk. divideres pakkens pris derfor med antal
    dele. Er siden tydeligt en variant-/pakningsside men antallet tvetydigt,
    afvises observationen frem for at gemme en farlig stykpris.
    """
    raw=_valid_amount(raw_price_incl_vat)
    if raw is None:
        return None
    wanted=_normalise_unit(article_unit, article_unit or "stk")
    seen=_normalise_unit(observed_unit, wanted)
    quantity,label,ambiguous=_package_quantity_from_page(
        page_text,url,title_text=title_text,product_text=product_text,
    )
    context_low=html_lib.unescape(" ".join((str(page_text or ""),str(title_text or ""),str(product_text or "")))).casefold()
    has_pack_signal=(seen == "pakke" or bool(re.search(
        r"\b(?:pakke|pakning|forpakning|blisterpakke|æske|karton|packaging\s+unit|pack\s+of|package\s+quantity|pack\s+size|pu\s*\(\s*spu\s*\))\b",
        context_low,re.I,
    )))
    article=dict(article or {})
    known_quantity=_valid_amount(article.get("sales_package_quantity"))
    maker=str(article.get("manufacturer","") or "").casefold()
    product_type=str(article.get("product_type","") or "").casefold()
    article_no=str(article.get("article_no","") or "")
    is_wago_connector=("wago" in maker and ("samlemuffe" in product_type or re.match(r"^(?:221|2273)-",article_no)))
    if wanted == "stk":
        if ambiguous:
            return None
        qty=float(quantity or 1.0)
        if qty <= 1.0 and known_quantity and known_quantity > 1.0:
            # Nogle grossistsider kalder hele salgsæsken "1 stk.". Brug den
            # dokumenterede underpakning, når siden dog siger pakke/æske. For
            # WAGO-samlemuffer bruges samme fallback ved en tydelig urealistisk
            # høj råpris; en normal enkeltstykpris bliver aldrig divideret.
            candidate=raw/known_quantity
            if has_pack_signal or (is_wago_connector and raw >= 50.0 and 0.05 <= candidate <= 50.0):
                qty=float(known_quantity)
                label=f"pakke á {int(qty) if qty.is_integer() else qty:g} stk. (artikeldata)"
        if qty <= 0:
            return None
        unit_incl=raw/qty
        unit_excl=unit_incl/(1.0+vat_rate)
        return {
            "price_incl_vat":round(unit_incl,4), "price_excl_vat":round(unit_excl,4),
            "price_unit":"stk", "raw_price_incl_vat":round(raw,4),
            "raw_price_excl_vat":round(raw/(1.0+vat_rate),4),
            "package_quantity":qty, "package_label":label,
        }
    # Meterpris må ikke udledes fra en styk-/pakkepris.
    if wanted == "m" and seen not in {"m"}:
        return None
    # For artikler der selv købes som pakke/rulle/sæt er webshopprisen allerede
    # pr. BOM-enhed; pakningsantal gemmes kun som provenance.
    return {
        "price_incl_vat":round(raw,4), "price_excl_vat":round(raw/(1.0+vat_rate),4),
        "price_unit":wanted, "raw_price_incl_vat":round(raw,4),
        "raw_price_excl_vat":round(raw/(1.0+vat_rate),4),
        "package_quantity":float(quantity or 1.0), "package_label":label,
    }


def article_identifiers(article: dict) -> list[tuple[str, str]]:
    """Identiteter i sikker prioritet: EAN -> EL-nr. -> producentnr."""
    art = dict(article or {})
    out: list[tuple[str, str]] = []
    ean = _digits(art.get("ean"))
    if len(ean) >= 8:
        out.append(("EAN", ean))
    el_no = _digits(art.get("el_no"))
    if len(el_no) >= 6 and ("EAN", el_no) not in out:
        out.append(("EL-nr.", el_no))
    article_no = str(art.get("article_no", "") or "").strip()
    if article_no:
        out.append(("Artikelnummer", article_no))
    return out


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._anchor_href = ""
        self._anchor_text: list[str] = []
        self._in_ld = False
        self._ld_buf: list[str] = []
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        data = {str(k).casefold(): str(v or "") for k, v in attrs}
        tag = tag.casefold()
        if tag == "a":
            self._anchor_href = data.get("href", "")
            self._anchor_text = []
        elif tag == "meta":
            key = (data.get("property") or data.get("name") or data.get("itemprop") or "").casefold()
            if key and data.get("content"):
                self.meta[key] = data["content"]
        elif tag == "script" and "ld+json" in data.get("type", "").casefold():
            self._in_ld = True
            self._ld_buf = []
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag == "a" and self._anchor_href:
            self.links.append((self._anchor_href, " ".join(self._anchor_text).strip()))
            self._anchor_href = ""
            self._anchor_text = []
        elif tag == "script" and self._in_ld:
            self.json_ld.append("".join(self._ld_buf))
            self._in_ld = False
            self._ld_buf = []
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)
        else:
            text = str(data or "").strip()
            if text:
                if self._in_title:
                    self.title_parts.append(text)
                self.text_parts.append(text)
                if self._anchor_href:
                    self._anchor_text.append(text)


@dataclass
class ParsedProduct:
    price_incl_vat: float
    currency: str
    unit: str
    identifiers: dict[str, set[str]]
    context: str = ""


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _json_product_candidates(parser: _PageParser, fallback_unit: str) -> list[ParsedProduct]:
    out: list[ParsedProduct] = []
    for raw in parser.json_ld:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for obj in _walk_json(data):
            typ = obj.get("@type", "")
            types = [str(x).casefold() for x in (typ if isinstance(typ, list) else [typ])]
            if not any("product" in t for t in types):
                continue
            ids = {"ean": set(), "el": set(), "article": set()}
            for key in ("gtin13", "gtin", "gtin12", "gtin14", "ean"):
                val = _digits(obj.get(key))
                if val: ids["ean"].add(val)
            for key in ("sku", "mpn", "productID", "productId"):
                val = str(obj.get(key, "") or "").strip()
                if val:
                    ids["article"].add(_compact(val)); ids["el"].add(_digits(val))
            offers = obj.get("offers", {})
            offer_rows = offers if isinstance(offers, list) else [offers]
            for offer in offer_rows:
                if not isinstance(offer, dict):
                    continue
                price = _parse_decimal(str(offer.get("price", "") or offer.get("lowPrice", "") or ""))
                if price is None:
                    spec = offer.get("priceSpecification", {})
                    if isinstance(spec, dict):
                        price = _parse_decimal(str(spec.get("price", "") or ""))
                if price is None:
                    continue
                currency = str(offer.get("priceCurrency", "DKK") or "DKK").upper()
                unit = _normalise_unit(str(offer.get("unitText", "") or offer.get("unitCode", "")), fallback_unit)
                context_parts=[]
                for source in (obj,offer):
                    for key in ("name","description","size","url","sku","mpn","unitText","unitCode","packageQuantity","packSize"):
                        value=source.get(key)
                        if value is not None and not isinstance(value,(dict,list)):
                            context_parts.append(str(value))
                # Feltseparatoren forhindrer fx SKU ``221-412`` efterfulgt af
                # et separat ``unitText=stk`` i at blive læst som 412 stk.
                out.append(ParsedProduct(price, currency, unit, ids, " | ".join(context_parts)))
    return out


def _identity_match(article: dict, ids: dict[str, set[str]], page_text: str) -> tuple[str, str] | None:
    ean = _digits(article.get("ean"))
    el_no = _digits(article.get("el_no"))
    article_no = str(article.get("article_no", "") or "").strip()
    compact_text = _compact(page_text)
    digit_text = _digits(page_text)
    if ean and (ean in ids.get("ean", set()) or ean in digit_text):
        return "EAN", ean
    if el_no and (el_no in ids.get("el", set()) or el_no in digit_text):
        return "EL-nr.", el_no
    if article_no and (_compact(article_no) in ids.get("article", set()) or _compact(article_no) in compact_text):
        return "Artikelnummer", article_no
    return None


def parse_product_page(html: str, article: dict, *, provider: ProviderConfig, url: str, vat_rate: float = DEFAULT_VAT_RATE) -> PriceObservation | None:
    """Parse en webshopside og normalisér salgs-pakninger til BOM-enhed."""
    parser = _PageParser()
    try:
        parser.feed(str(html or ""))
    except Exception:
        pass
    page_text = html_lib.unescape(" ".join(parser.text_parts))
    fallback_unit = str(article.get("unit", "stk") or "stk")
    title_text=" ".join([
        *(str(parser.meta.get(k,"") or "") for k in ("og:title","twitter:title","title")),
        *parser.title_parts,
    ]).strip()

    def make_observation(raw_price, currency, observed_unit, match, confidence, product_text=""):
        if str(currency or "DKK").upper() != "DKK":
            return None
        normalized=_normalise_observed_price(
            raw_price, vat_rate=vat_rate, article_unit=fallback_unit,
            observed_unit=observed_unit, page_text=page_text, url=url, title_text=title_text,
            product_text=product_text,article=article,
        )
        if not normalized:
            return None
        return PriceObservation(
            provider=provider.name, provider_key=provider.key,
            price_incl_vat=normalized["price_incl_vat"], price_excl_vat=normalized["price_excl_vat"],
            currency="DKK", price_unit=normalized["price_unit"], url=url,
            matched_by=match[0], matched_value=match[1], checked=date.today().isoformat(),
            confidence=confidence, vat_rate=vat_rate,
            raw_price_incl_vat=normalized["raw_price_incl_vat"], raw_price_excl_vat=normalized["raw_price_excl_vat"],
            package_quantity=normalized["package_quantity"], package_label=normalized["package_label"],
        )

    candidates = _json_product_candidates(parser, fallback_unit)
    for product in candidates:
        match = _identity_match(article, product.identifiers, page_text)
        if not match:
            continue
        obs=make_observation(product.price_incl_vat, product.currency, product.unit, match, "Høj",product.context)
        if obs:
            return obs

    # OpenGraph/schema-meta fallback. Kræver stadig identitetsmatch i siden.
    ids = {"ean": set(), "el": set(), "article": set()}
    match = _identity_match(article, ids, page_text)
    if not match:
        return None
    # Fritekst/meta er kun fallback. Hvis siden tydeligt indeholder flere EAN-
    # varianter, kan en synlig pris tilhøre en anden variant; afvis derfor den
    # usikre fallback og kræv struktureret JSON-LD for sådanne sider.
    page_eans=set(re.findall(r"(?<!\d)\d{13}(?!\d)", page_text))
    target_ean=_digits(article.get("ean"))
    if target_ean and len(page_eans)>1:
        return None
    meta_price = None
    for key in ("product:price:amount", "og:price:amount", "price"):
        if key in parser.meta:
            meta_price = _parse_decimal(parser.meta[key])
            if meta_price is not None:
                break
    currency = str(parser.meta.get("product:price:currency", parser.meta.get("pricecurrency", "DKK")) or "DKK").upper()
    if meta_price is not None and currency == "DKK":
        obs=make_observation(meta_price,currency,_normalise_unit(page_text,fallback_unit),match,"Middel")
        if obs:
            return obs

    # Sidste fallback: find priser tæt på "inkl. moms" / "pr. stk.". Undgå
    # fragtpriser ved kun at bruge den lokale kontekst omkring pris-markører.
    price_patterns = (
        r"(?:pr\.?\s*(?:stk\.?|meter|m)\s*[|·-]?\s*)?(?:inkl\.?\s*moms\s*)?(?:nu\s*)?([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?)\s*(?:kr\.?|,-)",
        r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*kr\.?",
    )
    lowered = page_text.casefold()
    for pattern in price_patterns:
        for m in re.finditer(pattern, lowered, re.I):
            context = lowered[max(0,m.start()-80):m.end()+80]
            if any(bad in context for bad in ("fragt", "pakkeshop", "hjemmelever", "click&collect", "levering")):
                continue
            price = _parse_decimal(m.group(1))
            if price is None:
                continue
            obs=make_observation(price,"DKK",_normalise_unit(context,fallback_unit),match,"Middel")
            if obs:
                return obs
    return None


def _same_domain(url: str, provider: ProviderConfig) -> bool:
    try:
        host = urlparse(url).netloc.casefold().removeprefix("www.")
        base = urlparse(provider.base_url).netloc.casefold().removeprefix("www.")
        return host == base
    except Exception:
        return False


def _candidate_links(html: str, page_url: str, provider: ProviderConfig, article: dict, limit: int = 5) -> list[str]:
    parser = _PageParser()
    try: parser.feed(str(html or ""))
    except Exception: pass
    desc_tokens=[t for t in re.findall(r"[0-9a-zæøå]+", str(article.get("description","") or "").casefold()) if len(t)>=4][:8]
    identifiers=[_compact(v) for _,v in article_identifiers(article)]
    scored=[]
    seen=set()
    for href,text in parser.links:
        url=urljoin(page_url,href)
        if url in seen or not _same_domain(url,provider): continue
        seen.add(url)
        low=(url+" "+text).casefold(); compact=_compact(low)
        score=0
        if any(i and i in compact for i in identifiers): score+=100
        score+=sum(4 for t in desc_tokens if t in low)
        if any(x in low for x in ("produkt","fuga","kabel","afbryder","stikkontakt","daase","dåse")): score+=2
        if any(x in low for x in ("account","login","contact","kundeservice","kurv","cart","brand","maerker","mærker")): score-=30
        if score>0: scored.append((score,url))
    scored.sort(key=lambda x:(-x[0],x[1]))
    return [u for _,u in scored[:limit]]


def estimate_from_observations(observations: Iterable[dict], *, article_unit: str = "stk") -> dict:
    """Robust estimat: 3+ median, 2 gennemsnit, 1 enkeltkilde/lav sikkerhed."""
    rows=[]
    wanted_unit=_normalise_unit(article_unit,article_unit)
    by_provider={}
    for raw in observations or []:
        if not isinstance(raw,dict): continue
        price=_valid_amount(raw.get("price_excl_vat"))
        if price is None or str(raw.get("currency","DKK") or "DKK").upper()!="DKK": continue
        unit=_normalise_unit(raw.get("price_unit",""),wanted_unit)
        # Undgå at blande meterpris og stykspris. Ukendt/almindelig leveringsenhed
        # accepteres mod artikelens egen enhed.
        if {unit,wanted_unit} == {"m","stk"}: continue
        key=str(raw.get("provider_key",raw.get("provider","")) or "").casefold()
        if key: by_provider[key]=dict(raw)
    rows=list(by_provider.values())
    if not rows:return {}
    prices=[float(r["price_excl_vat"]) for r in rows]
    if len(prices)>=3: estimate=float(statistics.median(prices)); confidence="Høj"; method="Median"
    elif len(prices)==2: estimate=sum(prices)/2.0; confidence="Middel"; method="Gennemsnit"
    else: estimate=prices[0]; confidence="Lav"; method="Enkelt kilde"
    checked=max((str(r.get("checked","") or "") for r in rows),default=date.today().isoformat()) or date.today().isoformat()
    providers=[str(r.get("provider","") or "") for r in rows]
    return {
        "estimated_price": round(estimate, 4),
        "estimated_price_source": "Webshops: " + " + ".join(providers),
        "estimated_price_checked": checked,
        "estimated_price_confidence": confidence,
        "estimated_price_method": method,
        "estimated_price_sources": len(rows),
        "estimated_price_min": round(min(prices),4),
        "estimated_price_max": round(max(prices),4),
        "price_currency": "DKK",
        "price_unit": wanted_unit,
        "price_observations": rows,
    }


class RetailPriceCollector:
    def __init__(self, *, cache_path: Path, request_delay_min: float = 1.0, request_delay_max: float = 1.8,
                 cache_max_age_hours: float = 24.0, timeout: float = 10.0,
                 backoff_seconds=(5.0,15.0,45.0), opener=None, sleep=None):
        self.cache_path=Path(cache_path)
        self.request_delay_min=float(request_delay_min); self.request_delay_max=float(request_delay_max)
        self.cache_max_age_hours=float(cache_max_age_hours); self.timeout=float(timeout)
        self.backoff_seconds=tuple(float(x) for x in backoff_seconds)
        self.opener=opener or urlopen; self.sleep=sleep or time.sleep
        self.stats=PriceSyncStats()
        raw=read_json(self.cache_path,{}) if self.cache_path.is_file() else {}
        if not isinstance(raw,dict) or int(raw.get("version",0) or 0)!=CACHE_VERSION: raw={}
        self.cache={"version":CACHE_VERSION,"providers":dict(raw.get("providers",{}) or {}),"observations":dict(raw.get("observations",{}) or {})}
        self._last_request=0.0

    def _save_cache(self):
        try: atomic_write_json(self.cache_path,self.cache)
        except Exception: pass

    def _cancel_check(self,cancel):
        if cancel and cancel(): self.stats.cancelled=True; raise PriceSyncCancelled("Prisopdateringen blev annulleret.")

    def _pace(self,cancel):
        if self._last_request:
            target=random.uniform(self.request_delay_min,self.request_delay_max)
            elapsed=time.monotonic()-self._last_request
            remaining=max(0.0,target-elapsed)
            if remaining:
                # korte bidder gør Annuller responsiv
                until=time.monotonic()+remaining
                while time.monotonic()<until:
                    self._cancel_check(cancel); self.sleep(min(0.15,max(0.0,until-time.monotonic())))

    def _fetch(self,url,*,cancel=None):
        attempts=max(1,len(self.backoff_seconds)+1)
        last_exc=None
        for attempt in range(attempts):
            self._cancel_check(cancel); self._pace(cancel)
            req=Request(url,headers={"User-Agent":USER_AGENT,"Accept-Language":"da-DK,da;q=0.9,en;q=0.7","Accept":"text/html,application/xhtml+xml"})
            try:
                self.stats.network_requests+=1
                with self.opener(req,timeout=self.timeout) as response:
                    final_url=getattr(response,"geturl",lambda:url)()
                    data=response.read(2_500_000)
                    charset="utf-8"
                    try: charset=response.headers.get_content_charset() or "utf-8"
                    except Exception: pass
                    self._last_request=time.monotonic()
                    return data.decode(charset,"replace"),final_url
            except HTTPError as exc:
                self._last_request=time.monotonic(); last_exc=exc
                if exc.code not in (403,429,500,502,503,504): raise
                self.stats.rate_limit_events += int(exc.code in (403,429))
            except (URLError,TimeoutError,OSError) as exc:
                self._last_request=time.monotonic(); last_exc=exc
            if attempt>=len(self.backoff_seconds): break
            wait=self.backoff_seconds[attempt]; self.stats.backoff_wait_seconds+=wait
            until=time.monotonic()+wait
            while time.monotonic()<until:
                self._cancel_check(cancel); self.sleep(min(0.2,max(0.0,until-time.monotonic())))
        raise PriceSyncError(f"Kunne ikke hente {url}: {last_exc}")

    def _cache_key(self,article,provider):
        ids=article_identifiers(article)
        stable=ids[0][1] if ids else str(article.get("article_no","") or "")
        return f"{provider.key}:{stable}"

    def _cached_observation(self,article,provider):
        raw=self.cache["observations"].get(self._cache_key(article,provider))
        if not isinstance(raw,dict): return None
        checked=str(raw.get("checked","") or "")
        try: when=datetime.fromisoformat(checked).replace(tzinfo=timezone.utc) if "T" not in checked else datetime.fromisoformat(checked)
        except Exception:
            try: when=datetime.combine(date.fromisoformat(checked),datetime.min.time(),tzinfo=timezone.utc)
            except Exception:return None
        now=datetime.now(timezone.utc)
        if when.tzinfo is None: when=when.replace(tzinfo=timezone.utc)
        if now-when > timedelta(hours=self.cache_max_age_hours): return None
        return raw

    def _store_observation(self,article,provider,obs):
        row=dict(obs); row["cached_at"]=datetime.now(timezone.utc).isoformat()
        self.cache["observations"][self._cache_key(article,provider)]=row; self._save_cache()

    def _known_urls(self,article,provider):
        urls=[]
        for value in (article.get("supplier_page",""),article.get("product_page","")):
            url=str(value or "").strip()
            if url and _same_domain(url,provider): urls.append(url)
        old=self.cache["observations"].get(self._cache_key(article,provider),{})
        url=str(old.get("url","") or "") if isinstance(old,dict) else ""
        if url and _same_domain(url,provider):urls.append(url)
        return list(dict.fromkeys(urls))

    def collect_provider(self,article,provider,*,cancel=None):
        cached=self._cached_observation(article,provider)
        if cached:
            self.stats.cache_hits+=1
            if cached.get("no_match"): return None
            return cached
        tried=set()
        # 1) kendt produkt-URL er billigst og mest præcis.
        for url in self._known_urls(article,provider):
            if url in tried:continue
            tried.add(url)
            try: html,final=self._fetch(url,cancel=cancel)
            except PriceSyncCancelled: raise
            except Exception: self.stats.provider_errors+=1; continue
            obs=parse_product_page(html,article,provider=provider,url=final)
            if obs:
                row=obs.to_dict(); self._store_observation(article,provider,row); return row

        ids=article_identifiers(article)
        if not ids:return None
        provider_meta=self.cache["providers"].setdefault(provider.key,{})
        preferred=str(provider_meta.get("search_template","") or "")
        templates=list(provider.search_templates)
        if preferred in templates:templates.remove(preferred); templates.insert(0,preferred)
        # Søg først på stærkeste identitet. Kun ét søgeterm pr. provider for at
        # holde trafikken lav; andre identiteter bruges til validering.
        term=ids[0][1]
        for template in templates:
            search_url=urljoin(provider.base_url,template.format(q=quote_plus(term)))
            if search_url in tried:continue
            tried.add(search_url)
            try: html,final=self._fetch(search_url,cancel=cancel)
            except PriceSyncCancelled: raise
            except Exception: self.stats.provider_errors+=1; continue
            # Nogle shops sender et præcist søg direkte til produktsiden.
            obs=parse_product_page(html,article,provider=provider,url=final)
            if obs:
                provider_meta["search_template"]=template; self._store_observation(article,provider,obs.to_dict()); return obs.to_dict()
            links=_candidate_links(html,final,provider,article,limit=3)
            for url in links:
                if url in tried:continue
                tried.add(url)
                try: product_html,product_url=self._fetch(url,cancel=cancel)
                except PriceSyncCancelled: raise
                except Exception: self.stats.provider_errors+=1; continue
                obs=parse_product_page(product_html,article,provider=provider,url=product_url)
                if obs:
                    provider_meta["search_template"]=template; self._store_observation(article,provider,obs.to_dict()); return obs.to_dict()
            # En 200-side på en egentlig /search-rute er tilstrækkeligt bevis
            # for at ruten findes. Husk den og undgå at probe alternative ruter
            # for hver eneste artikel uden webshopmatch.
            try: search_path=urlparse(final).path.casefold()
            except Exception: search_path=""
            if "search" in search_path:
                provider_meta["search_template"]=template
                break
        negative={"no_match":True,"provider":provider.name,"provider_key":provider.key,"checked":date.today().isoformat()}
        self._store_observation(article,provider,negative)
        return None

    def collect(self,articles: Iterable[dict], *, providers=PROVIDERS, progress: Callable[[str,int,int],None] | None=None, cancel=None) -> PriceSyncResult:
        rows=list(articles or []); self.stats.articles_total=len(rows)
        result={}
        total=max(1,len(rows)*max(1,len(providers))); step=0
        for index,article in enumerate(rows,1):
            self._cancel_check(cancel)
            observations=[]
            for provider in providers:
                step+=1
                if progress: progress(f"Pris {index}/{len(rows)} · {provider.name} · {article.get('article_no','')}",step,total)
                try: obs=self.collect_provider(article,provider,cancel=cancel)
                except PriceSyncCancelled: raise
                except Exception:
                    self.stats.provider_errors+=1; obs=None
                if obs: observations.append(obs)
            estimate=estimate_from_observations(observations,article_unit=str(article.get("unit","stk") or "stk"))
            if estimate:
                self.stats.articles_with_observations+=1; self.stats.estimates_updated+=1
                result[str(article.get("article_no","") or "")]=estimate
        self._save_cache()
        return PriceSyncResult(result,self.stats)
