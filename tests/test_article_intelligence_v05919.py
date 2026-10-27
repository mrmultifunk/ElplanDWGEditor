from __future__ import annotations

import json

import article_exchange
import article_intelligence as intel
import article_quality
import core_logic as core


def _row(no, desc, **extra):
    row = {
        "article_no": no,
        "description": desc,
        "manufacturer": extra.pop("manufacturer", "Schneider Electric / Lauritz Knudsen"),
        "unit": "stk",
        "series": extra.pop("series", "LK FUGA"),
        "category": extra.pop("category", "LK FUGA"),
        "kind": extra.pop("kind", "component"),
    }
    row.update(extra)
    return row


def test_controlled_taxonomy_preserves_source_category_and_handles_catalog_families():
    rows = core.normalize_article_catalog([
        _row("A1", "LK FUGA stikkontakt med jord 16 A", category="LK FUGA · Stikkontakter og udtag"),
        _row("A2", "IHC Control input modul", series="IHC Control", category="IHC Control"),
        _row("A3", "Actassi RJ45 dataudtag", series="Actassi", category="Actassi"),
    ])
    by_no = {r["article_no"]: r for r in rows}
    assert by_no["A1"]["category"] == "LK FUGA · Stikkontakter og udtag"
    assert by_no["A1"]["category_normalized"] == "Installation · Stikkontakter og udtag"
    assert by_no["A2"]["category_normalized"] == "Styring · IHC og automatik"
    assert by_no["A3"]["category_normalized"] == "Kabler og data · Data og netværk"
    assert by_no["A1"]["taxonomy_version"] == str(intel.TAXONOMY_VERSION)


def test_structured_specs_extract_explicit_values_but_not_cat6a_as_current():
    smart = core.normalize_article_catalog([
        _row("S1", "Zigbee lysdæmper 230VAC 16 A IP44", category="LK FUGA · Afbrydere", ip_rating="IP44")
    ])[0]
    specs = smart["technical_specs"]
    assert specs["rated_voltage"] == "230 VAC"
    assert specs["rated_current"] == "16 A"
    assert specs["smart_protocol"] == "Zigbee"
    assert specs["dimmable"] == "Ja"
    assert specs["ip_rating"] == "IP44"

    data = core.normalize_article_catalog([
        _row("D1", "Actassi Kobber Cat. 6A patchkabel S/FTP blå", series="Actassi", category="Actassi", color="blå")
    ])[0]
    assert "rated_current" not in data["technical_specs"]


def test_manual_specs_override_derived_specs():
    row = core.normalize_article_catalog([
        _row("M1", "Afbryder 230VAC 10 A", technical_specs_manual={"rated_current": "16 A", "custom": "verificeret"})
    ])[0]
    assert row["technical_specs"]["rated_voltage"] == "230 VAC"
    assert row["technical_specs"]["rated_current"] == "16 A"
    assert row["technical_specs"]["custom"] == "verificeret"
    assert row["technical_specs_manual"]["rated_current"] == "16 A"


def test_variant_groups_join_color_and_cct_variants_but_not_different_base_product():
    rows = core.normalize_article_catalog([
        {
            "article_no":"35511012", "description":"Nordtronic · Low Profile Flexible G2 Ø55 med driver, 2700K, Hvid",
            "manufacturer":"Nordtronic A/S", "series":"Low Profile Flexible G2", "category":"Nordtronic · Downlight",
            "product_type":"Downlight", "design_family":"Low Profile Flexible G2", "cct":"2700K", "color":"Hvid", "unit":"stk",
        },
        {
            "article_no":"35511093", "description":"Nordtronic · Low Profile Flexible G2 Ø55 med driver, 3000K, Sort",
            "manufacturer":"Nordtronic A/S", "series":"Low Profile Flexible G2", "category":"Nordtronic · Downlight",
            "product_type":"Downlight", "design_family":"Low Profile Flexible G2", "cct":"3000K", "color":"Sort", "unit":"stk",
        },
        {
            "article_no":"35512012", "description":"Nordtronic · Low Profile Flexible G2 Ø55 med serial connector, 2700K, Hvid",
            "manufacturer":"Nordtronic A/S", "series":"Low Profile Flexible G2", "category":"Nordtronic · Downlight",
            "product_type":"Downlight", "design_family":"Low Profile Flexible G2", "cct":"2700K", "color":"Hvid", "unit":"stk",
        },
    ])
    a,b,c = rows
    assert a["variant_group_id"] == b["variant_group_id"]
    assert a["variant_count"] == b["variant_count"] == 2
    assert set(a["variant_axes"]) == {"color", "cct"}
    assert c["variant_group_id"] != a["variant_group_id"]
    assert c["variant_count"] == 1


def test_relation_context_separates_confirmed_relations_from_suggestions():
    rows = core.normalize_article_catalog([
        _row("SW1", "LK FUGA 1-polet afbryder 1M", category="LK FUGA · Afbrydere", product_type="Afbryder / betjening", module_size="1M", relations=[{"type":"compatible","target_article_no":"T1","source":"manual"}]),
        _row("T1", "LK FUGA tangent 1M hvid", category="LK FUGA · Tangenter og afdækninger", product_type="Tangent / afdækning", module_size="1M", color="hvid"),
        _row("T2", "LK FUGA tangent 1M koksgrå", category="LK FUGA · Tangenter og afdækninger", product_type="Tangent / afdækning", module_size="1M", color="koksgrå"),
    ])
    ctx = intel.relation_context(rows[0], rows)
    assert [r["target_article_no"] for r in ctx["confirmed"]] == ["T1"]
    assert any(r["article_no"] == "T2" for r in ctx["suggestions"])
    assert all(r["article_no"] != "T1" for r in ctx["suggestions"])


def test_quality_validator_checks_relation_targets_and_returns_per_article_score():
    rows = core.normalize_article_catalog([
        _row("Q1", "LK FUGA afbryder 1M", category="LK FUGA · Afbrydere", product_type="Afbryder / betjening", relations=[{"type":"compatible","target_article_no":"MISSING"}]),
    ])
    result = article_quality.audit_article_catalog(rows)
    codes = {x["code"] for x in result["issues"]}
    assert "missing_relation_target" in codes
    assert result["profiles"]["Q1"]["score"] < 100
    assert 0 <= result["summary"]["quality_score"] <= 100


def test_article_exchange_json_roundtrip_keeps_structured_manual_data(tmp_path):
    path = tmp_path / "articles.json"
    rows = core.normalize_article_catalog([
        _row("R1", "LK FUGA stikkontakt", technical_specs_manual={"rated_current":"16 A"}, relations=[{"type":"alternative","target_article_no":"R2"}]),
        _row("R2", "LK FUGA stikkontakt alternativ"),
    ])
    article_exchange.save_article_library_json(path, rows, app_version="test")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["format_version"] == 4
    loaded = article_exchange.load_article_library(path)
    r1 = next(r for r in loaded.articles if r["article_no"] == "R1")
    assert r1["technical_specs_manual"]["rated_current"] == "16 A"
    assert r1["relations"][0]["target_article_no"] == "R2"


def test_article_ui_source_exposes_new_relations_and_quality_workflows():
    source = open("qt_articles.py", encoding="utf-8").read()
    for token in (
        "Standardkategori", "Tekniske egenskaber", "Relationer…", "Bekræftede relationer",
        "Forslag", "Datakvalitet:", "quality_score", "category_normalized",
    ):
        assert token in source


def test_relation_suggestions_prefer_explicit_product_system_over_stale_series():
    source = {
        "article_no": "A1",
        "manufacturer": "LK",
        "description": "LK FUGA korrespondanceafbryder",
        "series": "LK FUGA",
        "design_family": "FUGA",
        "module_size": "1M",
        "category_normalized": "Installation · Afbrydere og betjening",
    }
    stale = {
        "article_no": "B1",
        "manufacturer": "LK",
        "description": "CLIC'LINE kanaldåse 1 modul",
        # Deliberately stale metadata from an old import:
        "series": "LK FUGA",
        "design_family": "FUGA",
        "module_size": "1M",
        "category_normalized": "Installation · Dåser og montage",
    }
    rows = intel.enrich_catalog([source, stale])
    source = next(row for row in rows if row["article_no"] == "A1")
    suggestions = intel.relation_context(source, rows)["suggestions"]
    assert all(row["article_no"] != "B1" for row in suggestions)
