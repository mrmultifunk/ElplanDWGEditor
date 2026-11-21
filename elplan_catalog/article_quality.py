from __future__ import annotations

"""Non-destructive article catalogue quality audit.

The audit never changes an article.  It reports raw/source inconsistencies and
suggests a future normalised representation, so producer data can be retained
while filter/BOM metadata becomes predictable.
"""

from collections import defaultdict
from datetime import date
import re
from typing import Iterable

from elplan_catalog import article_intelligence
import core_logic as core

SEVERITY_ORDER = {"Fejl": 0, "Advarsel": 1, "Info": 2}


def _text(value) -> str:
    return str(value or "").strip()


def _key(value) -> str:
    text=_text(value).casefold()
    text=re.sub(r"\s*/\s*", " / ", text)
    text=re.sub(r"\s+", " ", text)
    return text.strip(" ·,-")


def canonical_status(value) -> str:
    text=_text(value).casefold()
    if not text:
        return "Ukendt"
    if "udgå" in text or "udgaa" in text:
        return "Udgået"
    if "udfas" in text:
        return "Udfaset"
    if "legacy" in text:
        return "Legacy"
    if "aktiv" in text:
        return "Aktiv"
    return "Ukendt"


def _valid_gtin(value) -> bool:
    s=re.sub(r"\D", "", _text(value))
    if len(s) not in (8, 12, 13, 14):
        return False
    digits=[int(ch) for ch in s]
    check=digits.pop()
    total=sum(d*(3 if (len(digits)-i) % 2 == 1 else 1) for i,d in enumerate(digits))
    return (10-total % 10) % 10 == check


def _issue(severity, category, code, message, *, article=None, field="", value="", suggestion="", count=1, article_list=None):
    article=article or {}
    articles=list(article_list or [])
    return {
        "severity": severity,
        "category": category,
        "code": code,
        "article_no": _text(article.get("article_no")),
        "manufacturer": _text(article.get("manufacturer")),
        "field": field,
        "value": _text(value),
        "message": message,
        "suggestion": suggestion,
        "count": int(count or 1),
        "articles": articles,
    }


def _taxonomy_tokens(value):
    stop={"og", "and", "the", "a", "as", "til", "for"}
    text=_key(value).replace("·", " ").replace("/", " ")
    return {t for t in re.findall(r"[\wæøåäöü]+", text, re.I) if t not in stop and len(t)>1}


def audit_article_catalog(records: Iterable[dict]) -> dict:
    rows=[dict(r) for r in (records or []) if isinstance(r,dict) and _text(r.get("article_no"))]
    issues=[]
    article_nos={_text(r.get("article_no")).casefold():_text(r.get("article_no")) for r in rows}

    # Identity collisions and source completeness.
    by_ean=defaultdict(list); by_el=defaultdict(list)
    for row in rows:
        ean=_text(row.get("ean")); el=_text(row.get("el_no"))
        if ean: by_ean[ean].append(row)
        if el: by_el[el].append(row)
        if not _text(row.get("description")):
            issues.append(_issue("Fejl","Identitet","missing_description","Beskrivelse mangler.",article=row,field="description",suggestion="Hent producentens officielle produktnavn/beskrivelse."))
        if not _text(row.get("manufacturer")):
            issues.append(_issue("Fejl","Identitet","missing_manufacturer","Producent mangler.",article=row,field="manufacturer",suggestion="Angiv officiel producent; brand bør være et separat felt."))
        if not ean:
            issues.append(_issue("Advarsel","Identitet","missing_ean","EAN/GTIN mangler.",article=row,field="ean",suggestion="Kontrollér producent/grossist og tilføj EAN/GTIN hvis den findes."))
        elif not _valid_gtin(ean):
            issues.append(_issue("Fejl","Identitet","invalid_ean","EAN/GTIN har ugyldigt format eller kontrolciffer.",article=row,field="ean",value=ean,suggestion="Verificér GTIN mod producentens kilde."))
        if not el:
            issues.append(_issue("Info","Identitet","missing_el_no","EL-/LM-nummer mangler.",article=row,field="el_no",suggestion="Tilføj grossistnummer når det findes; producentvarenummeret forbliver primær identitet."))
        if not _text(row.get("source")) and not _text(row.get("product_page")):
            issues.append(_issue("Fejl","Kilde","missing_source","Ingen kilde/produktside er angivet.",article=row,field="source",suggestion="Brug producentens officielle produktside som primær kilde."))
        if not _text(row.get("source_checked")):
            issues.append(_issue("Advarsel","Kilde","missing_source_checked","Kilden har ingen verifikationsdato.",article=row,field="source_checked",suggestion="Gem dato for seneste kontrol af kildedata."))
        if not (_text(row.get("image_local_path")) or _text(row.get("image_url"))):
            issues.append(_issue("Advarsel","Billede","missing_image","Direkte eller lokalt produktbillede mangler.",article=row,field="image_url",suggestion="Tilføj verificeret producentfoto eller lokal cache/reference."))

        # Module taxonomy. Explicit malformed values are errors; suspicious text is
        # only informational because a product number must never become a module.
        raw_module=_text(row.get("module_size"))
        source_module=_text(row.get("module_size_raw"))
        if raw_module and not core.normalize_article_module(raw_module):
            issues.append(_issue("Fejl","Modul","invalid_module","Modulværdien kan ikke være en gyldig normaliseret modulstørrelse.",article=row,field="module_size",value=raw_module,suggestion="Bevar producentens rå værdi, men fjern den fra modulfilteret indtil den er verificeret."))
        if source_module and source_module != raw_module and not core.normalize_article_module(source_module):
            issues.append(_issue("Info","Modul","raw_module_rejected","Rå producent-/importværdi er bevaret, men bruges ikke som modulstørrelse.",article=row,field="module_size_raw",value=source_module,suggestion="Kontrollér kun værdien hvis den skal bruges som modulfacet; rå kildedata er bevaret."))
        desc=_text(row.get("description"))
        for token in re.findall(r"(?<!\w)(\d{3,}\s*M)(?!\w)", desc, re.I):
            issues.append(_issue("Advarsel","Modul","suspicious_module_text","Beskrivelsen indeholder et M-tal der ligner et produkt-/mål-tal, ikke en modulstørrelse.",article=row,field="description",value=token,suggestion="Må ikke infereres som modulstørrelse uden eksplicit producentdata."))

        # Colour taxonomy: raw producer colour is kept, filter representation may
        # be canonical. Values describing an assembly state are not colours.
        raw_color=_text(row.get("color"))
        source_color=_text(row.get("color_raw"))
        if source_color and source_color != raw_color:
            issues.append(_issue("Info","Farve","color_normalized_from_source","Rå producentfarve er bevaret separat fra den normaliserede farvefacet.",article=row,field="color_raw",value=source_color,suggestion=f"Normaliseret farve: {raw_color or 'ingen farvefacet'}."))
        if raw_color and "uden afdækning" in raw_color.casefold():
            issues.append(_issue("Advarsel","Farve","non_color_value","Feltet Farve indeholder en konfigurations-/afdækningstilstand, ikke en egentlig farve.",article=row,field="color",value=raw_color,suggestion="Bevar producentteksten som variant/status og lad Farve være tom eller den faktiske farve."))

        # Controlled taxonomy and technical properties. These fields do not
        # replace producer wording; they make filtering and validation stable.
        normalized_category=_text(row.get("category_normalized")) or article_intelligence.derive_category(row)
        if normalized_category == "Øvrigt · Ukategoriseret":
            issues.append(_issue("Advarsel","Taksonomi","uncategorized","Artiklen kan ikke placeres sikkert i den kontrollerede kategoritaksonomi.",article=row,field="category_normalized",value=normalized_category,suggestion="Vælg en standardkategori manuelt eller udvid taksonomireglen for denne produkttype."))
        elif normalized_category not in article_intelligence.CATEGORY_PATHS:
            issues.append(_issue("Fejl","Taksonomi","invalid_normalized_category","Den normaliserede kategori findes ikke i den kontrollerede taksonomi.",article=row,field="category_normalized",value=normalized_category,suggestion="Vælg en kategori fra programmets standardtaksonomi."))

        specs=row.get("technical_specs") if isinstance(row.get("technical_specs"),dict) else article_intelligence.derive_technical_specs(row)
        if not specs and _text(row.get("kind")).casefold() != "cable":
            issues.append(_issue("Info","Egenskaber","missing_technical_specs","Der er ingen strukturerede tekniske egenskaber på artiklen.",article=row,field="technical_specs",suggestion="Tilføj kun verificerbare egenskaber; fri producenttekst bevares separat."))

        # Product semantics: own identity (family + variant) is distinct from
        # compatibility. Historical imports often copied a compatible design
        # series into the generic Design field; that is now detected explicitly.
        semantics=article_intelligence.derive_product_semantics(row)
        family=_text(semantics.get("product_family")); variant=_text(semantics.get("product_variant"))
        compatibility=article_intelligence.normalize_compatibility(semantics.get("compatibility"))
        compat_designs={str(x).casefold() for x in compatibility.get("design_series",[]) if _text(x)}
        desc_cf=_text(row.get("description")).casefold(); typ_cf=_text(row.get("product_type")).casefold(); cat_cf=_text(row.get("category")).casefold()
        is_box=("dåse" in desc_cf or "dåse" in typ_cf or "dåse" in cat_cf or "daase" in desc_cf)
        is_accessory=("tilbehør" in desc_cf or "tilbehoer" in desc_cf)
        box_identity_text=" ".join((desc_cf,typ_cf))
        is_physical_box=is_box and not is_accessory and any(token in box_identity_text for token in ("forfradåse", "forfra dåse", "forfradaase", "indstøbningsdåse", "indstoebningsdaase", "indmuringsdåse", "indmuringsdaase"))
        legacy_design=_text(row.get("design_family_raw") or row.get("design_family"))

        if _text(row.get("kind")).casefold() != "cable" and not family:
            issues.append(_issue("Info","Semantik","missing_product_family","Produktfamilie kunne ikke udledes sikkert.",article=row,field="product_family",suggestion="Angiv produktfamilie manuelt eller udvid en sikker identitetsregel; kompatibilitet må ikke bruges som familie."))
        if is_physical_box and family == "LK FUGA AIR" and not variant:
            issues.append(_issue("Advarsel","Semantik","missing_box_variant","FUGA AIR-dåsen mangler entydig produktvariant (Standard/SLIM).",article=row,field="product_variant",suggestion="Klassificér ud fra produktnavn/artikelserie; brug ikke kompatible rammeserier som variant."))
        if is_physical_box and variant and legacy_design and legacy_design.casefold() != variant.casefold():
            if legacy_design.casefold() in compat_designs:
                issues.append(_issue("Advarsel","Semantik","compatibility_used_as_identity","Et kompatibelt design er tidligere blevet brugt som dåsens eget Design/familie-felt.",article=row,field="design_family_raw" if row.get("design_family_raw") else "design_family",value=legacy_design,suggestion=f"Brug Produktfamilie='{family or 'ukendt'}' og Variant='{variant or 'ukendt'}'; behold {legacy_design} kun under kompatibilitet."))
            elif legacy_design.upper() in {"SLIM","CHOICE","PURE","SOFT","BASE 63","BASELINE 63","SOFTLINE 63"}:
                issues.append(_issue("Advarsel","Semantik","legacy_design_variant_conflict","Det gamle Design/familie-felt modsiger dåsens egen produktvariant.",article=row,field="design_family_raw" if row.get("design_family_raw") else "design_family",value=legacy_design,suggestion=f"Brug Produktfamilie='{family or 'ukendt'}' og Variant='{variant or 'ukendt'}'. Det gamle designfelt bevares kun som rå provenance."))
        if is_physical_box and "air slim" in desc_cf and variant.casefold() != "slim":
            issues.append(_issue("Fejl","Semantik","slim_name_variant_conflict","Produktnavnet angiver AIR SLIM, men den semantiske variant er ikke SLIM.",article=row,field="product_variant",value=variant,suggestion="Produktnavnet er stærkere identitetsevidens end serie-/kompatibilitetsfelter."))
        if is_physical_box and family == "LK FUGA AIR" and variant.casefold() == "standard" and "air slim" in desc_cf:
            issues.append(_issue("Fejl","Semantik","standard_slim_conflict","En AIR SLIM-dåse er klassificeret som Standard.",article=row,field="product_variant",value=variant,suggestion="Ret variant til SLIM."))
        raw_series=_text(row.get("series"))
        if is_physical_box and family == "LK FUGA AIR" and "/" in raw_series and "slim" in raw_series.casefold():
            issues.append(_issue("Advarsel","Semantik","mixed_family_variant_series","Kildens serie blander produktfamilie og variant i samme felt.",article=row,field="series",value=raw_series,suggestion="Bevar evt. rå serienavn, men brug Product family='LK FUGA AIR' og separat Standard/SLIM-variant i den kontrollerede model."))

        # Confirmed relation integrity is strict. Auto suggestions are not
        # persisted and therefore never become quality errors.
        relations=article_intelligence.normalize_relations(row.get("relations",[]),article_no=_text(row.get("article_no")))
        raw_relations=row.get("relations",[])
        if raw_relations and not relations:
            issues.append(_issue("Advarsel","Relationer","invalid_relations","Relationer findes i kildedata, men ingen kunne normaliseres sikkert.",article=row,field="relations",suggestion="Relationer skal have type og target_article_no; selv-relationer fjernes."))
        seen_rel=set()
        for rel in relations:
            target=_text(rel.get("target_article_no")); rel_key=(str(rel.get("type","")),target.casefold())
            if rel_key in seen_rel:
                issues.append(_issue("Advarsel","Relationer","duplicate_relation","Samme relation er registreret mere end én gang.",article=row,field="relations",value=target,suggestion="Behold kun én relation pr. type og målartikel."))
            seen_rel.add(rel_key)
            if target.casefold() not in article_nos:
                issues.append(_issue("Fejl","Relationer","missing_relation_target","En bekræftet artikelrelation peger på en artikel, som ikke findes i databasen.",article=row,field="relations",value=target,suggestion="Gendan målartiklen eller fjern/opdatér relationen."))

    for ean, group in by_ean.items():
        if len(group)>1:
            nos=[_text(r.get("article_no")) for r in group]
            issues.append(_issue("Fejl","Identitet","duplicate_ean",f"Samme EAN/GTIN bruges af {len(group)} artikelnumre.",field="ean",value=ean,suggestion="Verificér variant-/pakningsniveau; samme GTIN bør ikke pege på forskellige salgsartikler.",count=len(group),article_list=nos))
    for el, group in by_el.items():
        if len(group)>1:
            nos=[_text(r.get("article_no")) for r in group]
            issues.append(_issue("Advarsel","Identitet","duplicate_el_no",f"Samme EL-/LM-nummer bruges af {len(group)} artikelnumre.",field="el_no",value=el,suggestion="Kontrollér om posterne er dubletter eller alternative producentnumre.",count=len(group),article_list=nos))

    # Raw spelling duplicates which collapse to the same UI colour.
    color_groups=defaultdict(lambda: defaultdict(list))
    for row in rows:
        raw=_text(row.get("color"))
        if raw:
            canonical=core.normalize_article_color(raw)
            color_groups[canonical][raw].append(_text(row.get("article_no")))
    for canonical, variants in color_groups.items():
        if len(variants)>1:
            all_articles=[no for vals in variants.values() for no in vals]
            issues.append(_issue("Advarsel","Farve","duplicate_color_spelling",f"{len(variants)} rå farvebetegnelser ender som samme filterfarve '{canonical}'.",field="color",value=" | ".join(sorted(variants,key=str.casefold)),suggestion=f"Bevar rå producentværdi, men brug '{canonical}' som normaliseret filterværdi.",count=len(all_articles),article_list=all_articles))

    # Mixed manufacturer/brand values are a model issue rather than 300+ article
    # errors, so report them once per raw manufacturer label.
    manufacturers=defaultdict(list)
    for row in rows: manufacturers[_text(row.get("manufacturer"))].append(_text(row.get("article_no")))
    for manufacturer, nos in manufacturers.items():
        if " / " in manufacturer:
            issues.append(_issue("Advarsel","Taksonomi","mixed_manufacturer_brand",f"Producentfeltet '{manufacturer}' blander sandsynligvis producent og brand.",field="manufacturer",value=manufacturer,suggestion="Bevar producentens officielle navn i manufacturer og læg fx LK i et separat brand-felt.",count=len(nos),article_list=nos))

    # Status should gain a canonical state without deleting producer/source detail.
    statuses=defaultdict(list)
    for row in rows: statuses[_text(row.get("status"))].append(_text(row.get("article_no")))
    canonical_groups=defaultdict(list)
    for raw, nos in statuses.items(): canonical_groups[canonical_status(raw)].append((raw,nos))
    if len(statuses)>len(canonical_groups):
        detail=[]
        all_nos=[]
        for canonical, variants in sorted(canonical_groups.items()):
            detail.append(f"{canonical}: {len(variants)} variant(er)")
            for _raw,nos in variants: all_nos.extend(nos)
        issues.append(_issue("Info","Status","status_taxonomy",f"{len(statuses)} rå statusbetegnelser kan samles i {len(canonical_groups)} stabile statusgrupper.",field="status",value=" · ".join(detail),suggestion="Tilføj status_raw + status_normalized; behold kilde-/erstatningsdetaljen separat.",count=len(all_nos),article_list=all_nos))

    # Overlapping category names for the same manufacturer: audit only, never merge.
    categories_by_manufacturer=defaultdict(lambda: defaultdict(list))
    for row in rows:
        categories_by_manufacturer[_text(row.get("manufacturer"))][_text(row.get("category"))].append(_text(row.get("article_no")))
    seen_pairs=set()
    for manufacturer, cats in categories_by_manufacturer.items():
        names=[c for c in cats if c]
        for i,a in enumerate(names):
            ta=_taxonomy_tokens(a)
            if len(ta)<2: continue
            for b in names[i+1:]:
                tb=_taxonomy_tokens(b)
                if len(tb)<2: continue
                overlap=len(ta & tb)/max(1,min(len(ta),len(tb)))
                if overlap < 0.75: continue
                pair=tuple(sorted((a,b)))
                if pair in seen_pairs: continue
                seen_pairs.add(pair)
                nos=cats[a]+cats[b]
                issues.append(_issue("Info","Taksonomi","category_overlap",f"To kategorier hos {manufacturer} overlapper kraftigt og bør vurderes som rå vs. normaliseret kategori.",field="category",value=f"{a}  ↔  {b}",suggestion="Bevar producent-/kildekategori, men vælg én kontrolleret normalized_category hvis de betyder det samme.",count=len(nos),article_list=nos))

    # Variant groups should represent one base product. A group crossing
    # controlled categories is usually an over-aggressive grouping rule.
    variant_groups=defaultdict(list)
    for row in rows:
        gid=_text(row.get("variant_group_id"))
        if gid: variant_groups[gid].append(row)
    for gid,members in variant_groups.items():
        if len(members)<2: continue
        cats={_text(m.get("category_normalized")) or article_intelligence.derive_category(m) for m in members}
        if len(cats)>1:
            nos=[_text(m.get("article_no")) for m in members]
            issues.append(_issue("Advarsel","Varianter","variant_category_collision","En variantgruppe spænder over flere standardkategorier og bør kontrolleres.",field="variant_group_id",value=gid,suggestion="Opdel gruppen manuelt eller justér variantnøglen; variantgrupper må ikke bruges som kompatibilitetsbevis.",count=len(nos),article_list=nos))
        families={_text(m.get("product_family")) for m in members if _text(m.get("product_family"))}
        own_variants={_text(m.get("product_variant")) for m in members if _text(m.get("product_variant"))}
        if len(families)>1 or len(own_variants)>1:
            nos=[_text(m.get("article_no")) for m in members]
            issues.append(_issue("Advarsel","Semantik","variant_identity_collision","En variantgruppe krydser produktfamilie eller egen produktvariant.",field="variant_group_id",value=gid,suggestion="Produktfamilie og egen variant er identitet og skal indgå i variantnøglen; kompatibilitet må ikke samle grupperne.",count=len(nos),article_list=nos))

    # Stable ordering: important problems first, then category and article.
    issues.sort(key=lambda x:(SEVERITY_ORDER.get(x["severity"],9),x["category"].casefold(),x["article_no"].casefold(),x["code"]))
    affected={x["article_no"] for x in issues if x["article_no"] and x["severity"] in {"Fejl","Advarsel"}}
    # Per-article score is intentionally transparent rather than probabilistic.
    # Group findings also affect every explicitly listed article.
    score_by_no={_text(r.get("article_no")):100 for r in rows}
    counts_by_no={no:{"errors":0,"warnings":0,"info":0} for no in score_by_no}
    for issue in issues:
        targets=[]
        if _text(issue.get("article_no")): targets.append(_text(issue.get("article_no")))
        targets.extend(_text(x) for x in issue.get("articles",[]) if _text(x))
        severity=_text(issue.get("severity"))
        bucket={"Fejl":"errors","Advarsel":"warnings","Info":"info"}.get(severity)
        for no in set(targets):
            if no not in score_by_no: continue
            if bucket: counts_by_no[no][bucket]+=1
    for no,counts in counts_by_no.items():
        # Errors dominate, warnings matter, while informational cleanup hints
        # are capped so a catalogue-wide taxonomy note cannot make otherwise
        # usable articles look poor.
        penalty=min(66,counts.get("errors",0)*22)+min(28,counts.get("warnings",0)*7)+min(5,counts.get("info",0))
        score_by_no[no]=max(0,100-penalty)
    profiles={}
    for row in rows:
        no=_text(row.get("article_no")); score=int(score_by_no.get(no,100)); counts=counts_by_no.get(no,{})
        status="God" if score>=90 else ("Kontrollér" if score>=70 else "Kræver kontrol")
        profiles[no]={"score":score,"status":status,**counts}
    for issue in issues:
        no=_text(issue.get("article_no"))
        issue["quality_score"]=profiles.get(no,{}).get("score","") if no else ""
    summary={
        "articles":len(rows),
        "errors":sum(1 for x in issues if x["severity"]=="Fejl"),
        "warnings":sum(1 for x in issues if x["severity"]=="Advarsel"),
        "info":sum(1 for x in issues if x["severity"]=="Info"),
        "affected_articles":len(affected),
        "clean_articles":max(0,len(rows)-len(affected)),
        "issue_count":len(issues),
        "quality_score":(sum(score_by_no.values())/len(score_by_no)) if score_by_no else 100.0,
        "quality_good":sum(1 for score in score_by_no.values() if score>=90),
        "quality_review":sum(1 for score in score_by_no.values() if score<70),
    }
    summary["clean_percent"]=(100.0*summary["clean_articles"]/len(rows)) if rows else 100.0
    return {"summary":summary,"issues":issues,"profiles":profiles}
