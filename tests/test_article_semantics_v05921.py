import article_intelligence as ai
import article_quality
import core_logic as core
import lk_catalog_sync


def _article(no, description, product_type="Forfradåse", **extra):
    row={
        "article_no": no,
        "description": description,
        "manufacturer": "Schneider Electric / Lauritz Knudsen",
        "series": "LK FUGA AIR / SLIM",
        "product_type": product_type,
        "category": "LK FUGA · Dåser",
    }
    row.update(extra)
    return row


def test_504d3010_is_standard_air_and_slim_is_not_identity():
    row=core.normalize_article_catalog([_article(
        "504D3010", "LK FUGA® AIR dåser forfradåse 1 modul", design_family="SLIM"
    )])[0]
    assert row["product_family"] == "LK FUGA AIR"
    assert row["product_variant"] == "Standard"
    assert row.get("design_family", "") == ""
    assert row["design_family_raw"] == "SLIM"
    assert "SLIM" not in row["compatibility"]["design_series"]


def test_air_slim_front_box_has_own_slim_variant():
    row=core.normalize_article_catalog([_article(
        "504D3510", "LK FUGA® AIR dåser SLIM forfradåse 1 modul", design_family="SLIM"
    )])[0]
    assert row["product_family"] == "LK FUGA AIR"
    assert row["product_variant"] == "SLIM"
    assert row.get("design_family", "") == ""
    assert "SLIM" in row["compatibility"]["design_series"]


def test_cast_air_box_is_standard_but_slim_can_be_compatible():
    row=core.normalize_article_catalog([_article(
        "504D6010", "504D6010", product_type="Indstøbningsdåse", design_family="SLIM"
    )])[0]
    assert row["product_family"] == "LK FUGA AIR"
    assert row["product_variant"] == "Standard"
    assert "SLIM" in row["compatibility"]["design_series"]
    assert any("betinget" in n.casefold() for n in row["compatibility"].get("notes", []))


def test_fire_resistant_air_box_gets_distinct_product_variant():
    row=core.normalize_article_catalog([_article(
        "504D3110", "LK FUGA® AIR dåser brandsikker forfradåse 1 modul", design_family="AIR"
    )])[0]
    assert row["product_family"] == "LK FUGA AIR"
    assert row["product_variant"] == "Brandsikker"


def test_validator_finds_legacy_compatibility_used_as_identity():
    row=core.normalize_article_catalog([_article(
        "504D6010", "504D6010", product_type="Indstøbningsdåse", design_family="SLIM"
    )])[0]
    report=article_quality.audit_article_catalog([row])
    codes={issue["code"] for issue in report["issues"]}
    assert "compatibility_used_as_identity" in codes


def test_validator_finds_3010_legacy_slim_conflict():
    row=core.normalize_article_catalog([_article(
        "504D3010", "LK FUGA® AIR dåser forfradåse 1 modul", design_family="SLIM"
    )])[0]
    report=article_quality.audit_article_catalog([row])
    codes={issue["code"] for issue in report["issues"]}
    assert "legacy_design_variant_conflict" in codes


def test_predefined_air_family_contains_missing_3020_and_semantics():
    lookup={r["article_no"]:r for r in core.load_predefined_article_catalog()}
    row=lookup["504D3020"]
    assert row["el_no"] == "1017059399"
    assert row["ean"] == "5703302156103"
    assert row["product_family"] == "LK FUGA AIR"
    assert row["product_variant"] == "Standard"
    assert float(row["cutout_mm"]) == 57.0


def test_variant_group_separates_standard_and_slim_box_identity():
    standard=core.normalize_article_catalog([_article("504D3010", "LK FUGA® AIR dåser forfradåse 1 modul")])[0]
    slim=core.normalize_article_catalog([_article("504D3510", "LK FUGA® AIR dåser SLIM forfradåse 1 modul")])[0]
    assert ai.auto_variant_group_key(standard) != ai.auto_variant_group_key(slim)


def test_ui_exposes_family_variant_and_compatibility_as_separate_concepts():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1] / "qt_articles.py").read_text(encoding="utf-8")
    for token in ("Produktfamilie", "Produktvariant", "Kompatibilitet", "product_family", "product_variant"):
        assert token in source


def test_exchange_roundtrip_preserves_semantic_identity_and_compatibility(tmp_path):
    import article_exchange
    row=core.normalize_article_catalog([_article(
        "504D6010", "LK FUGA® AIR indstøbningsdåse 1 modul", product_type="Indstøbningsdåse"
    )])[0]
    for suffix, saver in (("json", article_exchange.save_article_library_json), ("csv", article_exchange.save_article_library_csv)):
        path=tmp_path / f"articles.{suffix}"
        saver(path, [row])
        loaded=article_exchange.load_article_library(path).articles[0]
        assert loaded["product_family"] == "LK FUGA AIR"
        assert loaded["product_variant"] == "Standard"
        assert "SLIM" in loaded["compatibility"]["design_series"]


def test_lk_parser_keeps_design_series_as_compatibility_not_box_identity():
    standard_html='''<html><body>
      <h1>LK FUGA AIR forfradåse 1 modul, blå</h1>
      <div>Farve</div><div>Blå</div><div>LK nummer</div><div>504D3010</div>
      <div>Område</div><div>LK FUGA AIR</div><div>Produkt- eller komponenttype</div><div>Montageboks</div>
      <div>Designserie</div><div>Pure Choice Soft</div><div>Antal moduler</div><div>1 modul</div>
      <p>Dåserne kan monteres med følgende rammetyper: Teknisk monteringsramme, samt design rammer: CHOICE, PURE, SOFT.</p>
    </body></html>'''
    slim_html=standard_html.replace('forfradåse 1 modul, blå','AIR SLIM forfradåse 1 modul, orange').replace('504D3010','504D3510').replace('Pure Choice Soft','Slim Choice Pure Soft')
    standard=lk_catalog_sync.parse_product_page(standard_html, fallback_article_no='504D3010')
    slim=lk_catalog_sync.parse_product_page(slim_html, fallback_article_no='504D3510')
    assert standard['product_family']=='LK FUGA AIR' and standard['product_variant']=='Standard'
    assert 'SLIM' not in standard['compatibility']['design_series']
    assert slim['product_family']=='LK FUGA AIR' and slim['product_variant']=='SLIM'
    assert 'SLIM' in slim['compatibility']['design_series']
